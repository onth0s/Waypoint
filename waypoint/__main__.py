"""Entry point. Installed via `python <repo>\waypoint\__main__.py`, so the
project root (where the `waypoint` package lives) must be bootstrapped onto
sys.path before importing it — running a script directly puts only the script's
directory there."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402
from waypoint.cli import main  # noqa: E402

raise SystemExit(main())
