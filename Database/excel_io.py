"""
单国 Excel ↔ game.db 导入/导出工具（pandas 重写版，100% 兼容 init_db 逻辑）
"""
import json
import os
import sqlite3"""
单国 Excel ↔ game.db 导入/导出工具（pandas 重写版，与 init_db.py 完全同源）
"""
import json
import os
import sqlite3
from collections import defaultdict

import pandas as pd
from openpyxl import Workbook

# ---------- 表列定义 ----------
_NATION_COLS = [
    "code", "name", "year", "war_status", "stability", "war_support",
    "civ_ic", "mil_ic", "nav_ic",
    "stockpile", "facilities", "pending_builds",
    "techs", "research", "army", "navy", "airforce",
    "policies", "queued_policies", "spirits",
    "capital_zone", "route_safety",
    "modifiers_policy", "modifiers_tech", "modifiers_spirit",
    "modifiers_stability", "modifiers_power_penalty", "modifiers_temporary",
]

_TILE_COLS = [
    "code", "name", "continent", "is_coastal", "controller",
    "occupation_type", "resources", "factories",
    "land_fort_level", "coastal_fort_level",
]

_AGR_COLS = [
    "id", "kind", "nation", "partner", "side",
    "recurring", "status", "payload", "created_turn", "note",
]

# ---------- 中文映射（完全复制 init_db.py） ----------
_NAME_TO_CODE = {
    "英国": "ENG", "德国": "GER", "美国": "USA", "苏联": "SOV",
    "日本": "JAP", "法国": "FRA", "意大利": "ITA",
}

_FACILITY_CN_MAP = {
    "民用工厂": "civilian_factory",
    "军用工厂": "military_factory",
    "船坞": "dockyard",
    "火炮厂": "artillery_foundry",
    "发动机厂": "engine_factory",
    "坦克厂": "tank_assembly",
    "飞机厂": "aircraft_assembly",
    "炼钢厂": "steel_mill",
    "炼铝厂": "aluminum_refinery",
    "合成油": "synthetic_oil_refinery",
    "合成橡胶": "synthetic_rubber_plant",
    "发电厂": "thermal_power_plant",
}

_RESOURCE_CN_MAP = {
    "石油": "oil",
    "生铁": "iron",
    "铝土": "bauxite",
    "煤炭": "coal",
    "钨": "tungsten",
    "稀有金属": "chromium",
    "橡胶": "rubber",
}

_STOCK_CN_MAP = {
    "橡胶库存": "rubber",
    "橡胶库存（除石油外资源库存单位为千）": "rubber",
    "钢库存": "steel",
    "铝库存": "aluminum",
    "钨库存": "tungsten",
    "铬库存": "chromium",
    "铝土矿库存": "bauxite",
    "煤库存": "coal",
    "生铁库存": "iron",
    "油库存": "oil",
}

_POLICY_CN_TO_EN = {
    "孤立主义": "isolationism", "严重孤立": "isolationism",
    "消费品经济": "consumer_economy",
    "民用经济": "civilian_economy",
    "前期动员": "early_mobilization", "早期动员": "early_mobilization", "初期动员": "early_mobilization",
    "部分动员": "partial_mobilization",
    "战时经济": "war_economy", "战争经济": "war_economy",
    "全面动员": "total_mobilization",
    "出口导向": "export_focus", "鼓励出口": "export_focus",
    "自由贸易": "free_trade",
    "贸易保护": "trade_protection",
    "封闭经济": "closed_economy",
    "最低税": "minimum_tax", "最低税率": "minimum_tax",
    "低税": "low_tax", "低税率": "low_tax",
    "平均税": "average_tax", "平均税率": "average_tax",
    "高税": "high_tax", "高税率": "high_tax",
    "最高税": "maximum_tax", "最高税率": "maximum_tax",
}

# ---------- 安全类型转换 ----------
def _safe_int(val):
    try:
        return int(float(val)) if pd.notna(val) and str(val).strip() != "" else 0
    except:
        return 0

def _safe_float(val):
    try:
        return float(val) if pd.notna(val) and str(val).strip() != "" else 0.0
    except:
        return 0.0

