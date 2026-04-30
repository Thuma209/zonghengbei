from static.recipes import RECIPE_SPECS
from static.policies import POLICY_SPECS

def apply(state, refining_orders):
    total_mods = state.modifiers.total()
    fixed_bonus = total_mods.get("resource_factory_fixed", 0)
    refining_outputs = {}
    refining_consumed = {}
    for order in refining_orders:
        recipe = RECIPE_SPECS[order.recipe]
        if recipe.get("tech_required") and recipe["tech_required"] not in state.techs:
            state.temp["logs"].append(f"精炼跳过: 缺少科技 {recipe['tech_required']}")
            continue
        fac_count = state.facilities.get(recipe["facility"], 0)
        runs = min(order.runs, fac_count)
        if runs <= 0:
            continue
        # 按最低满足率折算（手册规则：以满足比例最低的原料为准，产出和消耗同比例折算）
        ratio = 1.0
        for res, cost in recipe["inputs"].items():
            if res == "power":
                continue
            available = state.stockpile.get(res, 0)
            needed = cost * runs
            if needed > 0:
                ratio = min(ratio, available / needed)
        if ratio <= 1e-9:
            missing = [res for res, cost in recipe["inputs"].items()
                       if res != "power" and state.stockpile.get(res, 0) < cost]
            state.temp["logs"].append(f"精炼跳过: 原料不足 {missing}")
            continue
        if ratio < 1.0:
            state.temp["logs"].append(
                f"精炼减产: {order.recipe} 原料不足，按 {ratio*100:.1f}% 比例运行"
            )
        # 扣除原料（按比例消耗）
        for res, cost in recipe["inputs"].items():
            if res != "power":
                consumed = cost * runs * ratio
                state.stockpile[res] -= consumed
                refining_consumed[res] = refining_consumed.get(res, 0) + consumed
        # 产出（按比例，固定加成同样按比例缩放）
        for res, out in recipe["outputs"].items():
            amt = (out + fixed_bonus) * runs * ratio
            state.stockpile[res] = state.stockpile.get(res, 0) + amt
            refining_outputs[res] = refining_outputs.get(res, 0) + amt
        # 铬加成（基于实际运行量）
        if order.bonus_chromium > 0 and recipe.get("chromium_bonus"):
            effective_runs = runs * ratio
            chrome_used = min(order.bonus_chromium, effective_runs * recipe["chromium_cap"],
                              state.stockpile.get("chromium", 0))
            if chrome_used > 0:
                state.stockpile["chromium"] -= chrome_used
                state.stockpile["steel"] = state.stockpile.get("steel", 0) + chrome_used * recipe["chromium_bonus"]
    state.temp["refining_outputs"] = refining_outputs

    # 贸易政策出口
    trade_law = state.policies.get("trade_law", "trade_protection")
    export_ratio = POLICY_SPECS["trade_law"][trade_law]["export_ratio"]
    if export_ratio > 0:
        total_new = {}
        for d in [state.temp["raw_resources"], refining_outputs]:
            for res, amt in d.items():
                total_new[res] = total_new.get(res, 0) + amt
        # 扣除精炼已消耗的原料，避免双重计算
        for res, amt in refining_consumed.items():
            total_new[res] = total_new.get(res, 0) - amt
        for res, amt in total_new.items():
            lost = amt * export_ratio
            if lost > 0:
                state.stockpile[res] = max(0, state.stockpile.get(res, 0) - lost)