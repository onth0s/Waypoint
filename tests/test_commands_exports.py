from __future__ import annotations

import waypoint.commands


def test_commands_package_has_no_private_exports():
    """waypoint.commands package init must not re-export underscore-prefixed handlers."""
    for attr in dir(waypoint.commands):
        if attr.startswith("__") and attr.endswith("__"):
            continue
        assert not attr.startswith("_"), f"waypoint.commands exposes private name: {attr}"
