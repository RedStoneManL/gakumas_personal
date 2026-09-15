"""Export committed training sources into a new, independently pushable repo."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f'Export requires a new directory: {output}')
    selected = ['rl/ascend', 'rl/training', 'rl/hif-colab/build_bundle.py',
                'rl/hif-colab/build_training_bundle.py']
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip()
    data = subprocess.check_output(['git', 'archive', '--format=tar', revision, '--', *selected], cwd=workspace)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for item in archive:
            if not item.isfile():
                continue
            target = (output / item.name).resolve()
            if not target.is_relative_to(output):
                raise ValueError('Source archive path escaped export root')
            files[item.name] = archive.extractfile(item).read()
    readme = files.get('rl/ascend/REPOSITORY_README.md')
    if not readme or 'rl/hif-colab/build_bundle.py' not in files:
        raise ValueError('Commit the repository README and build scripts before exporting')
    output.mkdir(parents=True)
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (output / 'README.md').write_bytes(readme)
    (output / '.gitattributes').write_bytes(b'* -text\n')
    (output / '.gitignore').write_bytes(b'**/artifacts/\n**/runs/\n**/.venv/\n**/__pycache__/\n*.pyc\n*.pt\n')
    (output / 'SOURCE_EXPORT.json').write_text(json.dumps({'source_commit': revision,
        'source_paths': selected, 'history_policy': 'Arena snapshots and training sources are separate commits'},
        indent=2) + '\n', encoding='utf-8', newline='\n')

    def git(*args):
        return subprocess.run(['git', *args], cwd=output, check=True, capture_output=True, text=True)
    git('init', '--quiet', '--initial-branch=main')
    git('add', '--', '.gitattributes', '.gitignore', 'rl/ascend/arena',
        'rl/ascend/exam_search/runtime/arena', 'rl/ascend/full-arena-import.json')
    identity = ('-c', 'user.name=Codex', '-c', 'user.email=codex@openai.com')
    git(*identity, 'commit', '--quiet', '-m', 'Import the Arena snapshots bound to both training tasks')
    arena_commit = git('rev-parse', 'HEAD').stdout.strip()
    git('add', '--all')
    git(*identity, 'commit', '--quiet', '-m', 'Add portable Ascend training with configurable sampling and learner scale')
    print(json.dumps({'repository': str(output), 'source_commit': revision,
        'arena_commit': arena_commit, 'training_commit': git('rev-parse', 'HEAD').stdout.strip(),
        'source_files': len(files)}, indent=2))


if __name__ == '__main__':
    main()
