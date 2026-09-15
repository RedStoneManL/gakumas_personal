"""Generate the self-contained Chinese Colab notebook with verified bootstrap."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from textwrap import dedent


HERE = Path(__file__).resolve().parent


def cell(kind, source):
    result = {"cell_type": kind, "metadata": {}, "source": dedent(source).strip() + "\n"}
    result["id"] = hashlib.sha256((kind + result["source"]).encode()).hexdigest()[:12]
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def notebook():
    cells = [cell("markdown", """
        # HIF 完整培育 / 单场冲分训练

        准备两个文件：本 Notebook 和配套的 **gakumas-colab-training.zip**。在 Colab 上传此 Notebook，
        选择 **运行时 → 更改运行时类型 → GPU**，然后从上到下运行。无需上传第三个文件。

        默认累计训练 **24 小时**，每次会话最多安排 **8 小时**；这些是程序预算，并不保证
        [Colab 会话可持续对应时长](https://research.google.com/colaboratory/faq.html)。每次完整更新后
        把可恢复状态保存到 Google Drive。运行时断开后，重新运行本 Notebook、选择同一 ZIP 并保持同一
        `RUN_NAME`，即可自动恢复最近完整保存的更新。训练不会从半局或半个梯度更新恢复。

        默认 `full_produce_setup_mixed` 均衡混合两种模式：给定支援/回忆后培育，或由模型先选六支援、
        最多四回忆再培育。初始每批10局由环境安排五偶像×两模式各1局；调大批次后继续按种子轮转，模型不能只挑某个偶像训练。
        自选阶段使用包内明确的研究候选池，回忆按携带卡、卡片变体、HIF能力和金因子分别选择组成，
        不代表个人拥有库存或保证实机可生成；最终候选以配套 ZIP 的配置和预检报告为准。
        可切换仅自选 `full_produce_select`、五偶像给定编成 `full_produce_mixed`、固定编成
        `full_produce` 或独立单场冲分 `exam_score`。所有完整培育都从开局运行到真实终止。
        本机验收不等于已经在你的 Colab GPU 上跑过；下面的检查会在当前运行时实际执行。
        """), cell("code", """
        # 1. 检查 GPU，挂载 Google Drive（长训必需）
        import os, sys, json, hashlib, subprocess, datetime, shutil, tempfile, re
        from pathlib import Path
        if sys.version_info < (3, 11):
            raise RuntimeError(f"需要 Python >= 3.11；当前为 {sys.version}")
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("请先在 Colab 的运行时设置中选择 GPU，再重新运行。")
        INHERITED_TORCH = {"version": torch.__version__, "cuda": torch.version.cuda}
        print("GPU:", torch.cuda.get_device_name(0), "PyTorch:", INHERITED_TORCH)
        from google.colab import drive
        drive.mount("/content/drive")
        if not Path("/content/drive/MyDrive").is_dir():
            raise RuntimeError("Drive 尚未挂载成功，不能开始长时间训练。")
        """), cell("code", """
        # 2. 上传配套 ZIP；也可以提前将 ZIP 放入自己的 Drive
        BUNDLE_SOURCE = "upload"  # @param ["upload", "drive"]
        DRIVE_ZIP_PATH = "/content/drive/MyDrive/gakumas-colab-training.zip"  # @param {type:"string"}
        EXPECTED_MANIFEST_SHA256 = ""  # @param {type:"string"}
        # 可选：填入交付说明中的 manifest SHA256；空白时仍逐文件校验包内清单。
        if BUNDLE_SOURCE == "upload":
            from google.colab import files
            uploaded = files.upload()
            if len(uploaded) != 1:
                raise ValueError("请只上传一个配套的 .zip 文件。")
            name, content = next(iter(uploaded.items()))
            if not name.lower().endswith(".zip"):
                raise ValueError("需要上传 .zip 文件。")
            ZIP_PATH = Path(tempfile.mkdtemp(prefix="hif-upload-", dir="/content")) / "bundle.zip"
            ZIP_PATH.write_bytes(content)
            del uploaded, content
        elif BUNDLE_SOURCE == "drive":
            ZIP_PATH = Path(DRIVE_ZIP_PATH).expanduser().resolve()
            if not ZIP_PATH.is_file() or ZIP_PATH.suffix.lower() != ".zip":
                raise FileNotFoundError(ZIP_PATH)
        else:
            raise ValueError("BUNDLE_SOURCE 必须为 upload 或 drive。")
        print("ZIP:", ZIP_PATH)
        """), cell("markdown", """
        ## 校验、解压和安装

        先检查完整文件集合、大小和 SHA256，拒绝额外文件、路径穿越、重复路径和链接，再执行包内程序。
        解压到新的本地目录，训练进度单独保存在 Drive。独立 venv 继承 Colab 现有 GPU PyTorch，安装过程
        不安装或升级 PyTorch/CUDA。缺少 Node.js 20+ 时，从
        [Node.js 官方固定版本](https://nodejs.org/en/blog/release/v22.22.0) 下载并核对固定 SHA256。
        """), cell("code", (HERE / "bootstrap.py").read_text(encoding="utf-8") + """

# 3. 全部校验通过后才解压；此单元格不执行 ZIP 中的代码
BUNDLE_ROOT, BUNDLE_MANIFEST, MANIFEST_SHA256 = extract_verified_bundle(
    ZIP_PATH, "/content", EXPECTED_MANIFEST_SHA256)
print("已验证文件:", len(BUNDLE_MANIFEST["files"]))
print("manifest SHA256:", MANIFEST_SHA256)
print("工作目录:", BUNDLE_ROOT)
"""), cell("code", """
        # 4. 建立独立运行环境，保留 Colab GPU PyTorch
        import platform, tarfile, urllib.request
        node_bin = shutil.which("node")
        node_version = subprocess.check_output([node_bin, "--version"], text=True).strip() if node_bin else ""
        matched = re.fullmatch(r"v(\\d+)\\.(\\d+)\\.(\\d+)", node_version)
        if not matched or int(matched[1]) < 20:
            if platform.system() != "Linux":
                raise RuntimeError("自动 Node 安装仅支持 Linux。")
            arch = {"x86_64": "x64", "aarch64": "arm64"}.get(platform.machine())
            if arch is None:
                raise RuntimeError(f"不支持的 Node 架构：{platform.machine()}")
            release = "v22.22.0"
            basename = f"node-{release}-linux-{arch}"
            filename = basename + ".tar.xz"
            # 来自上述官方发布页的 SHASUMS；固定版本和哈希同时更新。
            pinned_hashes = {
                "x64": "9aa8e9d2298ab68c600bd6fb86a6c13bce11a4eca1ba9b39d79fa021755d7c37",
                "arm64": "1bf1eb9ee63ffc4e5d324c0b9b62cf4a289f44332dfef9607cea1a0d9596ba6f",
            }
            node_dir = Path(tempfile.mkdtemp(prefix="hif-node-", dir="/content"))
            archive_path = node_dir / filename
            with urllib.request.urlopen(f"https://nodejs.org/dist/{release}/{filename}", timeout=60) as src, archive_path.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != pinned_hashes[arch]:
                raise RuntimeError("Node 官方二进制 SHA256 不符。")
            with tarfile.open(archive_path, "r:xz") as archive:
                member = archive.getmember(basename + "/bin/node")
                if not member.isfile():
                    raise RuntimeError("Node 二进制不是普通文件。")
                with archive.extractfile(member) as src, (node_dir / "node").open("xb") as dst:
                    shutil.copyfileobj(src, dst)
            (node_dir / "node").chmod(0o755)
            os.environ["PATH"] = str(node_dir) + os.pathsep + os.environ["PATH"]
        print("Node:", subprocess.check_output(["node", "--version"], text=True).strip())
        VENV_DIR = Path(tempfile.mkdtemp(prefix="hif-venv-", dir="/content"))
        # Colab may omit ensurepip; its existing pip can install into this venv.
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(VENV_DIR)], check=True)
        RUN_PYTHON = VENV_DIR / "bin" / "python"
        PIP_COMMAND = [sys.executable, "-m", "pip", "--python", str(RUN_PYTHON)]
        # 仅安装非 Torch 依赖；两个本地工程使用 --no-deps，不能替换 CUDA 栈。
        subprocess.run(PIP_COMMAND + ["install", "--disable-pip-version-check",
                        "gymnasium>=0.29", "numpy>=1.26", "pyyaml>=6.0", "orjson>=3.9", "pydantic>=2.6", "psutil>=5.9"], check=True)
        subprocess.run(PIP_COMMAND + ["install", "--disable-pip-version-check", "--no-deps",
                        "-e", str(BUNDLE_ROOT / "arena"), "-e", str(BUNDLE_ROOT / "training")], check=True)
        probe = "import json,torch; print(json.dumps({'version':torch.__version__,'cuda':torch.version.cuda,'available':torch.cuda.is_available()}))"
        inherited = json.loads(subprocess.check_output([str(RUN_PYTHON), "-c", probe], text=True))
        if {k: inherited[k] for k in ("version", "cuda")} != INHERITED_TORCH or not inherited["available"]:
            raise RuntimeError(f"独立环境没有保留原 GPU PyTorch：{inherited}")
        ENV = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
        print("运行环境:", RUN_PYTHON, inherited)
        """), cell("code", """
        # 5. 训练设置：同一 RUN_NAME 自动恢复；换任务时请使用另一个名称
        CONFIG_NAME = "full_produce_setup_mixed"  # @param ["full_produce_setup_mixed", "full_produce_select", "full_produce_mixed", "full_produce", "exam_score"]
        # setup_mixed 均衡两模式；select 只训练自选；full_produce_mixed 只训练给定编成。
        TASK = "exam_score" if CONFIG_NAME == "exam_score" else "full_produce"
        RUN_NAME = "hif-setup-mixed-v4"  # @param {type:"string"}
        MIGRATE_FROM_RUN = ""  # @param {type:"string"}
        # 从旧包升级时填旧 RUN_NAME（如 hif-setup-mixed-v2），目标 RUN_NAME 必须不同。
        # 复制最近完整检查点，保留模型/优化器/词表/种子进度/日志/累计时间；旧运行不改动。
        WORKERS = "auto"  # @param {type:"string"}
        PPO_MICROBATCH = "auto"  # @param {type:"string"}
        # 输入 auto 或正整数：worker 和 microbatch 均无应用层固定上限。
        # 这是封存的初始配置；运行中修改下面第8格，无需改这里或换运行名称。
        TOTAL_HOURS = 24  # @param {type:"number"}
        SESSION_HOURS = 8  # @param {type:"number"}
        PERSISTENT_ROOT = "/content/drive/MyDrive/gakumas-runs"  # @param {type:"string"}
        LOCAL_ROOT = "/content/gakumas-runs"  # @param {type:"string"}
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", RUN_NAME):
            raise ValueError("RUN_NAME 只能使用字母、数字、下划线、点和连字符，最多80字符。")
        if MIGRATE_FROM_RUN and (MIGRATE_FROM_RUN == RUN_NAME or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", MIGRATE_FROM_RUN)):
            raise ValueError("迁移源必须是合法且不同的旧 RUN_NAME。")
        if not (0 < TOTAL_HOURS and 0 < SESSION_HOURS <= TOTAL_HOURS):
            raise ValueError("时间预算必须为正，SESSION_HOURS 不能大于 TOTAL_HOURS。")
        drive_base = Path("/content/drive/MyDrive").resolve()
        persistent = Path(PERSISTENT_ROOT).expanduser().resolve()
        if not persistent.is_relative_to(drive_base):
            raise ValueError("长训输出必须位于已挂载的 MyDrive 中。")
        if CONFIG_NAME not in {"full_produce", "full_produce_mixed", "full_produce_select", "full_produce_setup_mixed", "exam_score"}:
            raise ValueError("未知训练配置。")
        CONFIG_PATH = BUNDLE_ROOT / "configs" / f"{CONFIG_NAME}.json"
        if not CONFIG_PATH.is_file():
            raise FileNotFoundError("此 ZIP 尚未包含所选配置或已确认的研究候选池；请使用配套完整交付包。")
        selected_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if selected_config.get("task") != TASK:
            raise ValueError("配置与任务不一致。")
        sys.path.insert(0, str(BUNDLE_ROOT / "colab"))
        from performance import hardware_profile, prepare_config
        CONFIG_PATH = Path(tempfile.mkdtemp(prefix="hif-effective-config-", dir="/content")) / "config.json"
        PERFORMANCE = prepare_config(selected_config, manifest_sha256=MANIFEST_SHA256,
            run_name=RUN_NAME, persistent_root=persistent, output=CONFIG_PATH,
            hardware=hardware_profile(), workers=WORKERS, microbatch_size=PPO_MICROBATCH)
        selected_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        print("封存的初始配置（恢复复用；热控制另存，不改变运行身份）:", json.dumps(PERFORMANCE, ensure_ascii=False))
        config_display = json.loads(json.dumps(selected_config))
        inventory = config_display.get("task_config", {}).get("setup_inventory")
        if inventory is not None:
            config_display["task_config"]["setup_inventory"] = {
                "schema_version": inventory.get("schema_version"),
                "support_candidates": len(inventory.get("supports", [])),
                "fixed_memory_candidates": len(inventory.get("memories", [])),
                "memory_components": {name: len(options) for name, options in inventory.get("memory_components", {}).items()},
                "full_definition": "configs/research_inventory.json and embedded training config",
                "provenance": inventory.get("provenance")}
        print("固定配置摘要（恢复时保持一致，完整候选见包内配置）:")
        print(json.dumps(config_display, ensure_ascii=False, indent=2))
        print("Drive运行目录:", persistent / RUN_NAME)
        """), cell("markdown", """
        ## 当前运行时检查

        建议选择 Python 3、A100 GPU、High-RAM、Latest；本包使用 CUDA，TPU 不能直接替换。
        High-RAM 增加系统内存。首次自动模式按可用核数设置独立环境进程；6核以上为主进程留2核，
        小CPU配额按可用核数限制。GPU微批次按显存给出起点（约16GB为2，24GB为4，40GB为8，
        80GB为16），再由预检实测。A100 80GB、12核自动采用10个worker和microbatch 16。
        这些不是各硬件的实测速率排名。环境进程只模拟；词表、模型和GPU批量推理由主进程负责。
        初始参数保存在Drive并在续训时复用。首次也可手填正整数；若初始micro超过minibatch，
        minibatch会同时提高到micro并打印有效配置。运行中可在第8格调整四个执行参数，
        请求与实际生效值显示在第7格。规模无应用层固定上限，实际速度和内存是否足够需看本次运行。

        下一格首次用实际 Arena 各跑一个单场考试和一个完整任务 episode，检查所有遇到的决策能编码，
        并在当前 GPU 上进行真实前向和反向传播。多偶像配置按预检清单检查各偶像及配置模式；
        自选模式还检查实际配置动作。预检只覆盖实际执行路径，不代表所有支援/回忆组合都已穷举。
        启动批量探针最多32图并会在CUDA激活OOM时缩小，报告列出实际测过的批量；
        运行中更大的批次另有OOM退档，预检不会替所有未来状态保证容量。
        完整培育可能正常失败；检查通过不代表已经学会通关。
        检查使用独立临时模型和诊断目录，不会修改训练权重或恢复位置。
        续训默认复用同一运行目录中已通过的完整报告：训练包、配置、Python/Node/PyTorch/CUDA版本、
        GPU型号与总显存须一致。每次仍在独立训练环境中做一次小型CUDA前后向检查。
        找不到匹配报告时自动做完整检查；勾选 FORCE_PREFLIGHT 可主动重跑。
        """), cell("code", """
        # 6. 首次完整检查，续训自动复用已通过报告；每次仅保留快速 CUDA 检查
        FORCE_PREFLIGHT = False  # @param {type:"boolean"}
        PREFLIGHT = None  # 本格失败时不能沿用上一次的通过状态。
        if "TRAINING_SESSION" in globals() and TRAINING_SESSION.status().get("running"):
            raise RuntimeError("训练仍在运行，无需重做预检；调参请使用第8格。")
        sys.path.insert(0, str(BUNDLE_ROOT / "colab"))
        from process_utils import run_logged as _run_logged
        def run_logged(command, logfile):
            return _run_logged(command, logfile, cwd=BUNDLE_ROOT, env=ENV)
        STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f-UTC")
        DIAGNOSTICS = persistent / "_session_diagnostics" / RUN_NAME / STAMP
        DIAGNOSTICS.mkdir(parents=True, exist_ok=False)
        PREFLIGHT_PATH = DIAGNOSTICS / "preflight.json"
        CONFIG_SHA256 = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
        probe_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if probe_config.get("task") != "full_produce":
            probe_config = json.loads((BUNDLE_ROOT / "configs" / "full_produce.json").read_text(encoding="utf-8"))
        probe_task_config = probe_config.get("task_config", {})
        probe_profiles = probe_task_config.get("loadout_pool") or [{"name": None}]
        probe_mode = probe_task_config.get("setup_mode", "given")
        probe_modes = ("given", "select") if probe_mode == "mixed" else (probe_mode,)
        expected_produce_probes = {(profile["name"], mode) for profile in probe_profiles for mode in probe_modes}
        # 子进程退出即释放探针的GPU内存，不启动Arena、不加载训练权重。
        quick_probe = "\\n".join([
            "import sys,json,torch",
            "from pathlib import Path",
            "sys.path.insert(0, str(Path(sys.argv[1]) / 'colab'))",
            "from preflight import runtime_probe",
            "runtime = runtime_probe('cuda')",
            "x = torch.ones((64,64), device='cuda', requires_grad=True)",
            "loss = (x @ x).square().mean()",
            "loss.backward()",
            "assert torch.isfinite(loss).item() and torch.isfinite(x.grad).all().item()",
            "torch.cuda.synchronize()",
            "print(json.dumps({'runtime': runtime, 'cuda_smoke_passed': True}))",
        ])
        QUICK_CHECK = json.loads(subprocess.check_output(
            [str(RUN_PYTHON), "-B", "-c", quick_probe, str(BUNDLE_ROOT)],
            cwd=BUNDLE_ROOT, env=ENV, text=True))
        if QUICK_CHECK.get("cuda_smoke_passed") is not True:
            raise RuntimeError("当前运行环境的快速 CUDA 检查未通过。")
        (DIAGNOSTICS / "runtime-check.json").write_text(
            json.dumps(QUICK_CHECK, ensure_ascii=False, indent=2), encoding="utf-8")
        def matching_preflight(report):
            tasks = report.get("tasks", []) if isinstance(report, dict) else []
            complete_tasks = (isinstance(tasks, list) and all(isinstance(row, dict) for row in tasks)
                and len(tasks) == 1 + len(expected_produce_probes)
                and sum(row.get("task") == "exam_score" for row in tasks) == 1
                and all((row.get("loadout_profile") is None or isinstance(row.get("loadout_profile"), str))
                        and isinstance(row.get("setup_mode"), str)
                        for row in tasks if row.get("task") == "full_produce")
                and {(row.get("loadout_profile"), row.get("setup_mode"))
                     for row in tasks if row.get("task") == "full_produce"} == expected_produce_probes)
            return (isinstance(report, dict)
                    and report.get("schema") == "hif-colab-preflight/1"
                    and report.get("passed") is True
                    and report.get("manifest_sha256") == MANIFEST_SHA256
                    and report.get("selected_config_sha256") == CONFIG_SHA256
                    and report.get("runtime") == QUICK_CHECK["runtime"]
                    and complete_tasks)
        external_data_override = any(ENV.get(name) for name in (
            "GAKUMAS_RL_ROOT_DIR", "GAKUMAS_RL_ASSETS_DIR", "GAKUMAS_MASTERDATA_DIR"))
        if not FORCE_PREFLIGHT and not external_data_override:
            previous_reports = sorted(DIAGNOSTICS.parent.glob("*/preflight.json"), reverse=True)
            for previous_path in previous_reports:
                if previous_path == PREFLIGHT_PATH:
                    continue
                try:
                    previous_bytes = previous_path.read_bytes()
                    previous = json.loads(previous_bytes)
                except (OSError, ValueError):
                    continue  # 写入中断的报告不能作为通过记录。
                if not matching_preflight(previous) or previous.get("cache_reused"):
                    continue
                previous.update(cache_reused=True,
                    scope="Reused matching prior full preflight; only CUDA smoke executed this session",
                    reused_from=str(previous_path),
                    reused_report_sha256=hashlib.sha256(previous_bytes).hexdigest())
                PREFLIGHT_PATH.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
                PREFLIGHT = previous
                print("快速 CUDA 检查通过，跳过重复培育预检；复用:", previous_path)
                break
        if PREFLIGHT is None:
            print("执行完整 preflight：已要求重跑、使用外部数据，或没有匹配的通过记录。")
            run_logged([str(RUN_PYTHON), "-B", str(BUNDLE_ROOT / "colab" / "preflight.py"),
                        "--bundle-root", str(BUNDLE_ROOT), "--config", str(CONFIG_PATH),
                        "--device", "cuda", "--output", str(PREFLIGHT_PATH)],
                       DIAGNOSTICS / "preflight.log")
            report = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
            if not matching_preflight(report):
                raise RuntimeError("当前训练包、配置或运行环境尚未通过完整检查。")
            PREFLIGHT = report
            print("完整检查通过，报告已存入 Drive:", PREFLIGHT_PATH)
        """), cell("markdown", """
        ## 开始或恢复训练

        下一格会真正开始训练。每完成一次更新，脚本将日志、模型、优化器、词表、随机状态和采样进度
        同步到 Drive 的完整检查点版本，校验后才把它标记为可恢复。再次执行同一运行名称时自动恢复。
        首次训练前先做一次固定留出种子的基线评估；之后按配置定期复评，用相同偶像、模式、留出种子的
        前后分数判断提升。自选模式的评估同时包含配置与培育决策；给定模式的支援/回忆保持指定输入。

        配置阶段通过更强熵奖励探索（系数0.05，普通决策0.01），始终从策略分布采样并保存准确概率。
        配置动作与培育动作共享最终评价回报；不增加中途奖励，也不保证24小时足以学会复杂配置组合。

        从旧包升级：第5格 `MIGRATE_FROM_RUN` 填旧运行名称，`RUN_NAME` 使用新的名称。第7格会验证
        并复制旧运行最近完整检查点，保留学习状态、日志和累计时间。允许worker、每批局数、minibatch与microbatch变化；
        网络、编码、引擎、编成、奖励和其他PPO参数必须相同。更换批次布局后不承诺轨迹逐位一致。
        复制后旧目录保留；重复运行同一迁移设置会继续新运行，不会反复复制覆盖进度。

        第7格在后台启动训练后立即返回，不占住Notebook kernel；同一Notebook拒绝重复启动。
        训练期间可直接运行第8格改参数、第9格请求安全停止、第10格看曲线，无需另开终端。
        第8格可反复提交同一组参数；每次提交都有独立请求ID。CUDA激活OOM会缩小micro重算
        当前优化器minibatch，已完成的优化器步骤不重复；推理OOM会拆分前向后统一采样。
        单图或优化器自身OOM、系统RAM不足仍可能停止，恢复使用最近完整检查点。
        日志界面保留最近200行，完整内容仍写入Drive的training-console.log。
        第7格另起一个轻量资源记录进程，每15秒向同一诊断目录写resources.jsonl，记录主进程、
        worker与系统内存、GPU状态、阶段和时间（文件名含唯一后缀）。它不导入模型，也不改变训练参数。
        训练进程被杀后，观察器会尽量记录进程消失；整台VM被回收时只能保留已经写入Drive的记录。
        断线后可以使用独立HIF_Debug.ipynb读取这些文件，不依赖旧kernel变量，也无需重跑训练。

        同一个 `RUN_NAME` 不要在两个 Colab 会话同时运行。保持同一 ZIP、任务和基础配置；改变编成或模型
        结构应新建运行名称。`TOTAL_HOURS` 是这个运行的累计预算，`SESSION_HOURS` 限制本次会话。
        正常到时会在一次完整更新之后保存并退出，因此可能稍超预算。突然断开可能丢失尚未保存的那次更新。

        如需平稳停止，在 Drive 的运行目录新建一个名为 `STOP` 的空文件。程序会在安全边界结束；
        确认停止后删除该文件，下次仍可使用原名称继续。不包含模拟点击或绕过 Colab 会话限制的代码。
        """), cell("code", dedent("""
        # 7. 后台开始 / 自动恢复；本格立即返回，下面可实时调参
        if (not PREFLIGHT or not PREFLIGHT.get("passed") or not Path("/content/drive/MyDrive").is_dir()
                or PREFLIGHT.get("manifest_sha256") != MANIFEST_SHA256
                or PREFLIGHT.get("selected_config_sha256") != hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()):
            raise RuntimeError("必须先通过检查并挂载 Drive。")
        command = [str(RUN_PYTHON), "-u", str(BUNDLE_ROOT / "colab" / "run_training.py"),
                   "--bundle-root", str(BUNDLE_ROOT), "--config", str(CONFIG_PATH), "--task", TASK,
                   "--run-name", RUN_NAME, "--local-root", LOCAL_ROOT,
                   "--persistent-root", PERSISTENT_ROOT,
                   "--total-hours", str(TOTAL_HOURS), "--session-hours", str(SESSION_HOURS)]
        if MIGRATE_FROM_RUN:
            command += ["--migrate-from-run", MIGRATE_FROM_RUN]
        from notebook_session import start_session, write_runtime_control
        TRAINING_SESSION = start_session(command, DIAGNOSTICS / "training-console.log",
            cwd=BUNDLE_ROOT, env=ENV, persistent_run=Path(PERSISTENT_ROOT) / RUN_NAME)
        print("训练已启动，本格无需保持忙碌；可运行下面控制格。", TRAINING_SESSION.status())
        """) + "\nRESOURCE_WATCH_SOURCE = " + repr((HERE / "resource_watch.py").read_text(encoding="utf-8")) + "\n" + dedent("""
        # 观察器源文件写到包外临时目录，保留原ZIP的校验和与训练身份。
        try:
            WATCH_DIR = Path(tempfile.mkdtemp(prefix="hif-resource-watch-", dir="/content"))
            WATCH_SCRIPT = WATCH_DIR / "resource_watch.py"
            WATCH_SCRIPT.write_text(RESOURCE_WATCH_SOURCE, encoding="utf-8")
            WATCH_PID = TRAINING_SESSION.process.pid
            WATCH_CREATE_TIME = subprocess.check_output([str(RUN_PYTHON), "-c",
                "import psutil,sys; print(psutil.Process(int(sys.argv[1])).create_time())", str(WATCH_PID)],
                env=ENV, text=True, timeout=15).strip()
            WATCH_STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            RESOURCE_LOG_PATH = DIAGNOSTICS / ("resources-" + WATCH_STAMP + "-" + WATCH_DIR.name + ".jsonl")
            with (WATCH_DIR / "observer-console.log").open("ab") as watch_console:
                RESOURCE_WATCH_PROCESS = subprocess.Popen([str(RUN_PYTHON), "-u", str(WATCH_SCRIPT),
                    "--pid", str(WATCH_PID), "--create-time", WATCH_CREATE_TIME,
                    "--output", str(RESOURCE_LOG_PATH), "--local-output", str(WATCH_DIR / "resources.jsonl"),
                    "--status-path", str(Path(PERSISTENT_ROOT) / "_runtime_controls" / (RUN_NAME + ".status.json")),
                    "--interval", "15"], env=ENV, stdout=watch_console, stderr=subprocess.STDOUT,
                    start_new_session=(os.name != "nt"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            print("资源历史将写入:", RESOURCE_LOG_PATH)
            print("观察器本地日志:", WATCH_DIR / "observer-console.log")
        except Exception as error:
            print("训练已经启动，但资源记录器启动失败:", repr(error))
        """)), cell("code", """
        # 8. 运行中调参：改下面4项并运行本格；无需重启、换包或换 RUN_NAME
        LIVE_WORKERS = 12  # @param {type:"integer"}
        LIVE_EPISODES_PER_UPDATE = 40  # @param {type:"integer"}
        LIVE_MINIBATCH_SIZE = 128  # @param {type:"integer"}
        LIVE_MICROBATCH_SIZE = 32  # @param {type:"integer"}
        # 这些是可试的起点；只有运行本格才提交。四项均为正整数，无固定上限，micro不得超过mini。
        # 请求在下一采集/更新安全边界生效；第7格会显示请求值、实际值、等待和错误。
        from notebook_session import write_runtime_control
        CONTROL_PATH = write_runtime_control(Path(PERSISTENT_ROOT) / RUN_NAME,
            workers=LIVE_WORKERS, episodes_per_update=LIVE_EPISODES_PER_UPDATE,
            minibatch_size=LIVE_MINIBATCH_SIZE, microbatch_size=LIVE_MICROBATCH_SIZE)
        print("已提交参数请求，控制文件:", CONTROL_PATH)
        if "TRAINING_SESSION" in globals():
            TRAINING_SESSION.refresh()
        """), cell("code", """
        # 9. 安全停止：勾选后运行本格，等待当前安全边界保存；默认仅查看状态
        REQUEST_SAFE_STOP = False  # @param {type:"boolean"}
        if "TRAINING_SESSION" not in globals():
            raise RuntimeError("请先运行第7格启动本Notebook拥有的训练会话。")
        if REQUEST_SAFE_STOP:
            print("已创建STOP:", TRAINING_SESSION.request_stop())
        print(TRAINING_SESSION.refresh())
        # 进程退出后，确认状态running=False，再删除运行目录中的STOP即可使用同名继续。
        # 紧急中止仅作用于此Notebook拥有的进程：TRAINING_SESSION.terminate_owned()
        """), cell("code", """
        # 10. 查看已保存的进度与曲线（不要把采样均分当作独立评估成绩）
        import matplotlib.pyplot as plt
        sys.path.insert(0, str(BUNDLE_ROOT / "colab"))
        from persistence import SnapshotStore, safe_child, file_hash
        run_dir = Path(PERSISTENT_ROOT) / RUN_NAME
        identity_path = run_dir / "run-identity.json"
        metrics_by_namespace = {}
        if identity_path.is_file() and (run_dir / "snapshots").is_dir():
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            store = SnapshotStore(PERSISTENT_ROOT, RUN_NAME, identity)
            # 复用恢复校验寻找完整快照；绘图只读取并校验对应的 metrics 日志块。
            latest = store.latest(validate_logs=False)
            if latest:
                print("最近保存的 PPO 轮数:", latest["state"]["iteration"], "快照版本:", latest["manifest"]["generation"])
                print(json.dumps(latest["state"], ensure_ascii=False, indent=2)[:6000])
                for namespace in ("training", "evaluation"):
                    log = latest["manifest"].get("logs", {}).get(namespace + "/metrics.jsonl")
                    if not log:
                        continue
                    chunks = []
                    for chunk in log["chunks"]:
                        path = safe_child(run_dir, chunk["path"])
                        if path.stat().st_size != chunk["size"] or file_hash(path) != chunk["sha256"]:
                            raise ValueError(f"指标日志块校验失败：{path}")
                        chunks.append(path.read_bytes())
                    content = b"".join(chunks)
                    if len(content) != log["size"]:
                        raise ValueError("指标日志块长度不一致。")
                    metrics_by_namespace[namespace] = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
        if metrics_by_namespace:
            evaluation = metrics_by_namespace.get("evaluation", [])
            baselines = [row for row in evaluation if row.get("iteration") == 0]
            if baselines and evaluation:
                from IPython.display import display, Markdown
                baseline, latest_evaluation = baselines[0], evaluation[-1]
                def score_groups(metric):
                    groups = {}
                    for profile, data in (metric.get("loadout_profiles") or {"fixed": metric}).items():
                        modes = data.get("setup_modes")
                        if modes:
                            groups.update({profile + " / " + mode: value for mode, value in modes.items()})
                        else:
                            groups[profile] = data
                    return groups
                baseline_groups = score_groups(baseline)
                latest_groups = score_groups(latest_evaluation)
                rows = ["| 偶像 / 模式 | 开训前均分 | 最近评估均分 | 相对基线变化 |", "|---|---:|---:|---:|"]
                for name in sorted(set(baseline_groups) | set(latest_groups)):
                    before = baseline_groups.get(name, {}).get("raw_score_mean")
                    after = latest_groups.get(name, {}).get("raw_score_mean")
                    delta = after - before if before is not None and after is not None else None
                    values = [f"{value:,.1f}" if value is not None else "未记录" for value in (before, after)]
                    change = f"{delta:+,.1f}" if delta is not None else "未记录"
                    rows.append(f"| {name} | {values[0]} | {values[1]} | {change} |")
                display(Markdown(chr(10).join(rows)))
                print("仅比较相同偶像、模式和留出种子的前后分数；select 的变化包含配置能力与培育能力。")
                if latest_evaluation.get("iteration") == 0:
                    print("目前只有开训前基线，等待首次定期复评后再判断提升。")
            elif evaluation:
                print("当前保存记录中没有开训前基线，不能据此计算相对初始策略的提升。")
            plot_groups = []
            for namespace, metrics in metrics_by_namespace.items():
                modes = sorted({mode for row in metrics for mode in row.get("setup_modes", {})}) or [None]
                plot_groups.extend((namespace, mode, metrics) for mode in modes)
            fig, axes = plt.subplots(len(plot_groups), 1, figsize=(11, 3.5 * len(plot_groups)), squeeze=False)
            for axis, (namespace, mode, metrics) in zip(axes.flat, plot_groups):
                x = [row["iteration"] for row in metrics]
                totals = [row.get("setup_modes", {}).get(mode, {}) if mode else row for row in metrics]
                axis.plot(x, [row.get("raw_score_mean", float("nan")) for row in totals], label="all profiles", linewidth=2)
                profiles = sorted({name for row in metrics for name in row.get("loadout_profiles", {})})
                for name in profiles:
                    values = [row.get("loadout_profiles", {}).get(name, {}) for row in metrics]
                    if mode:
                        values = [row.get("setup_modes", {}).get(mode, {}) for row in values]
                    axis.plot(x, [row.get("raw_score_mean", float("nan")) for row in values], label=name, alpha=.75)
                axis.set(title=f"{namespace} / {mode or 'fixed'}: raw final score", xlabel="PPO update")
                axis.grid(alpha=.25); axis.legend()
            plt.tight_layout(); plt.show()
            print("training 为采样策略成绩；evaluation 为固定留出种子的贪心评估。")
            training_metrics = metrics_by_namespace.get("training", [])
            kinds = sorted({kind for row in training_metrics for kind in row.get("ppo", {}).get("decision_kinds", {})})
            if kinds:
                fig, axes = plt.subplots(2, 1, figsize=(11, 7), squeeze=False)
                for kind in kinds:
                    values = [row.get("ppo", {}).get("decision_kinds", {}).get(kind, {}) for row in training_metrics]
                    x = [row["iteration"] for row in training_metrics]
                    axes[0, 0].plot(x, [row.get("normalized_entropy", float("nan")) for row in values], label=kind)
                    axes[1, 0].plot(x, [row.get("approx_kl", float("nan")) for row in values], label=kind)
                axes[0, 0].set(title="Exploration by decision kind: H / log(legal candidates)", ylabel="normalized entropy")
                axes[1, 0].set(title="Sample approximate KL by decision kind", xlabel="PPO update")
                for axis in axes.flat:
                    axis.grid(alpha=.25); axis.legend()
                plt.tight_layout(); plt.show()
                print("熵接近1表示更均匀，接近0表示更确定。KL是优化过程的采样近似；这些指标不能单独证明分数提高。")
                print("最近决策诊断（含候选数、唯一采样数、优化观测数）:")
                print(json.dumps(training_metrics[-1].get("ppo", {}).get("decision_kinds", {}), ensure_ascii=False, indent=2))
            if training_metrics:
                print("最近训练批次配置组件选择频数（按配置决策种类分开）:")
                print(json.dumps(training_metrics[-1].get("setup_selection_counts", {}), ensure_ascii=False, indent=2))
                print("最近训练批次最终装备频数（按given/select分开，次数不等于优劣排名）:")
                print(json.dumps(training_metrics[-1].get("equipped_inventory_counts", {}), ensure_ascii=False, indent=2))
                print("每局具体回忆卡片/定制/能力组合保存在episodes.jsonl的metadata.selected_memory_specs。")
        else:
            print("尚无完整保存的更新，请先查看第7格日志。")
        """), cell("markdown", """
        ## 下一次会话

        再次选择 GPU，从第1格开始顺序运行，提供相同 ZIP，保持 `RUN_NAME`、`TASK` 和配置一致。
        第7格会读取 Drive 最近的有效完整版本继续训练；若累计预算已用完，可增加 `TOTAL_HOURS`。
        不要让两个会话同时写入同一个运行目录。若存在 STOP 文件，确认上一会话已停止后删除它再继续。

        worker 可填任意正整数；实际数量以第7格生效状态及训练日志为准，较大数字不保证更快。
        热控制文件保存在Drive的`_runtime_controls`目录，基础身份配置仍保持封存。
        given 配置用于给定编成；select 从明确研究池选择支援和回忆；
        setup_mixed 让同一个模型均衡训练这两种能力。候选池最终范围以配套配置和验收记录为准，
        不代表全部组合已覆盖，也不保证未见偶像或组合的泛化。较大训练预算不能替代覆盖和留出评估；
        详细目标、提前失败评价映射与能力边界保留在 ZIP 中的 `training/README.md` 和 `training/ACCEPTANCE.md`。
        """)]
    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"colab": {"name": "HIF_Training.ipynb", "provenance": []},
                         "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}, "accelerator": "GPU"}, "cells": cells}


def main():
    path = HERE / "HIF_Training.ipynb"
    path.write_text(json.dumps(notebook(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(path)


def diagnostic_notebook():
    reader = (HERE / 'diagnose_run.py').read_text(encoding='utf-8')
    cells = [cell('markdown', '''
        # HIF 断线诊断

        只需挂载保存训练结果的 Google Drive，不需要 GPU、训练 ZIP、venv 或旧 Notebook 变量。
        本 Notebook 不启动、停止或恢复训练，也不修改已有运行目录。运行名称填写断线的那次。
        会读取最新几个训练会话的完整日志末尾、最近提交的状态与评分，以及已有的资源历史。
        元数据会做哈希校验；模型权重只检查是否存在及大小，实际恢复仍由训练入口完整验证。
        原版本没有连续系统内存历史，无法追溯未曾记录的 RAM 峰值。
        '''), cell('code', '''
        from pathlib import Path
        from google.colab import drive
        import json, datetime
        drive.mount('/content/drive')
        RUN_NAME = 'hif-setup-mixed-v4-2'  # @param {type:"string"}
        PERSISTENT_ROOT = '/content/drive/MyDrive/gakumas-runs'  # @param {type:"string"}
        '''), cell('code', 'DIAGNOSTIC_SOURCE = ' + repr(reader) + '\n' + dedent('''
        diagnostic_scope = {'__name__': 'hif_offline_diagnostics'}
        exec(DIAGNOSTIC_SOURCE, diagnostic_scope)
        REPORT = diagnostic_scope['diagnose_run'](PERSISTENT_ROOT, RUN_NAME)
        diagnostic_scope['print_report'](REPORT)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        REPORT_PATH = Path('/content') / f'hif-diagnostics-{RUN_NAME}-{stamp}.json'
        REPORT_PATH.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
        print('完整诊断报告：', REPORT_PATH)
        ''')), cell('code', '''
        # 可选：下载报告后发给我；不要上传checkpoint权重文件。
        from google.colab import files
        files.download(str(REPORT_PATH))
        ''')]
    return {'nbformat': 4, 'nbformat_minor': 5, 'cells': cells,
            'metadata': {'colab': {'name': 'HIF_Debug.ipynb', 'provenance': []},
                         'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                         'language_info': {'name': 'python'}}}


if __name__ == "__main__":
    main()
