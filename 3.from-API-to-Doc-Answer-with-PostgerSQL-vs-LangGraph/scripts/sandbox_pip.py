"""pip runner that survives the Windows/DSH sandbox (see sandbox_compat.py).

    python scripts/sandbox_pip.py install -r requirements.txt
    python scripts/sandbox_pip.py --python .venv\\Scripts\\python.exe install pip
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox_compat import patch_mkdtemp  # noqa: E402


def main() -> int:
    patch_mkdtemp()
    from pip._internal.cli.main import main as pip_main

    return pip_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
