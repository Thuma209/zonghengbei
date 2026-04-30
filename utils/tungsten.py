def apply_tungsten_limit_all(ic_dict: dict, count_dict: dict, tungsten: float, per_factory_use: float):
    """
    按民工厂→军工厂→船坞顺序分配钨，不足时按比例扣减对应工厂的产出。
    ic_dict:    {"civilian_factory": float, "military_factory": float, "dockyard": float}
    count_dict: {"civilian_factory": int,   "military_factory": int,   "dockyard": int}
    返回: (更新后的 ic_dict, 实际消耗的钨)
    """
    ORDER = ("civilian_factory", "military_factory", "dockyard")
    result = dict(ic_dict)
    consumed = 0.0
    remaining = tungsten
    for fac in ORDER:
        count = count_dict.get(fac, 0)
        if count <= 0 or per_factory_use <= 0:
            continue
        needed = count * per_factory_use
        if remaining >= needed:
            remaining -= needed
            consumed += needed
        else:
            ratio = remaining / needed
            result[fac] = result.get(fac, 0.0) * ratio
            consumed += remaining
            remaining = 0.0
    return result, consumed