def apply(state, db):
    # 将临时池中的IC结余写回持久字段
    state.civ_ic = max(0, state.temp["civ_ic"])
    state.mil_ic = max(0, state.temp["mil_ic"])
    state.nav_ic = max(0, state.temp["nav_ic"])
    state.year += 0.5
    db.save_nation(state)