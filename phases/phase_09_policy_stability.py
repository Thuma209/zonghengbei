from static.policies import POLICY_ORDER, POLICY_SPECS

def apply(state, policy_changes):
    # 验证相邻性并写入排队
    for cat, new_key in policy_changes.items():
        if cat not in POLICY_ORDER:
            continue
        order = POLICY_ORDER[cat]
        current = state.policies.get(cat)
        if current is None:
            state.queued_policies[cat] = new_key
        elif current == new_key:
            pass  # 无变化，静默忽略
        else:
            if current in order and new_key in order:
                if abs(order.index(current) - order.index(new_key)) == 1:
                    state.queued_policies[cat] = new_key
                else:
                    state.temp["logs"].append(f"政策变更拒绝: {cat} 从 {current} 到 {new_key} 跨档")
    # 注意：电力惩罚已在 phase_02 末尾立即计算，此处无需重复处理
    # 应用稳定度和战支变化
    total_mods = state.modifiers.total()
    state.stability = max(0, min(100, state.stability + total_mods.get("stability_delta", 0)))
    state.war_support = max(0, min(100, state.war_support + total_mods.get("war_support_delta", 0)))
    # 稳定度变化后立即更新 modifiers.stability，确保存入 DB 的值与新稳定度一致
    from utils.modifiers import compute_stability_modifiers
    state.modifiers.stability = compute_stability_modifiers(state.stability)