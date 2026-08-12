"""Enforce that custom_components/sofar_modbus/sofar/ never imports homeassistant.

That package is the device library — it must stay HA-free to be mechanically
extractable to its own PyPI package later (a Home Assistant Core requirement
for built-in Modbus integrations). Checked via AST, not import, so it also
catches an import that's merely unreachable at runtime.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOFAR_LIB = Path(__file__).parent.parent.parent / "custom_components" / "sofar_modbus" / "sofar"


def _imported_top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_no_homeassistant_imports() -> None:
    offenders: dict[str, set[str]] = {}
    for path in SOFAR_LIB.rglob("*.py"):
        names = _imported_top_level_names(path)
        bad = {n for n in names if n == "homeassistant"}
        if bad:
            offenders[str(path.relative_to(SOFAR_LIB.parent.parent.parent.parent))] = bad
    assert not offenders, f"sofar/ must stay homeassistant-free: {offenders}"


if __name__ == "__main__":
    test_no_homeassistant_imports()
    print("OK: no homeassistant imports under sofar/")
