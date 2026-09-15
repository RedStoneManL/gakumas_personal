from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    spec = importlib.util.spec_from_file_location("colab_test_" + name, ROOT / "colab" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load_module("bootstrap")
builder = load_module("build_notebook")
config_builder = load_module("build_configs")
preflight = load_module("preflight")
process_utils = load_module("process_utils")


def zip_bytes(files=None, *, extra=None, manifest_transform=None, info_transform=None):
    files = files or {"training/readme.txt": b"hello", "arena/native.js": b"native"}
    manifest = {"schema": "hif-colab-training/1", "files": [
        {"path": name, "size": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for name, value in files.items()]}
    if manifest_transform:
        manifest_transform(manifest)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, value in files.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if info_transform:
                info_transform(info)
            archive.writestr(info, value)
        for name, value in (extra or {}).items():
            archive.writestr(name, value)
    data.seek(0)
    return data


class ColabNotebookTests(unittest.TestCase):
    def test_drive_log_failure_stops_writer_and_preserves_original_exception(self):
        writer = mock.Mock()
        writer.stdout = mock.MagicMock()
        writer.stdout.__iter__.return_value = iter(["batch output\n"])
        log = mock.MagicMock()
        error = OSError("Drive unavailable")
        log.__enter__.return_value.write.side_effect = error
        for shutdown_error in (None, RuntimeError("shutdown also failed")):
            writer.stdout.__iter__.return_value = iter(["batch output\n"])
            with tempfile.TemporaryDirectory() as folder:
                with mock.patch.object(process_utils.subprocess, "Popen", return_value=writer), \
                     mock.patch.object(process_utils.Path, "open", return_value=log), \
                     mock.patch.object(process_utils, "stop_and_drain", side_effect=shutdown_error) as stop, \
                     mock.patch("builtins.print"):
                    with self.assertRaises(OSError) as raised:
                        process_utils.run_logged(["python", "train"], Path(folder)/"log.txt", cwd=folder, env={})
                    self.assertIs(raised.exception, error)
                    stop.assert_called_once_with(writer)

    def test_interrupt_drains_stdout_and_confirms_exit_before_control_returns(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.communicate.return_value = ("saved\n", None)
        self.assertEqual(process_utils.stop_and_drain(process), "saved\n")
        process.send_signal.assert_called_once()
        process.communicate.assert_called_once_with(timeout=30)
        process.kill.assert_not_called()

    def test_unresponsive_writer_is_terminated_and_killed_with_bounded_wait(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.communicate.side_effect = [subprocess.TimeoutExpired("training", 30),
                                           subprocess.TimeoutExpired("training", 5), ("stopped\n", None)]
        self.assertEqual(process_utils.stop_and_drain(process), "stopped\n")
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_args_list, [mock.call(timeout=30), mock.call(timeout=5), mock.call(timeout=5)])

    def test_second_interrupt_still_reaps_writer(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.communicate.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            process_utils.stop_and_drain(process)
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)

    def test_notebook_is_reproducible_valid_code_and_unexecuted(self):
        saved = json.loads((ROOT / "colab" / "HIF_Training.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(saved, builder.notebook())
        self.assertEqual(saved["metadata"]["accelerator"], "GPU")
        identifiers = [cell["id"] for cell in saved["cells"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for i, cell in enumerate(saved["cells"]):
            if cell["cell_type"] == "code":
                ast.parse(cell["source"], filename=f"cell-{i}")
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])

    def test_notebook_uses_new_runner_drive_and_explicit_gpu_without_torch_install(self):
        code = "\n".join(cell["source"] for cell in builder.notebook()["cells"] if cell["cell_type"] == "code")
        for token in ("run_training.py", "preflight.py", "--persistent-root", 'drive.mount("/content/drive")',
                      "--system-site-packages", '"--no-deps"', "TOTAL_HOURS = 24", "SESSION_HOURS = 8",
                      "full_produce_mixed", "selected_config_sha256", "torch.cuda.is_available()"):
            self.assertIn(token, code)
        self.assertNotIn("training_enabled", code)
        self.assertNotIn("pip install torch", code)
        self.assertNotIn("Javascript", code)
        self.assertNotIn("setInterval", code)
        # Verifier is embedded, so unpacking does not import code from the ZIP.
        self.assertIn((ROOT / "colab" / "bootstrap.py").read_text(encoding="utf-8").strip(), code)
        for token in ('CONFIG_NAME = "full_produce_setup_mixed"', 'RUN_NAME = "hif-setup-mixed-v4"',
                      '--without-pip', 'MIGRATE_FROM_RUN', '--migrate-from-run',
                      'full_produce_select', 'setup_modes', 'normalized_entropy', 'approx_kl', 'equipped_inventory_counts'):
            self.assertIn(token, code)

    def test_start_is_nonblocking_and_controls_are_separate_explicit_cells(self):
        cells = [c['source'] for c in builder.notebook()['cells'] if c['cell_type'] == 'code']
        start = next(c for c in cells if '# 7.' in c)
        controls = next(c for c in cells if '# 8.' in c)
        stop = next(c for c in cells if '# 9.' in c)
        self.assertIn('TRAINING_SESSION = start_session(', start)
        self.assertNotIn('run_logged(command', start)
        self.assertNotIn('.wait(', start)
        self.assertNotIn('write_runtime_control(', start)
        for token in ('LIVE_WORKERS = 12', 'LIVE_EPISODES_PER_UPDATE = 40',
                      'LIVE_MINIBATCH_SIZE = 128', 'LIVE_MICROBATCH_SIZE = 32', 'write_runtime_control('):
            self.assertIn(token, controls)
        self.assertIn('REQUEST_SAFE_STOP = False', stop)
        settings = next(c for c in cells if '# 5.' in c)
        self.assertIn('WORKERS = "auto"  # @param {type:"string"}', settings)
        self.assertIn('PPO_MICROBATCH = "auto"  # @param {type:"string"}', settings)

    def test_offline_diagnostic_notebook_needs_only_drive_and_has_valid_embedded_reader(self):
        notebook = builder.diagnostic_notebook()
        self.assertNotIn('accelerator', notebook['metadata'])
        code = '\n'.join(c['source'] for c in notebook['cells'] if c['cell_type'] == 'code')
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                ast.parse(cell['source'])
        self.assertIn('drive.mount(', code)
        self.assertNotIn('BUNDLE_ROOT', code)
        self.assertNotIn('RUN_PYTHON', code)
        self.assertNotIn('TRAINING_SESSION', code)
        reader_cell = next(c['source'] for c in notebook['cells'] if 'DIAGNOSTIC_SOURCE = ' in c['source'])
        embedded = ast.literal_eval(ast.parse(reader_cell).body[0].value)
        self.assertEqual(embedded, (ROOT / 'colab/diagnose_run.py').read_text(encoding='utf8'))
        ast.parse(embedded)

    def test_resource_observer_is_standalone_with_unique_log_and_preserved_bundle(self):
        start = next(c['source'] for c in builder.notebook()['cells'] if '# 7.' in c['source'])
        tree = ast.parse(start)
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'RESOURCE_WATCH_SOURCE' for t in n.targets))
        self.assertEqual(ast.literal_eval(assignment.value), (ROOT / 'colab/resource_watch.py').read_text(encoding='utf8'))
        for token in ('TRAINING_SESSION.process.pid', '"--create-time"', '"--status-path"',
                      '"--local-output"', '"--interval", "15"', 'WATCH_DIR.name + ".jsonl"',
                      'WATCH_SCRIPT = WATCH_DIR / "resource_watch.py"'):
            self.assertIn(token, start)
        self.assertNotIn('BUNDLE_ROOT / "resource_watch.py"', start)

    def test_config_generator_requires_explicit_inventory_and_embeds_exact_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            training = Path(folder)
            here = training / 'colab'
            here.mkdir()
            (training / 'configs').mkdir()
            for name in ('full_produce', 'exam_score'):
                (training / 'configs' / f'{name}.json').write_bytes((ROOT / 'configs' / f'{name}.json').read_bytes())
            with mock.patch('builtins.print'):
                config_builder.main(here)
            self.assertFalse((here / 'configs/full_produce_setup_mixed.json').exists())
            inventory = {'schema_version': 'gakumas-setup-inventory/1',
                         'supports': [{'support_card_id': 'test-fixture', 'level': 60}],
                         'memories': [], 'memory_components': {'cards': [{'fixture': 'carried-card'}],
                             'gold_factors': [{'fixture': 'gold-factor'}], 'hif_abilities': []},
                         'provenance': {'scope': 'unit-test only'}}
            inventory_path = here / 'configs/research_inventory.json'
            inventory_path.write_text(json.dumps(inventory), encoding='utf8')
            before = inventory_path.read_bytes()
            config_builder.main(here)
            for name, mode in (('full_produce_select', 'select'), ('full_produce_setup_mixed', 'mixed')):
                config = json.loads((here / 'configs' / f'{name}.json').read_text(encoding='utf8'))
                self.assertEqual(config['task_config']['setup_inventory'], inventory)
                self.assertEqual(config['task_config']['setup_mode'], mode)
                self.assertEqual(len(config['task_config']['loadout_pool']), 5)
                self.assertEqual(config['episodes_per_update'], 10)
                self.assertEqual(config['eval_episodes'], 10)
                self.assertEqual(config['ppo']['setup_entropy_coefficient'], .05)
            given = json.loads((here / 'configs/full_produce_mixed.json').read_text(encoding='utf8'))
            self.assertEqual(given['task_config']['setup_mode'], 'given')
            self.assertNotIn('setup_inventory', given['task_config'])
            self.assertEqual(inventory_path.read_bytes(), before)

    def test_manifest_bytes_are_verified_before_any_extraction(self):
        contents = zip_bytes()
        with zipfile.ZipFile(contents) as archive:
            members, manifest, digest = bootstrap.validate_zip_archive(archive)
            self.assertEqual(len(members), 3)
            self.assertEqual(len(digest), 64)
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "bundle.zip"
            archive_path.write_bytes(contents.getvalue())
            unpacked, _, _ = bootstrap.extract_verified_bundle(archive_path, Path(folder) / "unpacked", digest)
            self.assertEqual((unpacked / "training/readme.txt").read_bytes(), b"hello")
            self.assertEqual(set(p.relative_to(unpacked).as_posix() for p in unpacked.rglob("*") if p.is_file()),
                             {"manifest.json", "training/readme.txt", "arena/native.js"})

    def test_rejects_extra_files_bad_hash_bad_size_and_old_schema(self):
        mutations = [
            dict(extra={"injected.py": b"bad"}),
            dict(manifest_transform=lambda m: m["files"][0].update(sha256="0"*64)),
            dict(manifest_transform=lambda m: m["files"][0].update(size=12345)),
            dict(manifest_transform=lambda m: m.update(schema="hif-colab-bundle/1")),
            dict(manifest_transform=lambda m: m["files"].append(m["files"][0])),
        ]
        for arguments in mutations:
            with self.subTest(arguments=list(arguments)):
                with zipfile.ZipFile(zip_bytes(**arguments)) as archive:
                    with self.assertRaises(ValueError):
                        bootstrap.validate_zip_archive(archive)

    def test_rejects_traversal_links_collisions_and_manifest_pin_mismatch(self):
        for path in ("../escape", "/abs", "a\\b", "C:drive", "CON.txt", "a/./b", "a//b"):
            with self.subTest(path=path), zipfile.ZipFile(zip_bytes({path: b"bad"})) as archive:
                with self.assertRaises(ValueError):
                    bootstrap.validate_zip_archive(archive)
        def symlink(info):
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        for data in (zip_bytes(info_transform=symlink), zip_bytes({"A": b"1", "a": b"2"}),
                     zip_bytes({"file": b"1", "file/child": b"2"})):
            with zipfile.ZipFile(data) as archive:
                with self.assertRaises(ValueError):
                    bootstrap.validate_zip_archive(archive)
        with zipfile.ZipFile(zip_bytes()) as archive:
            with self.assertRaises(ValueError):
                bootstrap.validate_zip_archive(archive, "0" * 64)

    def test_each_mixed_profile_gets_complete_own_probe_configuration(self):
        source = {"task": "full_produce", "model": {"width": 64}, "task_config": {
            "loadout": {"idol_card_id": "unused_base"}, "research_config": {"unused": True},
            "loadout_pool": [{"name": "a", "loadout": {"idol_card_id": "a"}},
                             {"name": "b", "loadout": {"idol_card_id": "b"}, "research_config": {"profile": 2}}]}}
        before = copy.deepcopy(source)
        profiles = preflight.profile_probe_configs(source)
        self.assertEqual([name for name, _ in profiles], ["a", "b"])
        self.assertEqual([row["task_config"]["loadout"]["idol_card_id"] for _, row in profiles], ["a", "b"])
        self.assertEqual([row["task_config"]["research_config"] for _, row in profiles], [{}, {"profile": 2}])
        self.assertTrue(all(row["task_config"]["loadout_pool"] is None for _, row in profiles))
        self.assertEqual(source, before)

    def test_preflight_explicitly_covers_five_profiles_times_two_setup_modes(self):
        source = {"task": "full_produce", "task_config": {"setup_mode": "mixed",
            "setup_inventory": {"kept": True}, "loadout_pool": [
                {"name": str(i), "loadout": {"idol_card_id": str(i)}} for i in range(5)]}}
        before = copy.deepcopy(source)
        probes = preflight.profile_probe_configs(source)
        self.assertEqual(len(probes), 10)
        self.assertEqual({(name, cfg["task_config"]["setup_mode"]) for name, cfg in probes},
                         {(str(i), mode) for i in range(5) for mode in ("given", "select")})
        self.assertTrue(all(cfg["task_config"]["loadout_pool"] is None for _, cfg in probes))
        self.assertTrue(all(cfg["task_config"]["setup_inventory"] == {"kept": True} for _, cfg in probes))
        self.assertEqual(source, before)
        source["task_config"]["loadout_pool"] = None
        self.assertEqual([cfg["task_config"]["setup_mode"] for _, cfg in preflight.profile_probe_configs(source)],
                         ["given", "select"])


if __name__ == "__main__":
    unittest.main()
