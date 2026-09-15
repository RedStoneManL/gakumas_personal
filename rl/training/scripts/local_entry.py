"""Repository-only Windows development bootstrap; never part of package imports.

The fallback reads installed dependencies from an existing environment. Appending
the directory directly deliberately avoids executing .pth files or activating
that environment. No old RL source directory is added or imported.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--extra-site-packages", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    training_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(training_root))
    if options.extra_site_packages is not None:
        dependencies = options.extra_site_packages.resolve(strict=True)
        if not (dependencies / "torch").is_dir():
            raise FileNotFoundError(f"No installed torch dependency in {dependencies}")
        sys.path.append(str(dependencies))
    arguments = options.arguments
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    from gakumas_training.cli import main as cli_main
    cli_main(arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