def _parse_tech_string(tech_str):
    if pd.isna(tech_str) or not str(tech_str).strip():
        return []
    prefix_map = {
        "工业": "industrial", "资源": "resource", "电子": "electronics",
        "步兵": "infantry", "装甲": "armor", "潜艇": "submarine",
        "航母": "carrier", "战列": "battleship", "屏卫": "screen", "空军": "aircraft",
    }
    techs = []
    for part in str(tech_str).split(","):
        part = part.strip()
        if not part:
            continue
        for ch, prefix in prefix_map.items():
            if part.startswith(ch):
                try:
                    lvl = int(part[len(ch):])
                    for i in range(1, lvl + 1):
                        techs.append(f"{prefix}_{i}")
                except ValueError:
                    pass
                break
    return techs

# ---------- 导出功能 ----------
def export_nation_excel(db_path, xlsx_path, nation_code):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    wb = Workbook()
    ws_n = wb.active
    ws_n.title = "国家"
    ws_n.append(_NATION_COLS)
    row = conn.execute("SELECT * FROM nation WHERE code=?", (nation_code,)).fetchone()
    if row:
        ws_n.append([json.dumps(row[c], ensure_ascii=False) if isinstance(row[c], (dict, list)) else row[c] for c in _NATION_COLS])
    ws_t = wb.create_sheet("地块")
    ws_t.append(_TILE_COLS)
    for t in conn.execute("SELECT * FROM tile WHERE controller=?", (nation_code,)):
        ws_t.append([json.dumps(t[c], ensure_ascii=False) if isinstance(t[c], (dict, list)) else t[c] for c in _TILE_COLS])
    ws_a = wb.create_sheet("协议")
    ws_a.append(_AGR_COLS)
    for a in conn.execute("SELECT * FROM agreement WHERE nation=? OR partner=?", (nation_code, nation_code)):
        ws_a.append([json.dumps(a[c], ensure_ascii=False) if isinstance(a[c], (dict, list)) else a[c] for c in _AGR_COLS])
    conn.close()
    wb.save(xlsx_path)

