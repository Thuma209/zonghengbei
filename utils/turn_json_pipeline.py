import copy
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from Database.db_manager import DatabaseManager
from engine import EconomyEngine
from models.orders import BuildOrder, RefiningOrder, TreatyTrade, TurnInput, UnitOrder
from static.facilities import FACILITY_SPECS
from static.policies import POLICY_ORDER
from static.recipes import RECIPE_SPECS
from static.techs import TECH_SPECS
from static.units import UNIT_TEMPLATES


class PayloadValidationError(Exception):
    def __init__(self, errors: List[str], warnings: List[str] | None = None):
        super().__init__("JSON payload validation failed")
        self.errors = errors
        self.warnings = warnings or []


def _ensure_dict(value: Any, path: str, errors: List[str]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    return value


def _ensure_list(value: Any, path: str, errors: List[str]) -> List[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    return value


def _validate_turn_input(nation: str, data: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    build_orders = _ensure_list(data.get("build_orders", []), f"inputs.{nation}.build_orders", errors)
    for i, item in enumerate(build_orders):
        row = _ensure_dict(item, f"inputs.{nation}.build_orders[{i}]", errors)
        fac = row.get("facility")
        if fac not in FACILITY_SPECS and fac not in ("land_fort", "coastal_fort"):
            errors.append(f"inputs.{nation}.build_orders[{i}].facility invalid: {fac}")

    refining_orders = _ensure_list(data.get("refining_orders", []), f"inputs.{nation}.refining_orders", errors)
    for i, item in enumerate(refining_orders):
        row = _ensure_dict(item, f"inputs.{nation}.refining_orders[{i}]", errors)
        recipe = row.get("recipe")
        if recipe not in RECIPE_SPECS:
            errors.append(f"inputs.{nation}.refining_orders[{i}].recipe invalid: {recipe}")

    unit_orders = _ensure_list(data.get("unit_orders", []), f"inputs.{nation}.unit_orders", errors)
    for i, item in enumerate(unit_orders):
        row = _ensure_dict(item, f"inputs.{nation}.unit_orders[{i}]", errors)
        template = row.get("template")
        year = row.get("year")
        if not isinstance(year, int):
            errors.append(f"inputs.{nation}.unit_orders[{i}].year must be int")
            continue
        if (template, year) not in UNIT_TEMPLATES:
            errors.append(f"inputs.{nation}.unit_orders[{i}] invalid unit template/year: {(template, year)}")

    research = data.get("research")
    if research is not None:
        row = _ensure_dict(research, f"inputs.{nation}.research", errors)
        tech = row.get("tech")
        if tech not in TECH_SPECS:
            errors.append(f"inputs.{nation}.research.tech invalid: {tech}")

    policy_changes = data.get("policy_changes", {})
    if policy_changes is not None:
        row = _ensure_dict(policy_changes, f"inputs.{nation}.policy_changes", errors)
        for category, key in row.items():
            allowed = POLICY_ORDER.get(category)
            if not allowed:
                errors.append(f"inputs.{nation}.policy_changes.{category} invalid category")
                continue
            if key not in allowed:
                errors.append(f"inputs.{nation}.policy_changes.{category} invalid value: {key}")

    treaties = _ensure_list(data.get("treaties", []), f"inputs.{nation}.treaties", errors)
    for i, item in enumerate(treaties):
        row = _ensure_dict(item, f"inputs.{nation}.treaties[{i}]", errors)
        action = row.get("action", "submit")
        kind = row.get("kind", "resource")
        side = row.get("side")

        if action not in ("submit", "cancel"):
            errors.append(f"inputs.{nation}.treaties[{i}].action must be submit/cancel")

        if kind not in ("resource", "military", "loan"):
            errors.append(f"inputs.{nation}.treaties[{i}].kind must be resource/military/loan")

        if action == "cancel":
            if not row.get("agreement_id"):
                errors.append(f"inputs.{nation}.treaties[{i}].agreement_id required for cancel")
            continue

        if side not in ("import", "export"):
            errors.append(f"inputs.{nation}.treaties[{i}].side must be import/export")

        route_safety = row.get("route_safety", 1.0)
        if not isinstance(route_safety, (int, float)) or route_safety < 0 or route_safety > 1:
            errors.append(f"inputs.{nation}.treaties[{i}].route_safety must be between 0 and 1")

        if kind == "resource":
            if not row.get("resource"):
                errors.append(f"inputs.{nation}.treaties[{i}].resource required for resource trade")
            if float(row.get("quantity", 0)) <= 0:
                errors.append(f"inputs.{nation}.treaties[{i}].quantity must be > 0 for resource trade")

        if kind == "military":
            tpl = row.get("unit_template", "")
            year = row.get("unit_year", 0)
            if (tpl, year) not in UNIT_TEMPLATES:
                errors.append(f"inputs.{nation}.treaties[{i}] invalid military unit_template/unit_year")
            if float(row.get("quantity", 0)) <= 0:
                errors.append(f"inputs.{nation}.treaties[{i}].quantity must be > 0 for military trade")

        if kind == "loan":
            if float(row.get("principal", 0)) <= 0:
                errors.append(f"inputs.{nation}.treaties[{i}].principal must be > 0 for loan")
            if float(row.get("interest_rate", 0)) < 0:
                errors.append(f"inputs.{nation}.treaties[{i}].interest_rate must be >= 0")
            if int(row.get("turns", 0)) < 0:
                errors.append(f"inputs.{nation}.treaties[{i}].turns must be >= 0")


def validate_json_payload(payload: Dict[str, Any], nation_codes: List[str]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(payload, dict):
        return ["payload root must be an object"], warnings

    schema_version = payload.get("schema_version", 1)
    if schema_version != 1:
        errors.append(f"unsupported schema_version: {schema_version}")

    inputs = payload.get("inputs")
    inputs = _ensure_dict(inputs, "inputs", errors)

    for nation, one_input in inputs.items():
        if nation not in nation_codes:
            errors.append(f"inputs.{nation} unknown nation code")
            continue
        one = _ensure_dict(one_input, f"inputs.{nation}", errors)
        _validate_turn_input(nation, one, errors, warnings)

    return errors, warnings


def json_to_turn_inputs(payload: Dict[str, Any]) -> Dict[str, TurnInput]:
    out: Dict[str, TurnInput] = {}
    for nation, one in payload.get("inputs", {}).items():
        build_orders = [
            BuildOrder(
                facility=row["facility"],
                quantity=int(row.get("quantity", 1)),
                location=row.get("location", ""),
                level=int(row.get("level", 0)),
            )
            for row in one.get("build_orders", [])
        ]

        refining_orders = [
            RefiningOrder(
                recipe=row["recipe"],
                runs=float(row.get("runs", 1.0)),
                bonus_chromium=float(row.get("bonus_chromium", 0.0)),
            )
            for row in one.get("refining_orders", [])
        ]

        unit_orders = [
            UnitOrder(
                template=row["template"],
                year=int(row["year"]),
                quantity=int(row.get("quantity", 1)),
            )
            for row in one.get("unit_orders", [])
        ]

        research = one.get("research")
        if research is not None:
            research = {
                "tech": research.get("tech"),
            }

        policy_changes = one.get("policy_changes", {}) or {}

        treaties: List[TreatyTrade] = []
        for row in one.get("treaties", []):
            treaties.append(
                TreatyTrade(
                    nation=row.get("nation", nation),
                    partner=row["partner"],
                    side=row["side"],
                    kind=row.get("kind", "resource"),
                    action=row.get("action", "submit"),
                    agreement_id=row.get("agreement_id", ""),
                    recurring=bool(row.get("recurring", True)),
                    resource=row.get("resource", ""),
                    quantity=float(row.get("quantity", 0.0)),
                    price_per_unit=float(row.get("price_per_unit", 0.0)),
                    route_safety=float(row.get("route_safety", 1.0)),
                    note=row.get("note", ""),
                    unit_template=row.get("unit_template", ""),
                    unit_year=int(row.get("unit_year", 0) or 0),
                    interest_rate=float(row.get("interest_rate", 0.0)),
                    turns=int(row.get("turns", 0) or 0),
                    principal=float(row.get("principal", 0.0)),
                )
            )

        out[nation] = TurnInput(
            build_orders=build_orders,
            refining_orders=refining_orders,
            unit_orders=unit_orders,
            research=research,
            treaties=treaties,
            policy_changes=policy_changes,
        )
    return out


def _snapshot_state(state) -> Dict[str, Any]:
    return {
        "code": state.code,
        "year": state.year,
        "war_status": state.war_status,
        "stability": state.stability,
        "war_support": state.war_support,
        "civ_ic": state.civ_ic,
        "mil_ic": state.mil_ic,
        "nav_ic": state.nav_ic,
        "stockpile": copy.deepcopy(state.stockpile),
        "facilities": copy.deepcopy(state.facilities),
        "research": copy.deepcopy(state.research),
        "techs": sorted(list(state.techs)),
        "policies": copy.deepcopy(state.policies),
        "queued_policies": copy.deepcopy(state.queued_policies),
        "army": copy.deepcopy(state.army),
        "navy": copy.deepcopy(state.navy),
        "airforce": copy.deepcopy(state.airforce),
    }


def _delta_map(before: Dict[str, float], after: Dict[str, float], threshold: float = 1e-9) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for k in sorted(set(before.keys()) | set(after.keys())):
        b = float(before.get(k, 0.0))
        a = float(after.get(k, 0.0))
        d = a - b
        if abs(d) > threshold:
            result[k] = round(d, 4)
    return result


def _build_preview(before_state, after_state, logs: List[str]) -> Dict[str, Any]:
    preview = {
        "nation": before_state.code,
        "year_before": before_state.year,
        "year_after": after_state.year,
        "ic_delta": {
            "civ_ic": round(after_state.civ_ic - before_state.civ_ic, 4),
            "mil_ic": round(after_state.mil_ic - before_state.mil_ic, 4),
            "nav_ic": round(after_state.nav_ic - before_state.nav_ic, 4),
        },
        "stockpile_delta": _delta_map(before_state.stockpile, after_state.stockpile),
        "facilities_delta": _delta_map(before_state.facilities, after_state.facilities),
        "army_delta": _delta_map(before_state.army, after_state.army),
        "navy_delta": _delta_map(before_state.navy, after_state.navy),
        "airforce_delta": _delta_map(before_state.airforce, after_state.airforce),
        "research_stockpile_delta": round(
            float(after_state.research.get("stockpile", 0.0)) - float(before_state.research.get("stockpile", 0.0)),
            4,
        ),
        "techs_added": sorted(list(after_state.techs - before_state.techs)),
        "queued_policies": copy.deepcopy(after_state.queued_policies),
        "logs": logs,
    }
    return preview


def run_turn_from_json_payload(db_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    db = DatabaseManager(db_path)
    try:
        nation_codes = list(db.load_all_nations().keys())
        errors, warnings = validate_json_payload(payload, nation_codes)
        if errors:
            raise PayloadValidationError(errors, warnings)

        turn_inputs = json_to_turn_inputs(payload)
        import static.spirits as _spirits
        _spirits.reload_from_db(db)
        results = EconomyEngine(db).process_turn(turn_inputs)

        states_after = db.load_all_nations()
        snapshot = {code: _snapshot_state(state) for code, state in states_after.items()}

        return {
            "ok": True,
            "warnings": warnings,
            "results": results,
            "snapshot": snapshot,
        }
    finally:
        db.close()


def preview_turn_from_json_payload(db_path: str, payload: Dict[str, Any], nation: str) -> Dict[str, Any]:
    source_db = DatabaseManager(db_path)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    try:
        states_before = source_db.load_all_nations()
        if nation not in states_before:
            raise ValueError(f"unknown nation code: {nation}")

        shutil.copy2(db_path, temp_file.name)

        temp_db = DatabaseManager(temp_file.name)
        try:
            nation_codes = list(temp_db.load_all_nations().keys())
            errors, warnings = validate_json_payload(payload, nation_codes)
            if errors:
                raise PayloadValidationError(errors, warnings)

            turn_inputs = json_to_turn_inputs(payload)
            import static.spirits as _spirits
            _spirits.reload_from_db(temp_db)
            results = EconomyEngine(temp_db).process_turn(turn_inputs)
            states_after = temp_db.load_all_nations()

            before = states_before[nation]
            after = states_after[nation]
            logs = results.get(nation, {}).get("logs", [])

            return {
                "ok": True,
                "warnings": warnings,
                "preview": _build_preview(before, after, logs),
            }
        finally:
            temp_db.close()
    finally:
        source_db.close()
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def list_active_agreements(db_path: str, nation: str | None = None) -> List[Dict[str, Any]]:
    db = DatabaseManager(db_path)
    try:
        return db.list_active_agreements(nation)
    finally:
        db.close()


# ── CLI 入口（原 run_turn_json.py）─────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(description="Run one turn from JSON payload")
    parser.add_argument("--db", default=os.path.join(_PROJECT_ROOT, "Database", "game.db"),
                        help="SQLite DB path")
    parser.add_argument("--input", required=True, help="JSON command file path")
    parser.add_argument("--output", default="", help="Output result JSON path")
    args = parser.parse_args()

    payload = load_json_file(args.input)

    try:
        result = run_turn_from_json_payload(args.db, payload)
    except PayloadValidationError as e:
        print("Validation failed:")
        for line in e.errors:
            print(f"  - {line}")
        if e.warnings:
            print("Warnings:")
            for line in e.warnings:
                print(f"  - {line}")
        raise SystemExit(2)

    output_path = args.output or os.path.splitext(args.input)[0] + ".result.json"
    save_json_file(output_path, result)
    print(f"Done. Result written to: {output_path}")
