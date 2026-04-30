#!/usr/bin/env python3
"""
批量导出：从 game.db 为每个玩家国导出独立的 Excel 文件。
用法：python export_all_nations.py
输出：dist_xlsx/<CODE>.xlsx
"""
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from Database.excel_io import export_nation_excel

DB_PATH = os.path.join(ROOT, "Database", "game.db")
OUT_DIR = os.path.join(ROOT, "dist_xlsx")

PLAYER_NATIONS = [
    "GER", "USA", "ENG", "FRA", "SOV", "JAP",
    "ITA", "SPR", "TUR", "SWE", "FIN", "ROM", "BUL", "HUN",
]

def main():
    if not os.path.exists(DB_PATH):
        print(f"错误：找不到 {DB_PATH}")
        sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    for code in PLAYER_NATIONS:
        out = os.path.join(OUT_DIR, f"{code}.xlsx")
        export_nation_excel(DB_PATH, out, code)
        print(f"  [OK] {code} → {out}")
    print(f"\n完成！{len(PLAYER_NATIONS)} 个文件已导出到 {OUT_DIR}")

if __name__ == "__main__":
    main()