# ---------- 导入功能（完全复制 init_db.py 核心逻辑） ----------
def import_nation_excel(xlsx_path, db_path):
    # 读取国家表（Sheet2）
    df_nation = pd.read_excel(xlsx_path, sheet_name=1, dtype=str)
    df_nation.columns = [c.strip() for c in df_nation.columns]
    nation_row = df_nation.iloc[0]

    # 读取地块表（Sheet1）
    df_tiles = pd.read_excel(xlsx_path, sheet_name=0, dtype=str)
    df_tiles.columns = [c.strip() for c in df_tiles.columns]
    df_tiles = df_tiles[df_tiles["地块名"].notna()]

    # ---------- 国家数据 ----------
    chinese_name = str(nation_row.get("国家", "")).strip()
    code = str(nation_row.get("唯一代码", ""))
    if not code or code == "nan":
        code = _NAME_TO_CODE.get(chinese_name, chinese_name[:3].upper())
    name = chinese_name

    policies = {}
    for cat, col in [("economy_law", "经济法案"), ("trade_law", "贸易法案"), ("tax_policy", "税收政策")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cn_val = str(val).strip()
            policies[cat] = _POLICY_CN_TO_EN.get(cn_val, cn_val)

    techs = _parse_tech_string(nation_row.get("初始科技", ""))

    stockpile = {}
    for stock_col, res_key in _STOCK_CN_MAP.items():
        val = nation_row.get(stock_col)
        stockpile[res_key] = _safe_float(val)

    army, navy, airforce = {}, {}, {}
    for en_type, col in [("infantry", "步兵军"), ("armor", "装甲军")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cnt = _safe_int(val)
            if cnt > 0:
                army[f"{en_type}_1936"] = cnt
    air_val = nation_row.get("飞机")
    if pd.notna(air_val) and str(air_val).strip():
        planes = _safe_int(air_val)
        if planes > 0:
            airforce["airwing_1936"] = max(1, planes // 100)
    for en_type, col in [("submarine", "潜艇"), ("screen", "屏卫舰"), ("carrier", "航空母舰"), ("battleship", "主力舰")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cnt = _safe_int(val)
            if cnt > 0:
                navy[f"{en_type}_1936"] = cnt

    stability = _safe_float(nation_row.get("稳定度", 50))
    war_support = _safe_float(nation_row.get("战争支持度", 50))
    war_status = "peace"
    if pd.notna(nation_row.get("战争状态")):
        ws = str(nation_row.get("战争状态")).strip().lower()
        if ws in ("war", "战争"):
            war_status = "war"
    year = 1936

    spirits_raw = nation_row.get("国家精神", "")
    if pd.notna(spirits_raw) and str(spirits_raw).strip():
        spirits = [s.strip() for s in str(spirits_raw).split(",") if s.strip()]
    else:
        from static.spirits import _DEFAULT_SPECS
        spirits = list(_DEFAULT_SPECS.get(code, []))

    # ---------- 地块数据 ----------
    nation_facilities = defaultdict(int)
    tiles = []
    for _, row in df_tiles.iterrows():
        tile_code = str(row["编号"]).strip()
        tile_name = str(row["地块名"]).strip()
        continent = str(row["所属地域"]).strip() if pd.notna(row.get("所属地域")) else ""
        is_coastal = 1 if str(row.get("是否沿海", "0")).strip() == "1" else 0
        occ_raw = str(row["属性"]).strip() if pd.notna(row.get("属性")) else "核心"
        occ_map = {"core": "核心", "occupied": "占领", "puppet": "占领", "傀儡": "占领"}
        occupation_type = occ_map.get(occ_raw, occ_raw if occ_raw in ("核心", "占领") else "占领")

        factories = {}
        for excel_col, db_col in _FACILITY_CN_MAP.items():
            val = row.get(excel_col)
            factories[db_col] = _safe_int(val)
            nation_facilities[db_col] += factories[db_col]

        resources = {}
        for excel_col, res_name in _RESOURCE_CN_MAP.items():
            val = row.get(excel_col)
            resources[res_name] = _safe_float(val)

        land_fort = _safe_int(row.get("陆地要塞", 0))
        coastal_fort = _safe_int(row.get("海岸要塞", 0))

        tiles.append({
            "code": tile_code,
            "name": tile_name,
            "continent": continent,
            "is_coastal": is_coastal,
            "controller": code,
            "occupation_type": occupation_type,
            "resources": resources,
            "factories": factories,
            "land_fort_level": land_fort,
            "coastal_fort_level": coastal_fort,
        })

    # ---------- 写入数据库 ----------
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    if os.path.exists(db_path):
        for suf in ["-journal", "-wal", "-shm"]:
            lf = db_path + suf
            if os.path.exists(lf):
                try: os.remove(lf)
                except: pass

    fresh = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        if fresh:
            conn.executescript(_INLINE_SCHEMA)
            try:
                from static.spirits import _DEFAULT_SPECS
                for key, spec in _DEFAULT_SPECS.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO spirit_definition (key, name, desc, modifiers) VALUES (?,?,?,?)",
                        (key, spec.get("name", ""), spec.get("desc", ""), json.dumps(spec.get("modifiers", {})))
                    )
            except: pass

        conn.execute("DELETE FROM tile WHERE controller=?", (code,))
        conn.execute("DELETE FROM nation WHERE code=?", (code,))

        # 插入 nation
        fields = [
            "code", "name", "year", "war_status", "stability", "war_support",
            "civ_ic", "mil_ic", "nav_ic", "stockpile", "facilities", "pending_builds",
            "techs", "research", "army", "navy", "airforce", "policies", "queued_policies",
            "spirits", "capital_zone", "route_safety",
            "modifiers_policy", "modifiers_tech", "modifiers_spirit",
            "modifiers_stability", "modifiers_power_penalty", "modifiers_temporary"
        ]
        values = [
            code, name, year, war_status, stability, war_support,
            0.0, 0.0, 0.0,
            json.dumps(stockpile), json.dumps(dict(nation_facilities)), "[]",
            json.dumps(techs), '{"current": null, "progress": 0.0, "stockpile": 0.0}',
            json.dumps(army), json.dumps(navy), json.dumps(airforce),
            json.dumps(policies), "{}",
            json.dumps(spirits), "", "{}",
            "{}", "{}", "{}", "{}", "{}", "{}"
        ]
        conn.execute(f"INSERT INTO nation ({','.join(fields)}) VALUES ({','.join('?'*len(fields))})", values)

        # 插入 tiles
        for t in tiles:
            conn.execute("""
                INSERT INTO tile (
                    code, name, continent, is_coastal, controller, occupation_type,
                    resources, factories, land_fort_level, coastal_fort_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["code"], t["name"], t["continent"], t["is_coastal"], t["controller"],
                t["occupation_type"], json.dumps(t["resources"]), json.dumps(t["factories"]),
                t["land_fort_level"], t["coastal_fort_level"]
            ))

        conn.commit()
        return code, len(tiles), 0
    except Exception as e:
        conn.rollback()
        raise Exception(f"数据库写入失败: {e}")
    finally:
        conn.close()

_INLINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS spirit_definition (key TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', desc TEXT NOT NULL DEFAULT '', modifiers TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS nation (code TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER DEFAULT 1938, war_status TEXT DEFAULT 'peace', stability REAL DEFAULT 50.0, war_support REAL DEFAULT 50.0, civ_ic REAL DEFAULT 0.0, mil_ic REAL DEFAULT 0.0, nav_ic REAL DEFAULT 0.0, stockpile TEXT DEFAULT '{}', facilities TEXT DEFAULT '{}', pending_builds TEXT DEFAULT '[]', techs TEXT DEFAULT '[]', research TEXT DEFAULT '{"current": null, "progress": 0.0, "stockpile": 0.0}', army TEXT DEFAULT '{}', navy TEXT DEFAULT '{}', airforce TEXT DEFAULT '{}', policies TEXT DEFAULT '{}', queued_policies TEXT DEFAULT '{}', spirits TEXT DEFAULT '[]', capital_zone TEXT DEFAULT '', route_safety TEXT DEFAULT '{}', modifiers_policy TEXT DEFAULT '{}', modifiers_tech TEXT DEFAULT '{}', modifiers_spirit TEXT DEFAULT '{}', modifiers_stability TEXT DEFAULT '{}', modifiers_power_penalty TEXT DEFAULT '{}', modifiers_temporary TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS tile (code TEXT PRIMARY KEY, name TEXT NOT NULL, continent TEXT, is_coastal INTEGER DEFAULT 0, controller TEXT, occupation_type TEXT DEFAULT '核心', resources TEXT DEFAULT '{}', factories TEXT DEFAULT '{}', land_fort_level INTEGER DEFAULT 0, coastal_fort_level INTEGER DEFAULT 0, FOREIGN KEY (controller) REFERENCES nation(code));
CREATE TABLE IF NOT EXISTS agreement (id TEXT PRIMARY KEY, kind TEXT NOT NULL, nation TEXT NOT NULL, partner TEXT NOT NULL, side TEXT NOT NULL, recurring INTEGER DEFAULT 1, status TEXT DEFAULT 'active', payload TEXT DEFAULT '{}', created_turn REAL DEFAULT 0, note TEXT DEFAULT '');
"""faultdict

import pandas as pd
from openpyxl import Workbook

# ---------- 表列定义 ----------
_NATION_COLS = [
    "code", "name", "year", "war_status", "stability", "war_support",
    "civ_ic", "mil_ic", "nav_ic",
    "stockpile", "facilities", "pending_builds",
    "techs", "research", "army", "navy", "airforce",
    "policies", "queued_policies", "spirits",
    "capital_zone", "route_safety",
    "modifiers_policy", "modifiers_tech", "modifiers_spirit",
    "modifiers_stability", "modifiers_power_penalty", "modifiers_temporary",
]

_TILE_COLS = [
    "code", "name", "continent", "is_coastal", "controller",
    "occupation_type", "resources", "factories",
    "land_fort_level", "coastal_fort_level",
]

_AGR_COLS = [
    "id", "kind", "nation", "partner", "side",
    "recurring", "status", "payload", "created_turn", "note",
]

# ---------- 中文映射（同 init_db） ----------
_NAME_TO_CODE = {
    "英国": "ENG", "德国": "GER", "美国": "USA", "苏联": "SOV",
    "日本": "JAP", "法国": "FRA", "意大利": "ITA",
}

_FACILITY_CN_MAP = {
    "民用工厂": "civilian_factory",
    "军用工厂": "military_factory",
    "船坞": "dockyard",
    "火炮厂": "artillery_foundry",
    "发动机厂": "engine_factory",
    "坦克厂": "tank_assembly",
    "飞机厂": "aircraft_assembly",
    "炼钢厂": "steel_mill",
    "炼铝厂": "aluminum_refinery",
    "合成油": "synthetic_oil_refinery",
    "合成橡胶": "synthetic_rubber_plant",
    "发电厂": "thermal_power_plant",
}

_RESOURCE_CN_MAP = {
    "石油": "oil",
    "生铁": "iron",
    "铝土": "bauxite",
    "煤炭": "coal",
    "钨": "tungsten",
    "稀有金属": "chromium",
    "橡胶": "rubber",
}

_STOCK_CN_MAP = {
    "橡胶库存": "rubber",
    "橡胶库存（除石油外资源库存单位为千）": "rubber",
    "钢库存": "steel",
    "铝库存": "aluminum",
    "钨库存": "tungsten",
    "铬库存": "chromium",
    "铝土矿库存": "bauxite",
    "煤库存": "coal",
    "生铁库存": "iron",
    "油库存": "oil",
}

_POLICY_CN_TO_EN = {
    "孤立主义": "isolationism", "严重孤立": "isolationism",
    "消费品经济": "consumer_economy",
    "民用经济": "civilian_economy",
    "前期动员": "early_mobilization", "早期动员": "early_mobilization", "初期动员": "early_mobilization",
    "部分动员": "partial_mobilization",
    "战时经济": "war_economy", "战争经济": "war_economy",
    "全面动员": "total_mobilization",
    "出口导向": "export_focus", "鼓励出口": "export_focus",
    "自由贸易": "free_trade",
    "贸易保护": "trade_protection",
    "封闭经济": "closed_economy",
    "最低税": "minimum_tax", "最低税率": "minimum_tax",
    "低税": "low_tax", "低税率": "low_tax",
    "平均税": "average_tax", "平均税率": "average_tax",
    "高税": "high_tax", "高税率": "high_tax",
    "最高税": "maximum_tax", "最高税率": "maximum_tax",
}

# ---------- 辅助函数 ----------
def _safe_int(val):
    try:
        return int(float(val)) if pd.notna(val) and str(val).strip() != "" else 0
    except:
        return 0

def _safe_float(val):
    try:
        return float(val) if pd.notna(val) and str(val).strip() != "" else 0.0
    except:
        return 0.0

def _parse_tech_string(tech_str):
    if pd.isna(tech_str) or not str(tech_str).strip():
        return []
    prefix_map = {
        "工业": "industrial", "资源": "resource", "电子": "electronics",
        "步兵": "infantry", "装甲": "armor", "潜艇": "submarine",
        "航母": "carrier", "战列": "battleship", "屏卫": "screen", "空军": "aircraft",
    }
    techs = []
    for part in str(tech_str).split(","):
        part = part.strip()
        if not part:
            continue
        for ch, prefix in prefix_map.items():
            if part.startswith(ch):
                try:
                    lvl = int(part[len(ch):])
                    for i in range(1, lvl + 1):
                        techs.append(f"{prefix}_{i}")
                except ValueError:
                    pass
                break
    return techs

# ---------- 导出功能（保持不变） ----------
def export_nation_excel(db_path, xlsx_path, nation_code):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    wb = Workbook()
    ws_n = wb.active
    ws_n.title = "国家"
    ws_n.append(_NATION_COLS)
    row = conn.execute("SELECT * FROM nation WHERE code=?", (nation_code,)).fetchone()
    if row:
        ws_n.append([json.dumps(row[c], ensure_ascii=False) if isinstance(row[c], (dict, list)) else row[c] for c in _NATION_COLS])
    ws_t = wb.create_sheet("地块")
    ws_t.append(_TILE_COLS)
    for t in conn.execute("SELECT * FROM tile WHERE controller=?", (nation_code,)):
        ws_t.append([json.dumps(t[c], ensure_ascii=False) if isinstance(t[c], (dict, list)) else t[c] for c in _TILE_COLS])
    ws_a = wb.create_sheet("协议")
    ws_a.append(_AGR_COLS)
    for a in conn.execute("SELECT * FROM agreement WHERE nation=? OR partner=?", (nation_code, nation_code)):
        ws_a.append([json.dumps(a[c], ensure_ascii=False) if isinstance(a[c], (dict, list)) else a[c] for c in _AGR_COLS])
    conn.close()
    wb.save(xlsx_path)

# ---------- 导入功能（pandas 重写） ----------
def import_nation_excel(xlsx_path, db_path):
    # 读取国家表（Sheet2）
    df_nation = pd.read_excel(xlsx_path, sheet_name=1, dtype=str)
    df_nation.columns = [c.strip() for c in df_nation.columns]
    nation_row = df_nation.iloc[0]  # 第一行数据

    # 读取地块表（Sheet1）
    df_tiles = pd.read_excel(xlsx_path, sheet_name=0, dtype=str)
    df_tiles.columns = [c.strip() for c in df_tiles.columns]
    df_tiles = df_tiles[df_tiles["地块名"].notna()]

    # ---------- 处理国家数据 ----------
    chinese_name = str(nation_row.get("国家", "")).strip()
    code = str(nation_row.get("唯一代码", ""))
    if not code or code == "nan":
        code = _NAME_TO_CODE.get(chinese_name, chinese_name[:3].upper())
    name = chinese_name

    policies = {}
    for cat, col in [("economy_law", "经济法案"), ("trade_law", "贸易法案"), ("tax_policy", "税收政策")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cn_val = str(val).strip()
            policies[cat] = _POLICY_CN_TO_EN.get(cn_val, cn_val)

    techs = _parse_tech_string(nation_row.get("初始科技", ""))

    stockpile = {}
    for stock_col, res_key in _STOCK_CN_MAP.items():
        val = nation_row.get(stock_col)
        stockpile[res_key] = _safe_float(val)

    army, navy, airforce = {}, {}, {}
    for en_type, col in [("infantry", "步兵军"), ("armor", "装甲军")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cnt = _safe_int(val)
            if cnt > 0:
                army[f"{en_type}_1936"] = cnt
    air_val = nation_row.get("飞机")
    if pd.notna(air_val) and str(air_val).strip():
        planes = _safe_int(air_val)
        if planes > 0:
            airforce["airwing_1936"] = max(1, planes // 100)
    for en_type, col in [("submarine", "潜艇"), ("screen", "屏卫舰"), ("carrier", "航空母舰"), ("battleship", "主力舰")]:
        val = nation_row.get(col)
        if pd.notna(val) and str(val).strip():
            cnt = _safe_int(val)
            if cnt > 0:
                navy[f"{en_type}_1936"] = cnt

    stability = _safe_float(nation_row.get("稳定度", 50))
    war_support = _safe_float(nation_row.get("战争支持度", 50))
    war_status = "peace"
    if pd.notna(nation_row.get("战争状态")):
        ws = str(nation_row.get("战争状态")).strip().lower()
        if ws in ("war", "战争"):
            war_status = "war"
    year = 1936

    spirits_raw = nation_row.get("国家精神", "")
    if pd.notna(spirits_raw) and str(spirits_raw).strip():
        spirits = [s.strip() for s in str(spirits_raw).split(",") if s.strip()]
    else:
        from static.spirits import _DEFAULT_SPECS
        spirits = list(_DEFAULT_SPECS.get(code, []))

    # ---------- 处理地块数据 ----------
    nation_facilities = defaultdict(int)
    tiles = []
    for _, row in df_tiles.iterrows():
        tile_code = str(row["编号"]).strip()
        tile_name = str(row["地块名"]).strip()
        continent = str(row["所属地域"]).strip() if pd.notna(row.get("所属地域")) else ""
        is_coastal = 1 if str(row.get("是否沿海", "0")).strip() == "1" else 0
        occ_raw = str(row["属性"]).strip() if pd.notna(row.get("属性")) else "核心"
        occ_map = {"core": "核心", "occupied": "占领", "puppet": "占领", "傀儡": "占领"}
        occupation_type = occ_map.get(occ_raw, occ_raw if occ_raw in ("核心", "占领") else "占领")

        factories = {}
        for excel_col, db_col in _FACILITY_CN_MAP.items():
            val = row.get(excel_col)
            factories[db_col] = _safe_int(val)
            nation_facilities[db_col] += factories[db_col]

        resources = {}
        for excel_col, res_name in _RESOURCE_CN_MAP.items():
            val = row.get(excel_col)
            resources[res_name] = _safe_float(val)

        land_fort = _safe_int(row.get("陆地要塞", 0))
        coastal_fort = _safe_int(row.get("海岸要塞", 0))

        tiles.append({
            "code": tile_code,
            "name": tile_name,
            "continent": continent,
            "is_coastal": is_coastal,
            "controller": code,
            "occupation_type": occupation_type,
            "resources": resources,
            "factories": factories,
            "land_fort_level": land_fort,
            "coastal_fort_level": coastal_fort,
        })

    # ---------- 写数据库 ----------
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    if os.path.exists(db_path):
        for suf in ["-journal", "-wal", "-shm"]:
            lf = db_path + suf
            if os.path.exists(lf):
                try: os.remove(lf)
                except: pass

    fresh = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        if fresh:
            conn.executescript(_INLINE_SCHEMA)
            try:
                from static.spirits import _DEFAULT_SPECS
                for key, spec in _DEFAULT_SPECS.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO spirit_definition (key, name, desc, modifiers) VALUES (?,?,?,?)",
                        (key, spec.get("name", ""), spec.get("desc", ""), json.dumps(spec.get("modifiers", {})))
                    )
            except: pass

        conn.execute("DELETE FROM tile WHERE controller=?", (code,))
        conn.execute("DELETE FROM nation WHERE code=?", (code,))

        # 插入 nation
        fields = [
            "code", "name", "year", "war_status", "stability", "war_support",
            "civ_ic", "mil_ic", "nav_ic", "stockpile", "facilities", "pending_builds",
            "techs", "research", "army", "navy", "airforce", "policies", "queued_policies",
            "spirits", "capital_zone", "route_safety",
            "modifiers_policy", "modifiers_tech", "modifiers_spirit",
            "modifiers_stability", "modifiers_power_penalty", "modifiers_temporary"
        ]
        values = [
            code, name, year, war_status, stability, war_support,
            0.0, 0.0, 0.0,
            json.dumps(stockpile), json.dumps(dict(nation_facilities)), "[]",
            json.dumps(techs), '{"current": null, "progress": 0.0, "stockpile": 0.0}',
            json.dumps(army), json.dumps(navy), json.dumps(airforce),
            json.dumps(policies), "{}",
            json.dumps(spirits), "", "{}",
            "{}", "{}", "{}", "{}", "{}", "{}"
        ]
        conn.execute(f"INSERT INTO nation ({','.join(fields)}) VALUES ({','.join('?'*len(fields))})", values)

        # 插入 tiles
        for t in tiles:
            conn.execute("""
                INSERT INTO tile (
                    code, name, continent, is_coastal, controller, occupation_type,
                    resources, factories, land_fort_level, coastal_fort_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["code"], t["name"], t["continent"], t["is_coastal"], t["controller"],
                t["occupation_type"], json.dumps(t["resources"]), json.dumps(t["factories"]),
                t["land_fort_level"], t["coastal_fort_level"]
            ))

        conn.commit()
        return code, len(tiles), 0
    except Exception as e:
        conn.rollback()
        raise Exception(f"数据库写入失败: {e}")
    finally:
        conn.close()

_INLINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS spirit_definition (key TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', desc TEXT NOT NULL DEFAULT '', modifiers TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS nation (code TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER DEFAULT 1938, war_status TEXT DEFAULT 'peace', stability REAL DEFAULT 50.0, war_support REAL DEFAULT 50.0, civ_ic REAL DEFAULT 0.0, mil_ic REAL DEFAULT 0.0, nav_ic REAL DEFAULT 0.0, stockpile TEXT DEFAULT '{}', facilities TEXT DEFAULT '{}', pending_builds TEXT DEFAULT '[]', techs TEXT DEFAULT '[]', research TEXT DEFAULT '{"current": null, "progress": 0.0, "stockpile": 0.0}', army TEXT DEFAULT '{}', navy TEXT DEFAULT '{}', airforce TEXT DEFAULT '{}', policies TEXT DEFAULT '{}', queued_policies TEXT DEFAULT '{}', spirits TEXT DEFAULT '[]', capital_zone TEXT DEFAULT '', route_safety TEXT DEFAULT '{}', modifiers_policy TEXT DEFAULT '{}', modifiers_tech TEXT DEFAULT '{}', modifiers_spirit TEXT DEFAULT '{}', modifiers_stability TEXT DEFAULT '{}', modifiers_power_penalty TEXT DEFAULT '{}', modifiers_temporary TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS tile (code TEXT PRIMARY KEY, name TEXT NOT NULL, continent TEXT, is_coastal INTEGER DEFAULT 0, controller TEXT, occupation_type TEXT DEFAULT '核心', resources TEXT DEFAULT '{}', factories TEXT DEFAULT '{}', land_fort_level INTEGER DEFAULT 0, coastal_fort_level INTEGER DEFAULT 0, FOREIGN KEY (controller) REFERENCES nation(code));
CREATE TABLE IF NOT EXISTS agreement (id TEXT PRIMARY KEY, kind TEXT NOT NULL, nation TEXT NOT NULL, partner TEXT NOT NULL, side TEXT NOT NULL, recurring INTEGER DEFAULT 1, status TEXT DEFAULT 'active', payload TEXT DEFAULT '{}', created_turn REAL DEFAULT 0, note TEXT DEFAULT '');
"""