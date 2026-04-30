from static.units import UNIT_TEMPLATES, SPECIAL_CAPACITIES
from static.techs import TECH_SPECS

# 模块级反向映射：unit unlock key → 需要的 tech key
UNIT_UNLOCK_TECH = {
    unlock: tech_key
    for tech_key, spec in TECH_SPECS.items()
    for unlock in spec.get("unlocks", [])
}

def apply(state, unit_orders):
    for order in unit_orders:
        tpl = UNIT_TEMPLATES.get((order.template, order.year))
        if not tpl:
            continue
        unit_key = f"{order.template}_{order.year}"
        required_tech = UNIT_UNLOCK_TECH.get(unit_key)
        if required_tech and required_tech not in state.techs:
            state.temp["logs"].append(f"造兵失败: 缺少科技 {required_tech} 方可建造 {unit_key}")
            continue
        ic_type = tpl["ic_type"]
        ic_cost = tpl["ic_cost"] * order.quantity
        if ic_type == "mil" and state.temp["mil_ic"] < ic_cost:
            state.temp["logs"].append(f"造兵失败: 军用IC不足")
            continue
        if ic_type == "naval" and state.temp["nav_ic"] < ic_cost:
            state.temp["logs"].append(f"造兵失败: 海军IC不足")
            continue
        ok = True
        for res, amt in tpl["resources"].items():
            need = amt * order.quantity
            if res in SPECIAL_CAPACITIES:
                if state.temp["special"].get(res, 0) < need:
                    ok = False
                    break
            else:
                if state.stockpile.get(res, 0) < need:
                    ok = False
                    break
        if not ok:
            state.temp["logs"].append(f"造兵失败: 资源或专用产能不足")
            continue
        if ic_type == "mil":
            state.temp["mil_ic"] -= ic_cost
        else:
            state.temp["nav_ic"] -= ic_cost
        for res, amt in tpl["resources"].items():
            need = amt * order.quantity
            if res in SPECIAL_CAPACITIES:
                state.temp["special"][res] -= need
            else:
                state.stockpile[res] -= need
        unit_name = f"{order.template}_{order.year}"
        if order.template == "airwing":
            state.airforce[unit_name] = state.airforce.get(unit_name, 0) + order.quantity
        elif ic_type == "naval":
            state.navy[unit_name] = state.navy.get(unit_name, 0) + order.quantity
        else:
            state.army[unit_name] = state.army.get(unit_name, 0) + order.quantity
        state.temp["logs"].append(f"造兵成功: {order.quantity} x {unit_name}")