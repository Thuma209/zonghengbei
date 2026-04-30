from collections import defaultdict
from static.facilities import FACILITY_SPECS, INDUSTRIAL, MIL_SPECIAL
from static.sea_routes import get_route, continent_to_zone
from utils.modifiers import compute_alpha1, compute_stability_modifiers, compute_policy_modifiers, compute_spirit_modifiers, compute_tech_modifiers
from utils.tungsten import apply_tungsten_limit_all

def apply(state, all_tiles: dict = None):
    # 刷新政策修正（phase_01 已将 queued_policies 应用到 policies）
    state.modifiers.policy = compute_policy_modifiers(state.policies)
    # 刷新科技修正（从已研究科技集合重算，确保初始状态也正确）
    state.modifiers.tech = compute_tech_modifiers(state.techs)
    # 刷新国家精神修正
    state.modifiers.spirit = compute_spirit_modifiers(state.spirits)
    # 重新计算稳定度修正
    state.modifiers.stability = compute_stability_modifiers(state.stability)
    # 清除上回合电力惩罚，本回合将在电力检查后重新判定
    state.modifiers.power_penalty = {}
    # 合并所有修正（政策+科技+精神+稳定度，电力惩罚此时为空）
    total_mods = state.modifiers.total()

    # 初始化临时变量（IC 从 0 开始，结余单独加入，不参与百分比修正）
    state.temp = {
        "civ_ic": 0.0,
        "mil_ic": 0.0,
        "nav_ic": 0.0,
        "power_gen": 0.0,
        "power_demand": 0.0,
        "special": defaultdict(float),
        "raw_resources": defaultdict(float),
        "refining_outputs": defaultdict(float),
        "logs": [],
    }

    # 预算每个大洲 → sea_safety（避免地块循环内重复寻路+遍历通道地块）
    _zone_safety_cache: dict[str, float] = {}
    def _sea_safety(continent: str) -> float:
        if continent not in _zone_safety_cache:
            tile_zone = continent_to_zone(continent) if continent else ""
            route = get_route(tile_zone, state.capital_zone, nation_tag=state.code, all_tiles=all_tiles) if (tile_zone and state.capital_zone) else None
            _zone_safety_cache[continent] = state.route_safety.get(route, 1.0) if route else 1.0
        return _zone_safety_cache[continent]

    # 遍历地块汇总
    for tile in state.tiles:
        # 只有核心/core = 全产；其余（占领/occupied及一切未知类型）= 砍半
        occ_coeff = 1.0 if tile.occupation_type in ("核心", "core") else 0.5
        sea_safety = _sea_safety(tile.continent or "")

        for res, amt in tile.resources.items():
            state.temp["raw_resources"][res] += amt * occ_coeff * (1 + total_mods.get("resource_output", 0)) * sea_safety
        for fac, count in tile.factories.items():
            if fac not in FACILITY_SPECS:
                continue
            spec = FACILITY_SPECS[fac]
            if fac in INDUSTRIAL:
                ic_out = spec.ic_output * count * occ_coeff * sea_safety
                if fac == "civilian_factory":
                    state.temp["civ_ic"] += ic_out
                elif fac == "military_factory":
                    state.temp["mil_ic"] += ic_out
                elif fac == "dockyard":
                    state.temp["nav_ic"] += ic_out
            if fac == "thermal_power_plant":
                state.temp["power_gen"] += count * spec.power_gen * occ_coeff * (1 + total_mods.get("power_output", 0))
            state.temp["power_demand"] += count * spec.power_use * occ_coeff
            if fac in MIL_SPECIAL and spec.special_output:
                mil_fixed = total_mods.get("military_facility_fixed", 0)
                at_fixed = total_mods.get("artillery_tank_fixed", 0) if fac in ("artillery_foundry", "tank_assembly") else 0
                for cap, base_amt in spec.special_output.items():
                    per_unit = max(0.0, base_amt + mil_fixed + at_fixed)
                    state.temp["special"][cap] += count * per_unit * occ_coeff

    # 按民工厂→军工厂→船坞顺序应用钨限制（不足时依序扣减产出）
    tungsten_available = state.stockpile.get("tungsten", 0)
    ic_vals = {
        "civilian_factory": state.temp["civ_ic"],
        "military_factory": state.temp["mil_ic"],
        "dockyard": state.temp["nav_ic"],
    }
    count_vals = {
        "civilian_factory": state.facilities.get("civilian_factory", 0),
        "military_factory": state.facilities.get("military_factory", 0),
        "dockyard": state.facilities.get("dockyard", 0),
    }
    ic_vals, tungsten_consumed = apply_tungsten_limit_all(
        ic_vals, count_vals, tungsten_available,
        FACILITY_SPECS["civilian_factory"].tungsten_use
    )
    state.temp["civ_ic"] = ic_vals["civilian_factory"]
    state.temp["mil_ic"] = ic_vals["military_factory"]
    state.temp["nav_ic"] = ic_vals["dockyard"]
    state.stockpile["tungsten"] = tungsten_available - tungsten_consumed

    # 电力惩罚（当回合立即生效，同回合一并计入 total_mods）
    power_demand = state.temp["power_demand"]
    power_gen = state.temp["power_gen"]
    shortage = power_demand - power_gen
    if shortage > 0 and power_demand > 0:
        ratio = shortage / power_demand
        if ratio >= 2/3:
            state.modifiers.power_penalty = {"civ_output": -0.10, "mil_output": -0.15}
            state.stability = max(0, state.stability - 10)
        elif ratio >= 1/3:
            state.modifiers.power_penalty = {"civ_output": -0.05, "mil_output": -0.10}
            state.stability = max(0, state.stability - 10)
        else:
            state.modifiers.power_penalty = {"mil_output": -0.05}
            state.stability = max(0, state.stability - 5)
        # 稳定度下降后须立即重算稳定度修正，再合并，确保本回合 IC 计算正确
        state.modifiers.stability = compute_stability_modifiers(state.stability)
    # 不论是否有电力惩罚，都重新合并修正（确保 power_penalty 清空或新值都被纳入）
    total_mods = state.modifiers.total()

    # 应用消费品系数 alpha1（仅作用于本回合新民用产出）
    alpha1 = compute_alpha1(state, total_mods)
    state.temp["civ_ic"] *= (1 - alpha1)

    # 应用百分比加成（仅作用于本回合新产出）
    state.temp["civ_ic"] *= (1 + total_mods.get("civ_output", 0))
    state.temp["mil_ic"] *= (1 + total_mods.get("mil_output", 0))
    state.temp["nav_ic"] *= (1 + total_mods.get("mil_output", 0))  # 船坞与军用产出共享 mil_output 加成

    # 加入上回合结余（结余不再重复扣消费品和百分比）
    state.temp["civ_ic"] += state.civ_ic
    state.temp["mil_ic"] += state.mil_ic
    state.temp["nav_ic"] += state.nav_ic

    for cap in state.temp["special"]:
        state.temp["special"][cap] += total_mods.get("special_output_fixed", 0)

    # 将本回合地块原料产出合入仓库（后续精炼和出口将从仓库操作）
    for res, amt in state.temp["raw_resources"].items():
        state.stockpile[res] = state.stockpile.get(res, 0) + amt