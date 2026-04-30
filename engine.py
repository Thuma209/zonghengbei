import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Database.db_manager import DatabaseManager
from models.orders import TurnInput

# 直接导入各 phase 模块的 apply 函数并赋予别名
from phases.phase_01_apply_queued import apply as phase_01
from phases.phase_02_gather import apply as phase_02
from phases.phase_03_refining import apply as phase_03
from phases.phase_04_trade import apply as phase_04
from phases.phase_05_research import apply as phase_05
from phases.phase_06_build import apply as phase_06
from phases.phase_07_maintain import apply as phase_07
from phases.phase_08_produce import apply as phase_08
from phases.phase_09_policy_stability import apply as phase_09
from phases.phase_10_commit import apply as phase_10

class EconomyEngine:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def process_turn(self, turn_inputs: dict) -> dict:
        states = self.db.load_all_nations()
        for state in states.values():
            state.temp = {"logs": []}

        # 1. 排队生效
        for state in states.values():
            phase_01(state)

        # 2. 地块汇总
        all_tiles = {t.code: t for s in states.values() for t in s.tiles}
        for state in states.values():
            phase_02(state, all_tiles)

        # 3. 精炼+出口（必须对所有国家执行，否则贸易法案出口不生效）
        for code, state in states.items():
            inp = turn_inputs.get(code)
            phase_03(state, inp.refining_orders if inp else [])

        # 4. 双边贸易
        all_treaties = []
        for code, inp in turn_inputs.items():
            if inp and inp.treaties:
                all_treaties.extend(inp.treaties)
        phase_04(states, all_treaties, self.db)

        # 5. 科研
        for code, state in states.items():
            inp = turn_inputs.get(code)
            if inp and inp.research:
                phase_05(state, inp.research)

        # 6. 建造
        for code, state in states.items():
            inp = turn_inputs.get(code)
            if inp and inp.build_orders:
                phase_06(state, inp.build_orders)

        # 7. 维护
        for state in states.values():
            phase_07(state)

        # 8. 造兵
        for code, state in states.items():
            inp = turn_inputs.get(code)
            if inp and inp.unit_orders:
                phase_08(state, inp.unit_orders)

        # 9. 政策/稳定度/电力惩罚
        for code, state in states.items():
            inp = turn_inputs.get(code)
            policy_changes = inp.policy_changes if inp else {}
            phase_09(state, policy_changes)

        # 10. 写回
        for state in states.values():
            phase_10(state, self.db)

        return {code: {"logs": state.temp["logs"]} for code, state in states.items()}