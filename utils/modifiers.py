def compute_stability_modifiers(stability: float) -> dict:
    if stability >= 50:
        consumer = -0.025 - 0.025 * (stability - 50) / 50
        mil_bonus = 0.10 * (stability - 50) / 50
    else:
        consumer = -0.025 * (stability / 50)
        mil_bonus = -0.20 * (1 - stability / 50)
    return {"consumer_goods_delta": consumer, "mil_output": mil_bonus}

def compute_alpha1(state, total_mods: dict) -> float:
    base = 0.35
    econ = state.policies.get("economy_law")
    from static.policies import POLICY_SPECS
    if econ in POLICY_SPECS["economy_law"]:
        base = POLICY_SPECS["economy_law"][econ].get("alpha1", base)
    base += total_mods.get("consumer_goods_delta", 0)
    return max(0.0, min(1.0, base))


def compute_policy_modifiers(policies: dict) -> dict:
    """根据当前三类政策，计算合并后的百分比和绝对值修正。"""
    from static.policies import POLICY_SPECS
    result = {}
    for cat, key in policies.items():
        if cat not in POLICY_SPECS or key not in POLICY_SPECS[cat]:
            continue
        spec = POLICY_SPECS[cat][key]
        for k, v in spec.get("pct", {}).items():
            result[k] = result.get(k, 0.0) + v
        for k, v in spec.get("abs", {}).items():
            result[k] = result.get(k, 0.0) + v
    return result


def compute_spirit_modifiers(spirits: list) -> dict:
    """根据激活的国家精神key列表，计算合并修正。"""
    from static.spirits import SPIRIT_SPECS
    result = {}
    for key in spirits:
        spec = SPIRIT_SPECS.get(key)
        if not spec:
            continue
        for k, v in spec.get("modifiers", {}).items():
            result[k] = result.get(k, 0.0) + v
    return result


def compute_tech_modifiers(techs: set) -> dict:
    """根据已研究科技集合，计算合并后的修正。"""
    from static.techs import TECH_SPECS
    result = {}
    for key in techs:
        spec = TECH_SPECS.get(key)
        if not spec:
            continue
        for k, v in spec.get("effects_pct", {}).items():
            result[k] = result.get(k, 0.0) + v
        for k, v in spec.get("effects_abs", {}).items():
            result[k] = result.get(k, 0.0) + v
    return result