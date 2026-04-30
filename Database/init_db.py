#!/usr/bin/env python3
"""
数据库初始化脚本
从 数据库.xlsx 读取 Sheet1（地块）和 Sheet2（国家配置），生成 game.db
运行位置：项目根目录（D:\chentp\Desktop\zhbeconomic）
命令：python Database\init_db.py
"""

import sqlite3
import json
import os
import sys
from collections import defaultdict

# 确保项目根目录在 sys.path 中（支持从任意位置运行）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import pandas as pd
except ImportError:
    print("错误：需要 pandas 和 openpyxl，请运行：pip install pandas openpyxl")
    sys.exit(1)

# 文件路径配置
EXCEL_FILE = "全地块经济数据库.xlsx"                    # 位于根目录
DB_FILE = os.path.join("Database", "game.db")         # 数据库生成在 Database 目录内
SCHEMA_FILE = os.path.join("Database", "schema.sql")  # schema.sql 在 Database 目录内

# 国家代码映射（Excel控制者列 → 国家代码）
# Sheet2 的 "唯一代码" 列是权威来源；此 dict 为兜底（含无 Sheet2 配置的中立国）
COUNTRY_CODE_MAP = {
    "德国": "GER", "美国": "USA", "英国": "ENG", "苏联": "SOV", "法国": "FRA",
    "意大利": "ITA", "日本": "JAP", "瑞典": "SWE", "芬兰": "FIN", "匈牙利": "HUN",
    "罗马尼亚": "ROM", "保加利亚": "BUL", "西班牙": "SPR", "土耳其": "TUR",
    "尤丁采夫马": "AAA", "沃卡米什马": "ZZZ",
    # 中立国 / 小国（Sheet1 有地块但 Sheet2 无配置）
    "波兰": "POL", "捷克斯洛伐克": "CZE", "南斯拉夫": "YUG",
    "希腊": "GRE", "比利时": "BEL", "荷兰": "HOL", "丹麦": "DEN",
    "挪威": "NOR", "瑞士": "SWI", "葡萄牙": "POR", "爱尔兰": "IRE",
    "伊朗": "IRN", "伊拉克": "IRQ", "沙特阿拉伯": "SAU", "阿富汗": "AFG",
    "泰国": "SIA", "巴西": "BRA", "阿根廷": "ARG", "墨西哥": "MEX",
    "哥伦比亚": "COL", "委内瑞拉": "VEN", "智利": "CHL", "秘鲁": "PRU",
    "拉脱维亚": "LAT", "爱沙尼亚": "EST", "立陶宛": "LIT",
    "阿尔巴尼亚": "ALB", "利比里亚": "LBR", "也门": "YEM", "阿曼": "OMA",
    "中美洲": "CAM", "西班牙第二共和国": "SPC",
}

# 各国默认国家精神（可被 Excel Sheet2 "国家精神" 列覆盖）
NATION_DEFAULT_SPIRITS = {
    "GER": ["germany_mefo"],
    "USA": ["usa_great_depression"],
    "ENG": ["uk_empire"],
    "SOV": ["ussr_five_year"],
    "FRA": ["france_politics"],
    "ITA": ["italy_disorg"],
    "JAP": [],
    "SWE": ["sweden_neutral"],
    "FIN": ["finland_mannerheim"],
    "HUN": ["hungary_trianon"],
    "ROM": ["romania_iron_guard"],
    "BUL": ["bulgaria_neuilly"],
    "SPR": ["spain_recovery"],
    "TUR": ["turkey_legacy"],
    "AAA": ["inazuma_shogun"],
    "ZZZ": [],
}

