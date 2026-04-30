"""
merge_and_run.py — 推演组合并多国指令并执行推演

用法示例：
    python utils/merge_and_run.py Database/game.db turn_3_GER.json turn_3_SOV.json turn_3_USA.json

每个 JSON 文件由玩家通过 player_ui 导出，结构为：
    { "schema_version": 1, "turn": N, "inputs": { "国家代码": { ... } } }

本脚本将所有文件的 inputs 合并，校验后执行推演并输出结果。
"""

import json
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.turn_json_pipeline import run_turn_from_json_payload, PayloadValidationError


def merge_payloads(json_files: list[str]) -> dict:
    merged = {"schema_version": 1, "inputs": {}}
    for path in json_files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for nation, orders in data.get("inputs", {}).items():
            if nation in merged["inputs"]:
                print(f"[警告] 国家 {nation} 在多个文件中出现，后者覆盖前者（{path}）")
            merged["inputs"][nation] = orders
        # 以最后一个文件的 turn 为准
        if "turn" in data:
            merged["turn"] = data["turn"]
    return merged


def main():
    if len(sys.argv) < 3:
        print("用法: python utils/merge_and_run.py <db路径> <json文件1> [json文件2 ...]")
        sys.exit(1)

    db_path = sys.argv[1]
    json_files = sys.argv[2:]

    if not os.path.exists(db_path):
        print(f"[错误] 数据库不存在: {db_path}")
        sys.exit(1)

    for f in json_files:
        if not os.path.exists(f):
            print(f"[错误] JSON文件不存在: {f}")
            sys.exit(1)

    print(f"合并 {len(json_files)} 个指令文件: {', '.join(json_files)}")
    payload = merge_payloads(json_files)
    nations = list(payload["inputs"].keys())
    print(f"参与国家: {', '.join(nations)}")

    try:
        result = run_turn_from_json_payload(db_path, payload)
    except PayloadValidationError as e:
        print("\n[校验失败]")
        for err in e.errors:
            print(f"  错误: {err}")
        for w in e.warnings:
            print(f"  警告: {w}")
        sys.exit(1)

    if result.get("warnings"):
        print("\n[警告]")
        for w in result["warnings"]:
            print(f"  {w}")

    print("\n=== 推演完成 ===")
    results = result.get("results", {})
    for nation, nr in sorted(results.items()):
        logs = nr.get("logs", []) if isinstance(nr, dict) else []
        if logs:
            print(f"\n[{nation}]")
            for log in logs:
                print(f"  {log}")

    snapshot = result.get("snapshot", {})
    print("\n=== 推演后状态 ===")
    for nation, snap in sorted(snapshot.items()):
        print(f"\n[{nation}]")
        print(f"  年份: {snap.get('year')}  稳定度: {snap.get('stability')}  战争支持: {snap.get('war_support')}")
        print(f"  民用IC: {float(snap.get('civ_ic', 0)):.2f}  军用IC: {float(snap.get('mil_ic', 0)):.2f}  船坞IC: {float(snap.get('nav_ic', 0)):.2f}")
        techs = snap.get("techs", [])
        if techs:
            print(f"  科技: {', '.join(sorted(techs))}")


if __name__ == "__main__":
    main()
