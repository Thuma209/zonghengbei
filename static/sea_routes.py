# static/sea_routes.py
# 航线安全系数静态定义
#
# Zone（大洲/区域）来自 tile.continent 经 CONTINENT_TO_ZONE 转换。
# 次大洲（japan/southeast_asia/scandinavia）继承父大洲路由：
#   对其他大洲的路由 = 父大洲对该大洲的路由。
# CHOKEPOINTS 定义通道控制权如何切换航道：
#   每条记录 (tile_code, 控制时航线, 未控制时航线)
#   tile_code=None = 无通道，直接用 open_route
#   route=None = 陆路直连，safety 1.0
#   route=... = 继续检查下一条记录
# 推演组通过 sim_ui "航线安全" 窗口设置每国每条航道安全系数（0~1）。

# ── 大洲中文 → zone key ────────────────────────────────────────────────────
CONTINENT_TO_ZONE: dict[str, str] = {
    "欧洲":           "europe",
    "北美洲":         "americas",
    "南美洲":         "americas",
    "美洲":           "americas",
    "日本列岛":       "japan",
    "日本":           "japan",
    "斯堪的纳维亚":   "scandinavia",
    "北欧":           "scandinavia",
    "亚洲":           "asia",
    "乌拉尔":         "asia",
    "中东":           "middle_east",
    "伊斯坦布尔":     "middle_east",
    "苏伊士":         "middle_east",
    "东南亚":         "southeast_asia",
    "马来群岛":       "southeast_asia",
    "非洲":           "africa",
    "大洋洲":         "oceania",
    "大洋洲群岛":     "pacific_islands",
    "南极洲":         "oceania",
    # 幻想乡五子区域
    "红魔馆":         "koumakan",
    "白玉楼":         "hakugyokurou",
    "博丽神社":       "hakurei",
    "八云邸":         "yakumo",
    "人间之里":       "village",
}

# zone key → 显示名
ZONE_NAMES: dict[str, str] = {
    "europe":         "欧洲",
    "americas":       "美洲",
    "japan":          "日本列岛",
    "scandinavia":    "斯堪的纳维亚",
    "asia":           "亚洲",
    "middle_east":    "中东",
    "southeast_asia": "东南亚",
    "africa":         "非洲",
    "oceania":        "大洋洲",
    "pacific_islands":"大洋洲群岛",
    # 幻想乡五子区域
    "koumakan":       "红魔馆",
    "hakugyokurou":   "白玉楼",
    "hakurei":        "博丽神社",
    "yakumo":         "八云邸",
    "village":        "人间之里",
}

# ── 航道名（已废弃，仅保留以免旧代码 import 报错）────────────────────────────
ROUTE_NAMES: dict[str, str] = {}  # 航道安全系数现在按大洲对 key 存储，此表废弃

# ── 次大洲 → 父大洲（路由继承）────────────────────────────────────────────
# 次大洲对其他大洲的路由 = 父大洲对那里的路由；同父大洲之间视为邻近（None）。
_PARENT_ZONE: dict[str, str] = {
    "japan":          "asia",
    "southeast_asia": "asia",
    "middle_east":    "asia",      # 中东归亚洲；europe↔middle_east 保留特殊条目
    "pacific_islands":"oceania",   # 大洋洲群岛归大洋洲
    "scandinavia":    "europe",
    # 幻想乡五子区域 → 日本列岛
    "koumakan":       "japan",
    "hakugyokurou":   "japan",
    "hakurei":        "japan",
    "yakumo":         "japan",
    "village":        "japan",
}

# ── 通道表 ───────────────────────────────────────────────────────────────
# 只收录有实际通道地块的父大洲对。次大洲由 get_route 上溯后命中此表。
# 每条记录: (tile_code, if_controlled, if_not_controlled)
#   None  → 陆路直连（safety 1.0）
#   True  → 海路（返回父大洲对键）
CHOKEPOINTS: dict[frozenset, list] = {
    # 欧洲 ↔ 亚洲：乌拉尔走廊 或 土耳其海峡（伊斯坦布尔），控制任一即陆路
    frozenset({"europe", "asia"}): [
        ("乌拉尔",      None,  False),  # 控制乌拉尔 → 陆路；否则继续检查
        ("伊斯坦布尔",  None,  True),   # 控制伊斯坦布尔 → 陆路；均未控制 → 海路
    ],
    # 亚洲 ↔ 非洲：苏伊士运河陆路；否则海路
    frozenset({"asia", "africa"}): [
        ("苏伊士", None, True),
    ],
}

_ROUTE_TABLE: dict[frozenset, str] = {}  # 已废弃，保留以免旧代码报错


def get_route(zone_a: str, zone_b: str, nation_tag: str = "",
              all_tiles: dict = None) -> str | None:
    """
    返回两 zone 之间的航线安全系数键，None = 陆路/safety 1.0。
    键格式：两个【父大洲】key 按字母序连接，如 'africa_europe'。
    次大洲自动上溯父大洲，所有子大洲共用同一父大洲对键：
      日本/东南亚/中东 → 亚洲；斯堪的纳维亚 → 欧洲；大洋洲群岛 → 大洋洲
    """
    if not zone_a or not zone_b or zone_a == zone_b:
        return None

    # 上溯到父大洲
    parent_a = _PARENT_ZONE.get(zone_a, zone_a)
    parent_b = _PARENT_ZONE.get(zone_b, zone_b)

    # 子大洲 ↔ 其直属父大洲：独立海路键（如日本↔亚洲 = asia_japan）
    if _PARENT_ZONE.get(zone_a) == zone_b or _PARENT_ZONE.get(zone_b) == zone_a:
        return "_".join(sorted([zone_a, zone_b]))

    # 同父大洲的其他子大洲之间（如日本↔东南亚）→ 也给独立键
    if parent_a == parent_b:
        return "_".join(sorted([zone_a, zone_b]))

    # 有子大洲 → 委托给父大洲对（复用父大洲键）
    if parent_a != zone_a or parent_b != zone_b:
        return get_route(parent_a, parent_b, nation_tag, all_tiles)

    # 以下两个都是父大洲
    pair_key = "_".join(sorted([zone_a, zone_b]))
    key = frozenset({zone_a, zone_b})
    tiles = all_tiles or {}

    checks = CHOKEPOINTS.get(key)
    if checks is not None:
        for continent_name, on_ctrl, off_ctrl in checks:
            if continent_name is None:
                r = on_ctrl
            else:
                # 按地块的 continent 属性寻找通道地块，而非 tile.code
                t = next(
                    (tile for tile in tiles.values() if tile.continent == continent_name),
                    None,
                )
                controlled = bool(t and nation_tag and t.controller == nation_tag)
                r = on_ctrl if controlled else off_ctrl
            if r is None:
                return None     # 陆路
            if r is True:
                return pair_key # 海路
        return pair_key

    # 兜底：两个父大洲之间默认海路
    return pair_key


def continent_to_zone(continent: str) -> str:
    """将 tile.continent 字符串转为 zone key，未知的原样返回。"""
    return CONTINENT_TO_ZONE.get(continent, continent)