# Sheet1 设施列名 → 数据库字段名
FACILITY_COLS = {
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

# Sheet1 资源列名 → 资源名
RESOURCE_COLS = {
    "石油": "oil",
    "生铁": "iron",
    "铝土": "bauxite",
    "煤炭": "coal",
    "钨": "tungsten",
    "稀有金属": "chromium",
    "橡胶": "rubber",
}

def create_tables(conn):
    """执行 schema.sql 建表"""
    if os.path.exists(SCHEMA_FILE):
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        print("已执行 schema.sql 建表。")
    else:
        print(f"错误：找不到 {SCHEMA_FILE}")
        sys.exit(1)

def parse_tile_sheet():
    """解析 Sheet1（地块数据）"""
    df = pd.read_excel(EXCEL_FILE, sheet_name=0, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["地块名"].notna()]

    # 从 Sheet2 读取 唯一代码 列，优先级高于 COUNTRY_CODE_MAP
    try:
        df2 = pd.read_excel(EXCEL_FILE, sheet_name=1, dtype=str)
        df2.columns = [c.strip() for c in df2.columns]
        for _, r2 in df2.iterrows():
            n = r2.get("国家")
            c = r2.get("唯一代码")
            if pd.notna(n) and pd.notna(c):
                COUNTRY_CODE_MAP[str(n).strip()] = str(c).strip()
    except Exception:
        pass

    nation_facilities = defaultdict(lambda: defaultdict(int))
    tiles = []

    for _, row in df.iterrows():
        controller_name = row.get("国家")
        if pd.isna(controller_name) or str(controller_name).strip() == "":
            continue
        controller_name = str(controller_name).strip()
        code = COUNTRY_CODE_MAP.get(controller_name)
        if not code:
            # 自动生成3字母代码（取前3个字符的拼音首字母或直接截取）
            code = controller_name[:3].upper()
            COUNTRY_CODE_MAP[controller_name] = code
            print(f"  自动生成代码：'{controller_name}' → {code}")

        tile_code = str(row["编号"]).strip()
        tile_name = str(row["地块名"]).strip()
        continent = str(row["所属地域"]).strip() if pd.notna(row.get("所属地域")) else ""
        is_coastal = 1 if str(row.get("是否沿海", "0")).strip() == "1" else 0
        _occ_raw = str(row["属性"]).strip() if pd.notna(row.get("属性")) else "核心"
        # 归一化：只保留核心/占领两种，其余（傀儡等）视为占领
        _occ_map = {"core": "核心", "occupied": "占领", "puppet": "占领", "傀儡": "占领"}
        occupation_type = _occ_map.get(_occ_raw, _occ_raw if _occ_raw in ("核心", "占领") else "占领")

        factories = {}
        for excel_col, db_col in FACILITY_COLS.items():
            val = row.get(excel_col)
            factories[db_col] = int(float(val)) if pd.notna(val) and str(val).strip() != "" else 0

        resources = {}
        for excel_col, res_name in RESOURCE_COLS.items():
            val = row.get(excel_col)
            resources[res_name] = float(val) if pd.notna(val) and str(val).strip() != "" else 0.0

        land_fort = int(float(row["陆地要塞"])) if "陆地要塞" in row and pd.notna(row.get("陆地要塞")) else 0
        coastal_fort = int(float(row["海岸要塞"])) if "海岸要塞" in row and pd.notna(row.get("海岸要塞")) else 0

        for db_col, qty in factories.items():
            nation_facilities[code][db_col] += qty

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

    return tiles, nation_facilities

def parse_tech_string(tech_str: str) -> list:
    """
    将 Sheet2 中的简化科技字符串转换为引擎内部科技 key 列表。
    例如 "工业2,资源1,电子2,步兵2,装甲1" → ["industrial_1","industrial_2","resource_1","electronics_1","electronics_2",...]
    """
    if pd.isna(tech_str) or not str(tech_str).strip():
        return []

    prefix_map = {
        "工业": "industrial",
        "资源": "resource",
        "电子": "electronics",
        "步兵": "infantry",
        "装甲": "armor",
        "潜艇": "submarine",
        "航母": "carrier",
        "战列": "battleship",
        "屏卫": "screen",
        "空军": "aircraft",
    }

    techs = []
    parts = str(tech_str).split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        for ch, prefix in prefix_map.items():
            if part.startswith(ch):
                try:
                    level = int(part[len(ch):])
                except ValueError:
                    continue
                for lvl in range(1, level + 1):
                    techs.append(f"{prefix}_{lvl}")
                break
    return techs

def parse_nation_config_sheet():
    """解析 Sheet2（国家配置）"""
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=1, dtype=str)
    except Exception as e:
        print(f"警告：无法读取 Sheet2，错误：{e}。各国将使用空初始状态。")
        return {}

    df.columns = [c.strip() for c in df.columns]
    configs = {}

    resource_col_map = {
        "生铁库存": "iron", "煤库存": "coal", "铝土矿库存": "bauxite",
        "钢库存": "steel", "铝库存": "aluminum", "油库存": "oil",
        "铬库存": "chromium", "钨库存": "tungsten",
        "橡胶库存（除石油外资源库存单位为千）": "rubber"
    }

    # 政策中文 → 英文 key（对应 POLICY_SPECS 中的键）
    POLICY_CN_TO_EN = {
        # economy_law
        "孤立主义": "isolationism", "严重孤立": "isolationism",
        "消费品经济": "consumer_economy",
        "民用经济": "civilian_economy",
        "前期动员": "early_mobilization", "早期动员": "early_mobilization",
        "初期动员": "early_mobilization",
        "部分动员": "partial_mobilization",
        "战时经济": "war_economy", "战争经济": "war_economy",
        "全面动员": "total_mobilization",
        # trade_law
        "出口导向": "export_focus", "鼓励出口": "export_focus",
        "自由贸易": "free_trade",
        "贸易保护": "trade_protection",
        "封闭经济": "closed_economy",
        # tax_policy
        "最低税": "minimum_tax", "最低税率": "minimum_tax",
        "低税": "low_tax", "低税率": "low_tax", "低税收": "low_tax",
        "平均税": "average_tax", "平均税率": "average_tax", "平均税收": "average_tax",
        "高税": "high_tax", "高税率": "high_tax", "高税收": "high_tax",
        "最高税": "maximum_tax", "最高税率": "maximum_tax",
    }

    for _, row in df.iterrows():
        name = row.get("国家")
        if pd.isna(name):
            continue
        name = str(name).strip()
        # 优先使用 "唯一代码" 列
        raw_code = row.get("唯一代码")
        if pd.notna(raw_code) and str(raw_code).strip():
            code = str(raw_code).strip()
        else:
            code = COUNTRY_CODE_MAP.get(name)
        if not code:
            print(f"警告：未知国家 '{name}'，跳过")
            continue

        policies = {}
        for cat, col in [("economy_law", "经济法案"), ("trade_law", "贸易法案"), ("tax_policy", "税收政策")]:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                cn_val = str(val).strip()
                en_val = POLICY_CN_TO_EN.get(cn_val, cn_val)  # 转换为英文key
                policies[cat] = en_val

        techs = parse_tech_string(row.get("初始科技", ""))

        stockpile = {}
        for col, res in resource_col_map.items():
            val = row.get(col)
            stockpile[res] = float(val) if pd.notna(val) and str(val).strip() else 0.0

        army, navy, airforce = {}, {}, {}
        for en_type, col in [("infantry", "步兵军"), ("armor", "装甲军")]:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                cnt = int(float(val))
                if cnt > 0:
                    army[f"{en_type}_1936"] = cnt
        air_val = row.get("飞机")
        if pd.notna(air_val) and str(air_val).strip():
            planes = int(float(air_val))
            if planes > 0:
                airforce["airwing_1936"] = max(1, planes // 100)  # 每个飞行队单位=100架飞机
        for en_type, col in [("submarine", "潜艇"), ("screen", "屏卫舰"), ("carrier", "航空母舰"), ("battleship", "主力舰")]:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                cnt = int(float(val))
                if cnt > 0:
                    navy[f"{en_type}_1936"] = cnt

        stability = float(row["稳定度"]) if pd.notna(row.get("稳定度")) else 50.0
        war_support = float(row["战争支持度"]) if pd.notna(row.get("战争支持度")) else 50.0
        year = 1938.5
        war_status = "peace"
        if pd.notna(row.get("战争状态")):
            ws = str(row["战争状态"]).strip().lower()
            if ws in ("war", "战争"):
                war_status = "war"

        # 国家精神：优先读 Excel 列，否则用默认映射
        spirits_raw = row.get("国家精神", "")
        if pd.notna(spirits_raw) and str(spirits_raw).strip():
            spirits = [s.strip() for s in str(spirits_raw).split(",") if s.strip()]
        else:
            spirits = list(NATION_DEFAULT_SPIRITS.get(code, []))

        configs[code] = {
            "policies": policies,
            "techs": techs,
            "stockpile": stockpile,
            "army": army,
            "navy": navy,
            "airforce": airforce,
            "stability": stability,
            "war_support": war_support,
            "year": year,
            "war_status": war_status,
            "spirits": spirits,
        }
    return configs

def insert_nations(conn, nation_facilities, nation_configs, nation_capital_zones):
    cursor = conn.cursor()
    # 反向映射：code → 中文名
    code_to_name = {v: k for k, v in COUNTRY_CODE_MAP.items()}
    for code, facs in nation_facilities.items():
        name = code_to_name.get(code, code)
        cfg = nation_configs.get(code, {})
        # 首都大洲：优先用配置里的，其次用地块推导的
        cfg["capital_zone"] = cfg.get("capital_zone") or nation_capital_zones.get(code, "")
        policies = cfg.get("policies", {})
        techs = cfg.get("techs", [])
        stockpile = cfg.get("stockpile", {})
        army = cfg.get("army", {})
        navy = cfg.get("navy", {})
        airforce = cfg.get("airforce", {})
        stability = cfg.get("stability", 50.0)
        war_support = cfg.get("war_support", 50.0)
        year = cfg.get("year", 1938)
        war_status = cfg.get("war_status", "peace")
        spirits = cfg.get("spirits", [])
        capital_zone = cfg.get("capital_zone", "")
        facilities = {db: facs.get(db, 0) for db in FACILITY_COLS.values()}

        # 计算精神修正
        from utils.modifiers import (compute_spirit_modifiers, compute_policy_modifiers,
                                     compute_tech_modifiers, compute_stability_modifiers)
        mods_spirit = compute_spirit_modifiers(spirits)
        mods_policy = compute_policy_modifiers(policies)
        mods_tech = compute_tech_modifiers(set(techs))
        mods_stability = compute_stability_modifiers(stability)

        # 构建字段和值列表（确保数量一致）
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
            json.dumps(stockpile), json.dumps(facilities), "[]",
            json.dumps(techs), '{"current": null, "progress": 0.0, "stockpile": 0.0}',
            json.dumps(army), json.dumps(navy), json.dumps(airforce),
            json.dumps(policies), "{}",
            json.dumps(spirits), capital_zone, "{}",
            json.dumps(mods_policy), json.dumps(mods_tech), json.dumps(mods_spirit),
            json.dumps(mods_stability), "{}", "{}"
        ]
        placeholders = ", ".join(["?"] * len(fields))
        query = f"INSERT INTO nation ({', '.join(fields)}) VALUES ({placeholders})"
        cursor.execute(query, values)
    conn.commit()

