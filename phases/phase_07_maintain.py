from collections import defaultdict
from static.units import UNIT_TEMPLATES, SPECIAL_CAPACITIES


def apply(state):
    # 本回合已升级的军事科技类型（phase_05 写入）
    upgraded_types = state.temp.get("upgraded_unit_types", set())
    is_war = state.war_status == "war"

    mil_maint_ic = 0.0
    nav_maint_ic = 0.0
    resource_maint = defaultdict(float)
    special_maint = defaultdict(float)

    total_mods = state.modifiers.total()
    reduce_land  = min(1.0, max(0.0, total_mods.get("maint_reduction_land",  0.0)))
    reduce_naval = min(1.0, max(0.0, total_mods.get("maint_reduction_naval", 0.0)))
    reduce_air   = min(1.0, max(0.0, total_mods.get("maint_reduction_air",   0.0)))

    def _accum(unit_dict, ic_pool, base_rate, upgrade_rate, reduce):
        nonlocal mil_maint_ic, nav_maint_ic
        for unit_key, count in unit_dict.items():
            parts = unit_key.rsplit("_", 1)
            if len(parts) != 2:
                continue
            unit_type, year_str = parts
            try:
                year = int(year_str)
            except ValueError:
                continue
            tpl = UNIT_TEMPLATES.get((unit_type, year))
            if not tpl:
                continue
            # 本回合该军种科技升级则使用升级比例；否则战时使用基础比例，和平时为0
            if unit_type in upgraded_types:
                rate = upgrade_rate
            elif is_war:
                rate = base_rate
            else:
                rate = 0.0
            if rate == 0.0:
                continue
            ic_cost = tpl["ic_cost"] * count * rate * (1.0 - reduce)
            if ic_pool == "mil":
                mil_maint_ic += ic_cost
            else:
                nav_maint_ic += ic_cost
            for res, amt in tpl["resources"].items():
                total_res = amt * count * rate * (1.0 - reduce)
                if res in SPECIAL_CAPACITIES:
                    special_maint[res] += total_res
                else:
                    resource_maint[res] += total_res

    # 陆军：战时10%，科技升级20%，用mil_ic
    _accum(state.army,    "mil", base_rate=0.10, upgrade_rate=0.20, reduce=reduce_land)
    # 海军：战时3%，科技升级6%，用nav_ic
    _accum(state.navy,    "nav", base_rate=0.03, upgrade_rate=0.06, reduce=reduce_naval)
    # 空军：战时5%，科技升级10%，用mil_ic
    _accum(state.airforce, "mil", base_rate=0.05, upgrade_rate=0.10, reduce=reduce_air)

    # — IC 扣除 —
    state.temp["mil_ic"] -= mil_maint_ic
    state.temp["nav_ic"] -= nav_maint_ic
    if mil_maint_ic > 0 and state.temp["mil_ic"] < 0:
        state.temp["logs"].append(
            f"【推演组注意】军用IC维护费不足，缺少 {-state.temp['mil_ic']:.1f}")
    if nav_maint_ic > 0 and state.temp["nav_ic"] < 0:
        state.temp["logs"].append(
            f"【推演组注意】海军IC维护费不足，缺少 {-state.temp['nav_ic']:.1f}")

    # — 仓库资源扣除 —
    for res, amt in resource_maint.items():
        have = state.stockpile.get(res, 0)
        if have < amt:
            state.temp["logs"].append(
                f"【推演组注意】维护资源不足: {res} 需要 {amt:.2f}，仅有 {have:.2f}")
            state.stockpile[res] = 0
        else:
            state.stockpile[res] = have - amt

    # — 特殊产能扣除（炮/发/坦/飞） —
    for res, amt in special_maint.items():
        cur = state.temp["special"].get(res, 0)
        if cur < amt:
            state.temp["logs"].append(
                f"【推演组注意】维护产能不足: {res} 需要 {amt:.2f}，仅有 {cur:.2f}")
            state.temp["special"][res] = 0
        else:
            state.temp["special"][res] = cur - amt

    # — 战时油耗（仅战时） —
    if is_war:
        oil_used = 0.0
        for unit_key, count in state.army.items():
            # 装甲军和机械化步兵（infantry_1945）油耗 2.5；普通步兵 0
            if "armor" in unit_key or unit_key == "infantry_1945":
                oil_used += count * 2.5
        for unit_key, count in state.navy.items():
            if "battleship" in unit_key:
                oil_used += count * 1.0
            elif "carrier" in unit_key:
                oil_used += count * 0.8
            elif "screen" in unit_key:
                oil_used += count * 0.15  # 10艘屏卫 = 1.5 油
            elif "submarine" in unit_key:
                oil_used += count * 0.1
        for unit_key, count in state.airforce.items():
            if "airwing" in unit_key:
                oil_used += count * 0.2
        have_oil = state.stockpile.get("oil", 0)
        if have_oil < oil_used:
            state.temp["logs"].append(
                f"【推演组注意】石油不足，需要 {oil_used:.1f}，仅有 {have_oil:.1f}")
            state.stockpile["oil"] = 0
        else:
            state.stockpile["oil"] = have_oil - oil_used