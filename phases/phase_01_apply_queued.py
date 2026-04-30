def apply(state):
    # 排队政策生效
    if state.queued_policies:
        for cat, key in state.queued_policies.items():
            state.policies[cat] = key
        state.queued_policies.clear()
    # 建造已改为立即生效，pending_builds 不再使用