def insert_tiles(conn, tiles):
    cursor = conn.cursor()
    for t in tiles:
        cursor.execute("""
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

def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"错误：找不到 {EXCEL_FILE}")
        sys.exit(1)

    print("正在读取 Excel 数据...")
    tiles, nation_facilities = parse_tile_sheet()
    print(f"发现 {len(nation_facilities)} 个国家，{len(tiles)} 个地块")

    nation_configs = parse_nation_config_sheet()
    print(f"已加载 {len(nation_configs)} 个国家的配置")

    # 从地块推导各国首都大洲（取该国第一个地块的 continent 转为 zone key）
    from static.sea_routes import continent_to_zone
    nation_capital_zones: dict = {}
    for t in tiles:
        code = t["controller"]
        if code and code not in nation_capital_zones and t["continent"]:
            nation_capital_zones[code] = continent_to_zone(t["continent"])

    print("正在创建数据库...")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    create_tables(conn)

    print("正在种入国家精神定义...")
    from static.spirits import _DEFAULT_SPECS
    for key, spec in _DEFAULT_SPECS.items():
        conn.execute(
            "INSERT OR IGNORE INTO spirit_definition (key, name, desc, modifiers) VALUES (?,?,?,?)",
            (key, spec.get("name", ""), spec.get("desc", ""), json.dumps(spec.get("modifiers", {})))
        )
    conn.commit()
    print(f"  已写入 {len(_DEFAULT_SPECS)} 条精神定义")

    print("正在插入国家数据...")
    insert_nations(conn, nation_facilities, nation_configs, nation_capital_zones)

    print("正在插入地块数据...")
    insert_tiles(conn, tiles)

    conn.close()
    print(f"[OK] 数据库初始化完成！文件：{DB_FILE}")

if __name__ == "__main__":
    main()