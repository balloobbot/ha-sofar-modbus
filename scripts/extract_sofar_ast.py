#!/usr/bin/env python3
"""Extract entity descriptions from the upstream plugin_sofar.py via AST.

Does not import homeassistant. Walks the source, pulls the five top-level
entity-description lists (SENSOR_TYPES, BUTTON_TYPES, NUMBER_TYPES,
SELECT_TYPES, BATTERY_SENSOR_TYPES) into plain Python dicts: literal values
via ast.literal_eval where possible, otherwise the exact source text (for
things like ``SensorDeviceClass.POWER`` or ``HYBRID | PV``) so the generator
can re-emit them unchanged.

Read-only: writes nothing. Run with --dump to pretty-print the result.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

UPSTREAM = Path(
    "/home/darkrain/homeassistant/homeassistant-solax-modbus/custom_components/solax_modbus/plugin_sofar.py"
)

# Bitmask constants copied from plugin_sofar.py's module-level assignments,
# needed to evaluate `allowedtypes=HYBRID | X3 | GEN` into an actual int.
BITMASKS: dict[str, int] = {
    "GEN": 0x0001,
    "GEN2": 0x0002,
    "GEN3": 0x0004,
    "GEN4": 0x0008,
    "X1": 0x0100,
    "X3": 0x0200,
    "PV": 0x0400,
    "AC": 0x0800,
    "HYBRID": 0x1000,
    "MIC": 0x2000,
    "EPS": 0x8000,
    "DCB": 0x10000,
    "PM": 0x20000,
    "MPPT3": 0x40000,
    "MPPT4": 0x80000,
    "MPPT6": 0x100000,
    "MPPT8": 0x200000,
    "MPPT10": 0x400000,
    "BAT_BTS": 0x1000000,
    "ALLDEFAULT": 0,
}
BITMASKS["ALL_GEN_GROUP"] = BITMASKS["GEN2"] | BITMASKS["GEN3"] | BITMASKS["GEN4"] | BITMASKS["GEN"]
BITMASKS["ALL_X_GROUP"] = BITMASKS["X1"] | BITMASKS["X3"]
BITMASKS["ALL_TYPE_GROUP"] = BITMASKS["PV"] | BITMASKS["AC"] | BITMASKS["HYBRID"] | BITMASKS["MIC"]
BITMASKS["ALL_EPS_GROUP"] = BITMASKS["EPS"]
BITMASKS["ALL_DCB_GROUP"] = BITMASKS["DCB"]
BITMASKS["ALL_PM_GROUP"] = BITMASKS["PM"]
BITMASKS["ALL_MPPT_GROUP"] = BITMASKS["MPPT3"] | BITMASKS["MPPT4"] | BITMASKS["MPPT6"] | BITMASKS["MPPT8"] | BITMASKS["MPPT10"]


def eval_bitmask_expr(node: ast.expr) -> int:
    """Evaluate a `HYBRID | X3 | GEN`-shaped expression against BITMASKS."""
    if isinstance(node, ast.Name):
        return BITMASKS[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return eval_bitmask_expr(node.left) | eval_bitmask_expr(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    raise ValueError(f"cannot evaluate bitmask expr: {ast.dump(node)}")


def node_to_value(node: ast.expr) -> dict[str, Any]:
    """Convert one kwarg's AST node to {"kind": ..., ...}.

    kind is one of: "literal" (a plain Python value), "source" (an expression
    we re-emit verbatim, e.g. an enum member), "dict" (an int->str/int map,
    used for scale=), "bitmask" (an evaluated allowedtypes int, with source
    text kept alongside for readability in generated comments).
    """
    try:
        return {"kind": "literal", "value": ast.literal_eval(node)}
    except (ValueError, TypeError):
        pass

    if isinstance(node, ast.Dict):
        try:
            keys = [ast.literal_eval(k) for k in node.keys if k is not None]
            values = [ast.literal_eval(v) for v in node.values]
            return {"kind": "dict", "value": dict(zip(keys, values, strict=True))}
        except (ValueError, TypeError):
            pass

    return {"kind": "source", "value": ast.unparse(node)}


def extract_list(tree: ast.Module, name: str) -> list[dict[str, Any]] | None:
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target
        else:
            continue
        if target.id != name:
            continue

        value = node.value
        if not isinstance(value, ast.List):
            return None

        out: list[dict[str, Any]] = []
        for elt in value.elts:
            if not isinstance(elt, ast.Call):
                continue
            entry: dict[str, Any] = {"_class": ast.unparse(elt.func)}
            for kw in elt.keywords:
                if kw.arg is None:
                    continue
                if kw.arg == "allowedtypes":
                    try:
                        entry[kw.arg] = {
                            "kind": "bitmask",
                            "value": eval_bitmask_expr(kw.value),
                            "source": ast.unparse(kw.value),
                        }
                        continue
                    except (KeyError, ValueError):
                        pass
                entry[kw.arg] = node_to_value(kw.value)
            out.append(entry)
        return out
    return None


def main() -> None:
    text = UPSTREAM.read_text()
    tree = ast.parse(text)

    result = {}
    for name in ("SENSOR_TYPES", "BUTTON_TYPES", "NUMBER_TYPES", "SELECT_TYPES", "BATTERY_SENSOR_TYPES"):
        lst = extract_list(tree, name)
        result[name] = lst
        count = len(lst) if lst is not None else 0
        print(f"{name}: {count} entries", file=sys.stderr)

    out_path = Path(__file__).parent / "_sofar_extracted.json"
    out_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {out_path}", file=sys.stderr)

    if "--dump" in sys.argv:
        json.dump(result, sys.stdout, indent=2, default=str)


if __name__ == "__main__":
    main()
