from __future__ import annotations

from pathlib import Path

import waypoint.commands


def test_commands_package_has_no_private_exports():
    """waypoint.commands package init must not re-export underscore-prefixed handlers."""
    for attr in dir(waypoint.commands):
        if attr.startswith("__") and attr.endswith("__"):
            continue
        assert not attr.startswith("_"), f"waypoint.commands exposes private name: {attr}"


def test_no_cross_module_private_imports_in_source():
    """Source files in waypoint/ should not import private underscore names from each other."""
    pkg_dir = Path(waypoint.__file__).parent
    for py_file in pkg_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "from waypoint" in line and "import" in line:
                imported_part = line.split("import")[-1]
                imported_names = [n.strip() for n in imported_part.split(",") if n.strip()]
                for name in imported_names:
                    # e.g., "from waypoint.commands.bookmarks import cmd_add"
                    clean_name = name.split()[0]
                    assert not (clean_name.startswith("_") and not clean_name.startswith("__")), (
                        f"{py_file.name} imports private name {clean_name!r}: {line}"
                    )
