"""Entry point for `python -m waypoint`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from waypoint.cli import main

raise SystemExit(main())
