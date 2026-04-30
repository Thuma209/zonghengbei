# phase_05_research.py
"""
第五步：科研处理

规则依据手册：
- 每个国家每回合只能研究一个科技。
- 科技有1~5级，对应不同年代：
    1级：1936-1938
    2级：1939-1941
    3级：1942-1944
    4级：1945-1947
    5级：1948及以后
- 超前惩罚：每超前一级，基础成本乘以5。
- 科技完成时立即生效（修正累加到永久修正中）。
- 科研速度加成（research_speed）影响盈余计算：盈余 = 标准成本 × 科研速度（若加成>0）。
- 支持半年制年份（浮点数），比较时取年份整数部分。
"""

from static.techs import TECH_SPECS

def get_tech_level(tech_key: str) -> int:
    """
    从科技key中提取等级数字。
    例如：'industrial_2' -> 2, 'resource_5' -> 5。
    如果key格式不符合，默认返回1级（避免崩溃）。
    """
    parts = tech_key.split('_')
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 1

def get_available_level(year: float) -> int:
    """
    根据当前年份返回可以无惩罚研发的最高科技等级。
    年份可以是整数或半年的浮点数（如1938.5），比较时取整数部分。
    规则：
        - 1936-1938：1级
        - 1939-1941：2级
        - 1942-1944：3级
        - 1945-1947：4级
        - 1948及以后：5级
    """
    y = int(year)  # 忽略半年小数，只看年份
    if y >= 1948:
        return 5
    elif y >= 1945:
        return 4
    elif y >= 1942:
        return 3
    elif y >= 1939:
        return 2
    else:
        return 1

def apply(state, research_cmd: dict):
    """
    执行科研命令。

    参数:
        state: NationState对象
        research_cmd: dict，格式 {"tech": "科技key"}，引擎自动核算费用
    """
    if not research_cmd:
        return

    tech = research_cmd["tech"]

    # 获取科技定义
    spec = TECH_SPECS.get(tech)
    if not spec:
        state.temp["logs"].append(f"科研失败: 未知科技 {tech}")
        return

    # 检查是否已完成
    if tech in state.techs:
        state.temp["logs"].append(f"科研失败: 科技 {tech} 已完成")
        return

    # 检查前置科技
    for prereq in spec.get("prereq", []):
        if prereq not in state.techs:
            state.temp["logs"].append(f"科研失败: 缺少前置科技 {prereq}")
            return

    # ---------- 超前惩罚计算 ----------
    tech_level = get_tech_level(tech)
    available_level = get_available_level(state.year)
    ahead_levels = max(0, tech_level - available_level)

    # 基础成本乘以5的等级差次方
    base_cost = spec["cost"] * (5 ** ahead_levels)
    # ------------------------------------

    # 获取科研速度加成（来自修正总和）
    total_mods = state.modifiers.total()
    research_speed = total_mods.get("research_speed", 0.0)

    # 计算实际需要支付的IC
    # 负加成增加所需成本，正加成不影响最低支付额（但玩家可以多付来加速？手册未明确，此处按正加成不减少成本，但产生盈余）
    if research_speed < 0:
        required = base_cost * (1 - research_speed)  # 例如-10% → 1.1倍
    else:
        required = base_cost

    # 检查玩家支付的IC是否足够（至少需要等于required）
    if state.temp["civ_ic"] < required:
        state.temp["logs"].append(
            f"科研失败: 可用民用IC不足 (可用 {state.temp['civ_ic']:.1f}, 需要 {required:.1f})")
        return

    # 扣除民用IC（按引擎核算的 required 扣除）
    state.temp["civ_ic"] -= required

    # 科技完成
    state.techs.add(tech)
    state.temp["logs"].append(f"科研完成: {tech} (扣除 {required:.1f} IC, 超前 {ahead_levels} 级)")

    # 应用科技效果（百分比和绝对数值修正）
    for k, v in spec.get("effects_pct", {}).items():
        state.modifiers.tech[k] = state.modifiers.tech.get(k, 0.0) + v
    for k, v in spec.get("effects_abs", {}).items():
        state.modifiers.tech[k] = state.modifiers.tech.get(k, 0.0) + v

    # 无自动效果的科技（notify_only）：通知推演组手动处理
    if spec.get("notify_only", False):
        state.temp["logs"].append(
            f"【推演组注意】{state.code} 完成科技 {tech}，该科技无自动效果，请推演组手动处理。"
        )

    # 科研速度为正时产生盈余，存入科研槽
    if research_speed > 0:
        surplus = 1000 * research_speed  # 盈余固定按标准1000×速度，与实际费用无关
        state.research["stockpile"] = state.research.get("stockpile", 0.0) + surplus
        state.temp["logs"].append(f"科研槽盈余 +{surplus:.1f} (总计 {state.research['stockpile']:.1f})")
    # 追踪本回合军事科技升级类型（供 phase_07 判断维护费 20% 档位）
    for unlock_key in spec.get("unlocks", []):
        if not spec.get("skip_maintenance_upgrade", False):
            unit_type = unlock_key.rsplit("_", 1)[0]
            if "upgraded_unit_types" not in state.temp:
                state.temp["upgraded_unit_types"] = set()
            state.temp["upgraded_unit_types"].add(unit_type)
    # 科研槽满 1000 时通知推演组并扣除（每 1000 对应一次免费科研机会）
    while state.research.get("stockpile", 0.0) >= 1000.0:
        state.research["stockpile"] -= 1000.0
        state.temp["logs"].append("【推演组注意】科研槽达到1000，可选择一个不受超前惩罚的科技免费研究。")