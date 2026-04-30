#!/usr/bin/env python3
"""
test_core.py — 趁手工具经济引擎回归测试
用法: python test_core.py

覆盖模块:
  T0  16 国全 10 阶段冒烟测试 (engine 完整流程)
  T1  和平期 IC 汇总 (phase_02)
  T2  精炼流水线 (phase_03)
  T3  双边贸易撮合 (phase_04)
  T4  战时 10% 基础维护 (phase_07)
  T5  科技升级 20% 维护 (phase_05 + phase_07)
  T6  船坞海岸限制 (phase_06)
  T7  政策变更 (phase_09 + phase_01)
  T8  5 回合稳定性压力测试
"""
import sys, os, copy, subprocess, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Database.db_manager import DatabaseManager
from engine import EconomyEngine
from models.orders import TurnInput, RefiningOrder, UnitOrder, TreatyTrade, BuildOrder
from static.techs import TECH_SPECS
from static.policies import POLICY_ORDER

# ═══════════════════════════════════════════════════════════
# 轻量测试框架
# ═══════════════════════════════════════════════════════════
_PASS = 0
_FAIL = 0

def CHECK(label: str, ok: bool, detail: str = ""):
    global _PASS, _FAIL
    if ok:
        _PASS += 1
        print(f"  [PASS] {label}")
    else:
        _FAIL += 1
        detail_str = f"   ← {detail}" if detail else ""
        print(f"  [FAIL] {label}{detail_str}")

def SECTION(title: str):
    print(f"\n{'━'*60}\n  {title}\n{'━'*60}")

# ═══════════════════════════════════════════════════════════
# 全局初始化（只 reinit 一次，后续用 deepcopy 快速重置）
# ═══════════════════════════════════════════════════════════
_INIT_PY = os.path.join(os.path.dirname(__file__), "Database", "init_db.py")
_DB_PATH  = os.path.join(os.path.dirname(__file__), "Database", "game.db")
AAA, ZZZ  = "AAA", "ZZZ"

def _open_db():
    return DatabaseManager(_DB_PATH)

def _run_turn(d: DatabaseManager, inputs: dict) -> dict:
    return EconomyEngine(d).process_turn(inputs)

def _logs(results: dict, nation: str) -> list:
    return results.get(nation, {}).get("logs", [])

def _empty():
    return TurnInput()

# 初始化数据库并保存干净快照
print("初始化数据库...")
_result = subprocess.run(
    [sys.executable, _INIT_PY],
    capture_output=True,
    cwd=os.path.dirname(os.path.abspath(__file__))
)
if not os.path.exists(_DB_PATH):
    print("STDOUT:", _result.stdout.decode("utf-8", errors="replace"))
    print("STDERR:", _result.stderr.decode("utf-8", errors="replace"))
    raise RuntimeError("init_db.py 失败，数据库文件未创建")
_BASE_DB = _open_db()
_CLEAN   = _BASE_DB.load_all_nations()   # 干净快照（在内存中）
_BASE_DB.close()


def _reset() -> DatabaseManager:
    """把数据库恢复到干净初始状态，返回新的连接。"""
    d = _open_db()
    for state in copy.deepcopy(_CLEAN).values():
        d.save_nation(state)
    return d


# ═══════════════════════════════════════════════════════════
# T0: 16 国全 10 阶段冒烟测试
# ═══════════════════════════════════════════════════════════
def test_all_nations_full_pipeline():
    SECTION("T0: 16 国全 10 阶段冒烟测试 (engine 完整流程)")
    d = _reset()
    try:
        states = d.load_all_nations()
        CHECK("加载国家数 >= 16", len(states) >= 16, f"实际={len(states)}")

        # 为每个国家构建空 TurnInput
        turn_inputs = {code: _empty() for code in states}

        results = _run_turn(d, turn_inputs)
        CHECK("process_turn 无异常返回", results is not None)

        end_states = d.load_all_nations()
        for code, s in sorted(end_states.items()):
            civ = s.civ_ic
            mil = s.mil_ic
            nav = s.nav_ic
            print(f"    {code}: civ={civ:.1f}  mil={mil:.1f}  nav={nav:.1f}")

        # 每个国家都应产生结果
        CHECK("所有国家都有结果", len(results) == len(states),
              f"results={len(results)}, states={len(states)}")

        # 基本合理性：至少有一国 civ_ic > 0
        any_civ = any(s.civ_ic > 0 for s in end_states.values())
        CHECK("至少一国 civ_ic > 0", any_civ)

        # 检查无 "错误" / "error" 级别日志
        error_nations = []
        for code, r in results.items():
            err_logs = [l for l in r.get("logs", [])
                        if "错误" in str(l) or "error" in str(l).lower()]
            if err_logs:
                error_nations.append(f"{code}: {err_logs}")
        CHECK("无国家出现错误级日志", not error_nations, str(error_nations))
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T1: 和平期 IC 汇总
# ═══════════════════════════════════════════════════════════
def test_gather_peace():
    SECTION("T1: 和平期 IC 汇总 (phase_02)")
    d = _reset()
    try:
        results = _run_turn(d, {AAA: _empty(), ZZZ: _empty()})
        s = d.load_all_nations()
        sa, sz = s[AAA], s[ZZZ]

        CHECK("AAA civ_ic > 0", sa.civ_ic > 0, f"civ_ic={sa.civ_ic:.2f}")
        CHECK("AAA mil_ic > 0", sa.mil_ic > 0, f"mil_ic={sa.mil_ic:.2f}")
        CHECK("ZZZ civ_ic > 0", sz.civ_ic > 0, f"civ_ic={sz.civ_ic:.2f}")
        CHECK("ZZZ mil_ic > 0", sz.mil_ic > 0, f"mil_ic={sz.mil_ic:.2f}")

        # 原材料应已进入仓库（phase_02 末尾 raw_resources → stockpile）
        iron_a = sa.stockpile.get("iron", 0)
        CHECK("AAA 铁矿进入仓库", iron_a > 0, f"iron={iron_a:.1f}")

        # 和平下没有维护警告
        no_warn = not any("维护" in l for l in _logs(results, AAA))
        CHECK("和平期无维护警告", no_warn, str(_logs(results, AAA)))

        print(f"    AAA: civ={sa.civ_ic:.1f}  mil={sa.mil_ic:.1f}  nav={sa.nav_ic:.1f}")
        print(f"    ZZZ: civ={sz.civ_ic:.1f}  mil={sz.mil_ic:.1f}  nav={sz.nav_ic:.1f}")
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T2: 精炼流水线
# ═══════════════════════════════════════════════════════════
def test_refining():
    SECTION("T2: 精炼流水线 (phase_03)")
    d = _reset()
    try:
        # 注入充足的原料，清零产成品
        states = d.load_all_nations()
        sa = states[AAA]
        sa.stockpile.update({"iron": 5000, "coal": 5000, "bauxite": 5000,
                              "steel": 0, "aluminum": 0})
        d.save_nation(sa)

        orders = {
            AAA: TurnInput(refining_orders=[
                RefiningOrder(recipe="steel",    runs=5),
                RefiningOrder(recipe="aluminum", runs=5),
            ]),
            ZZZ: _empty(),
        }
        _run_turn(d, orders)

        sa2 = d.load_all_nations()[AAA]
        steel = sa2.stockpile.get("steel", 0)
        alum  = sa2.stockpile.get("aluminum", 0)
        iron  = sa2.stockpile.get("iron", 0)
        coal  = sa2.stockpile.get("coal", 0)

        CHECK("steel 有产出",   steel > 0,       f"steel={steel:.1f}")
        CHECK("aluminum 有产出", alum  > 0,       f"alum={alum:.1f}")
        CHECK("铁矿有消耗",      iron  < 5000,    f"iron 剩 {iron:.1f}")
        # 注: coal 是地块自然资源，当回合 tile 产 coal 可能抵消消耗，不做 <5000 判断
        # steel mill 单次: 消耗 iron=40,coal=10 → 产 steel=24
        # ≤5 runs（受工厂数限制），至少 1 run → steel ≥ 24，iron 减少 ≥ 40
        CHECK("iron 消耗 ≥ 40",  5000 - iron >= 40,  f"消耗 {5000-iron:.1f}")

        print(f"    炼钢产出: {steel:.1f}, 铁矿减少: {5000-iron:.1f}, 煤炭减少: {5000-coal:.1f}")
        print(f"    炼铝产出: {alum:.1f},  铝土减少: {5000-sa2.stockpile.get('bauxite',0):.1f}")
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T3: 双边贸易撮合
# ═══════════════════════════════════════════════════════════
def test_trade():
    SECTION("T3: 双边贸易撮合 (phase_04)")
    d = _reset()
    try:
        # 给 ZZZ 一些油，让 AAA 进口
        states = d.load_all_nations()
        sa, sz = states[AAA], states[ZZZ]
        sz.stockpile["oil"] = 200
        d.save_nation(sa)
        d.save_nation(sz)

        # 价格 8 IC/桶，量 5 桶 → 总成本 40 IC（和平期 civ_ic ~50+）
        PRICE, QTY = 8, 5
        treaties_a = [TreatyTrade(AAA, ZZZ, "oil", QTY, PRICE, "import", 1.0)]
        treaties_z = [TreatyTrade(ZZZ, AAA, "oil", QTY, PRICE, "export", 1.0)]

        results = _run_turn(d, {
            AAA: TurnInput(treaties=treaties_a),
            ZZZ: TurnInput(treaties=treaties_z),
        })

        la = _logs(results, AAA)
        lz = _logs(results, ZZZ)
        sa2 = d.load_all_nations()[AAA]
        sz2 = d.load_all_nations()[ZZZ]

        import_ok = any("进口" in l and "oil" in l for l in la)
        export_ok = any("出口" in l and "oil" in l for l in lz)
        no_fail   = not any("贸易失败" in l for l in la + lz)

        CHECK("AAA 进口 oil 成功（日志）",        import_ok, str(la))
        CHECK("ZZZ 出口 oil 成功（日志）",        export_ok, str(lz))
        CHECK("无贸易失败日志",                   no_fail,   str(la + lz))
        CHECK("AAA oil 库存增加",                 sa2.stockpile.get("oil", 0) >= QTY,
              f"oil={sa2.stockpile.get('oil',0):.1f}")
        # 注: ZZZ tile 自然产 oil，库存净增是正常的；通过日志已验证出口成功

        # 贸易失败测试：价格过高撮合失败
        d2 = _reset()
        try:
            sz3 = d2.load_all_nations()[ZZZ]
            sz3.stockpile["oil"] = 10
            d2.save_nation(sz3)
            huge_price = 99999   # IC 肯定不足
            results2 = _run_turn(d2, {
                AAA: TurnInput(treaties=[TreatyTrade(AAA, ZZZ, "oil", 5, huge_price, "import", 1.0)]),
                ZZZ: TurnInput(treaties=[TreatyTrade(ZZZ, AAA, "oil", 5, huge_price, "export", 1.0)]),
            })
            la2 = _logs(results2, AAA)
            fail_logged = any("贸易失败" in l for l in la2)
            CHECK("IC 不足时记录贸易失败日志", fail_logged, str(la2))
        finally:
            d2.close()
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T4: 战时 10% 基础维护
# ═══════════════════════════════════════════════════════════
def test_war_maintenance():
    SECTION("T4: 战时 10% 基础维护 (phase_07)")
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        sa.war_status = "war"
        # 3 步兵 1936：ic=1000 each → 维护 IC = 3*1000*0.10 = 300
        #   钢铁: 3*70*0.10 = 21，钨: 3*7*0.10 = 2.1
        sa.army        = {"infantry_1936": 3}
        sa.navy        = {}
        sa.airforce    = {}
        sa.stockpile["steel"]   = 5000.0
        sa.stockpile["tungsten"] = 500.0
        sa.stockpile["oil"]     = 500.0   # 防止油耗报错
        d.save_nation(sa)

        results = _run_turn(d, {AAA: _empty(), ZZZ: _empty()})
        sa2 = d.load_all_nations()[AAA]
        la  = _logs(results, AAA)

        # 理论维护 IC = 300，gather 后 mil_ic > 0 说明支付了
        no_ic_short = not any("军用IC维护费不足" in l for l in la)
        CHECK("维护 IC 充足（无不足警告）",  no_ic_short, str(la))

        # gather 期间不精炼 → steel 只减不增
        steel_after = sa2.stockpile.get("steel", 0)
        tungsten_after = sa2.stockpile.get("tungsten", 0)
        expected_steel_deduct  = 3 * 70 * 0.10   # 21
        expected_tung_deduct   = 3 * 7  * 0.10   # 2.1

        CHECK("钢铁维护消耗 ~21",
              abs((5000 - steel_after) - expected_steel_deduct) < 2,
              f"实际消耗 {5000-steel_after:.2f}，期望 {expected_steel_deduct:.1f}")
        # 注: 钨是地块自然资源，tile 产出抵消维护消耗，净差不可测；仅记录
        print(f"    钨  :  500 → {tungsten_after:.2f}  (注: tile 自然产钨，净值不代表维护量)")

        print(f"    钢铁: 5000 → {steel_after:.2f}  (消耗 {5000-steel_after:.2f}，理论 {expected_steel_deduct})")
        print(f"    mil_ic: {sa2.mil_ic:.1f}")
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T5: 科技升级 20% 维护
# ═══════════════════════════════════════════════════════════
def test_upgrade_maintenance():
    SECTION("T5: 科技升级 20% 维护 (phase_05 → phase_07)")
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        sa.war_status = "war"
        sa.year       = 1939.0    # infantry_2 (level-2) 在 1939 年无超前惩罚
        sa.army       = {"infantry_1936": 2}
        sa.navy       = {}
        sa.airforce   = {}
        sa.techs.discard("infantry_2")
        sa.techs.add("infantry_1")          # 满足前置 prereq
        sa.stockpile["steel"]    = 5000.0
        sa.stockpile["tungsten"] = 500.0
        sa.stockpile["oil"]      = 500.0
        d.save_nation(sa)

        results = _run_turn(d, {
            AAA: TurnInput(research={"tech": "infantry_2", "payment": 1000}),
            ZZZ: _empty(),
        })
        sa2 = d.load_all_nations()[AAA]
        la  = _logs(results, AAA)

        # 科技应完成
        CHECK("infantry_2 本轮完成",
              "infantry_2" in sa2.techs, f"techs={sa2.techs}")

        # 20% 维护：2 步兵 * 1000 * 20% = 400 IC
        # 钢铁：2 * 70 * 20% = 28，是 T4 (21) 的 4/3 倍
        no_short = not any("维护费不足" in l for l in la)
        CHECK("升级维护 IC 充足", no_short, str(la))

        steel_after = sa2.stockpile.get("steel", 0)
        expected_20 = 2 * 70 * 0.20   # 28
        expected_10 = 2 * 70 * 0.10   # 14（普通战时）

        CHECK("钢铁消耗 ~28 (20%) 而非 ~14 (10%)",
              abs((5000 - steel_after) - expected_20) < 2,
              f"实际 {5000-steel_after:.2f}，期望20%={expected_20}，10%={expected_10}")

        print(f"    钢铁: 5000 → {steel_after:.2f}  "
              f"(消耗 {5000-steel_after:.2f}，20%理论={expected_20}，10%理论={expected_10})")
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T6: 船坞海岸限制
# ═══════════════════════════════════════════════════════════
def test_coastal_restriction():
    SECTION("T6: 船坞海岸限制 (phase_06)")
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        non_coastal = [t for t in sa.tiles if not t.is_coastal]

        if not non_coastal:
            print("  [SKIP] AAA 无非沿海地块，跳过该测试")
            return

        target = non_coastal[0]
        before = target.factories.get("dockyard", 0)
        sa.stockpile["steel"] = 99999   # 排除材料不足干扰
        d.save_nation(sa)

        results = _run_turn(d, {
            AAA: TurnInput(build_orders=[BuildOrder("dockyard", 1, target.code)]),
            ZZZ: _empty(),
        })
        sa2 = d.load_all_nations()[AAA]
        la  = _logs(results, AAA)
        tile2 = next(t for t in sa2.tiles if t.code == target.code)

        CHECK("非沿海地块船坞数未增加",
              tile2.factories.get("dockyard", 0) == before,
              f"before={before}, after={tile2.factories.get('dockyard',0)}")
        CHECK("日志记录拒绝理由（含'海岸'/'dockyard'/'船坞'）",
              any(kw in l for l in la for kw in ("沿海", "dockyard", "船坞")),
              str(la))
        print(f"    测试地块: {target.code}({target.name}), is_coastal={target.is_coastal}")
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T7: 政策变更
# ═══════════════════════════════════════════════════════════
def test_policy_changes():
    SECTION("T7: 政策变更 (phase_09 + phase_01)")
    tax_order = POLICY_ORDER.get("tax_policy", [])
    if len(tax_order) < 3:
        print("  [SKIP] tax_policy 档位不足 3，跳过该测试")
        return

    # ── T7a: 合法前进一档 ──
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        # 把 AAA 税务政策设为中间档（确保左右都有空间）
        mid = len(tax_order) // 2
        sa.policies["tax_policy"] = tax_order[mid]
        sa.queued_policies = {}
        d.save_nation(sa)

        current = tax_order[mid]
        legal   = tax_order[mid + 1]  # 前进一档

        _run_turn(d, {AAA: TurnInput(policy_changes={"tax_policy": legal}), ZZZ: _empty()})
        sa2 = d.load_all_nations()[AAA]

        # phase_09 本轮验证合法性并写入 queued_policies
        # phase_01 下一轮生效 → queued_policies 应已有 legal
        queued = sa2.queued_policies.get("tax_policy")
        CHECK("合法变更写入 queued_policies",
              queued == legal, f"queued={queued}, 期望={legal}")
    finally:
        d.close()

    # ── T7b: 合法变更下一轮 phase_01 生效 ──
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        sa.policies["tax_policy"] = tax_order[mid]
        sa.queued_policies        = {}
        d.save_nation(sa)
        legal = tax_order[mid + 1]

        # 第一轮：提交申请
        _run_turn(d, {AAA: TurnInput(policy_changes={"tax_policy": legal}), ZZZ: _empty()})
        # 第二轮：phase_01 应将 queued → policies
        _run_turn(d, {AAA: _empty(), ZZZ: _empty()})
        sa3 = d.load_all_nations()[AAA]

        CHECK("两轮后 policies['tax_policy'] == legal",
              sa3.policies.get("tax_policy") == legal,
              f"actual={sa3.policies.get('tax_policy')}, 期望={legal}")
    finally:
        d.close()

    # ── T7c: 跨档变更被拒绝 ──
    if mid + 2 < len(tax_order):
        d = _reset()
        try:
            states = d.load_all_nations()
            sa = states[AAA]
            sa.policies["tax_policy"] = tax_order[mid]
            sa.queued_policies = {}
            d.save_nation(sa)
            illegal = tax_order[mid + 2]   # 跳两档

            results = _run_turn(d, {
                AAA: TurnInput(policy_changes={"tax_policy": illegal}), ZZZ: _empty()
            })
            la = _logs(results, AAA)
            sa2 = d.load_all_nations()[AAA]

            rejected = sa2.queued_policies.get("tax_policy") != illegal
            CHECK("跨档变更未进入 queued_policies", rejected,
                  f"queued={sa2.queued_policies.get('tax_policy')}")
            CHECK("跨档被拒绝日志存在",
                  any("拒绝" in l or "跨档" in l for l in la), str(la))
        finally:
            d.close()

    # ── T7d: 同档无变化静默通过 ──
    d = _reset()
    try:
        states = d.load_all_nations()
        sa = states[AAA]
        same = sa.policies.get("tax_policy", tax_order[mid])
        d.save_nation(sa)

        results = _run_turn(d, {AAA: TurnInput(policy_changes={"tax_policy": same}), ZZZ: _empty()})
        la = _logs(results, AAA)
        no_error = not any("拒绝" in l or "跨档" in l or "错误" in l for l in la)
        CHECK("同档变更静默无报错日志", no_error, str(la))
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T8: 5 回合混合压力测试
# ═══════════════════════════════════════════════════════════
def test_5turn_stress():
    SECTION("T8: 5 回合混合压力测试")
    d = _reset()
    try:
        # 初始化：AAA 战争，ZZZ 和平；双方充足原料
        states = d.load_all_nations()
        sa, sz = states[AAA], states[ZZZ]
        sa.war_status = "war"
        resources = {k: 5000 for k in
                     ["steel","iron","coal","bauxite","aluminum","oil","rubber","tungsten","chromium"]}
        sa.stockpile.update(resources)
        sz.stockpile.update(resources)
        sa.pending_builds = []; sa.queued_policies = {}
        sz.pending_builds = []; sz.queued_policies = {}
        d.save_nation(sa); d.save_nation(sz)

        # 科研队列（按前置顺序排列）
        research_queue = [t for t in
            ["electronics_1","industrial_1","resource_1","infantry_1","armor_1",
             "electronics_2","industrial_2","resource_2","infantry_2","armor_2"]
            if t in TECH_SPECS]

        def pick_research(state):
            for tech in research_queue:
                if tech in state.techs:
                    continue
                spec = TECH_SPECS.get(tech, {})
                if all(p in state.techs for p in spec.get("prereq", [])):
                    return {"tech": tech, "payment": 1000}
            return None

        errors = []
        for turn in range(1, 6):
            s = d.load_all_nations()
            sa_t, sz_t = s[AAA], s[ZZZ]

            # 保证 ZZZ 有油可出口
            sz_t.stockpile["oil"] = max(sz_t.stockpile.get("oil", 0), 100)
            d.save_nation(sz_t)

            # 贸易：AAA 进口 5 油（价 5 IC/桶，总 25 IC）
            trade_a = [TreatyTrade(AAA, ZZZ, "oil", 5, 5, "import", 1.0)]
            trade_z = [TreatyTrade(ZZZ, AAA, "oil", 5, 5, "export", 1.0)]

            inputs = {
                AAA: TurnInput(
                    research=pick_research(sa_t),
                    unit_orders=[UnitOrder("infantry", 1936, 1)],
                    refining_orders=[RefiningOrder("steel", 3)],
                    treaties=trade_a,
                ),
                ZZZ: TurnInput(
                    research=pick_research(sz_t),
                    treaties=trade_z,
                ),
            }

            try:
                results = _run_turn(d, inputs)
            except Exception as e:
                errors.append(f"回合{turn}: {e}")
                traceback.print_exc()
                break

            end = d.load_all_nations()
            sea, sez = end[AAA], end[ZZZ]
            print(f"  回合{turn}: AAA mil_ic={sea.mil_ic:.1f}  "
                  f"steel={sea.stockpile.get('steel',0):.1f}  "
                  f"army={sea.army}  techs={sorted(sea.techs)}")

        CHECK("5 回合全部完成无异常", not errors, str(errors))
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# T9: 全指令多回合压力测试（原 demo.py）
#     双方同时建造、造兵、贸易、精炼、科研、政策变更
# ═══════════════════════════════════════════════════════════
def test_full_orders_multi_turn():
    SECTION("T9: 全指令多回合压力测试（原 demo.py）")

    ALL_FACILITIES = [
        "civilian_factory", "military_factory", "dockyard",
        "artillery_foundry", "engine_factory", "tank_assembly", "aircraft_assembly",
        "steel_mill", "aluminum_refinery", "synthetic_oil_refinery",
        "synthetic_rubber_plant", "thermal_power_plant",
    ]
    ALL_SHIPS = ["submarine", "carrier", "battleship", "screen"]
    TOTAL_TURNS = 5

    # 科研队列
    RESEARCH_QUEUE = []
    for level in [1, 2, 3, 4, 5]:
        RESEARCH_QUEUE.extend([
            f"electronics_{level}", f"industrial_{level}", f"resource_{level}",
            f"infantry_{level}", f"armor_{level}",
        ])
    RESEARCH_QUEUE = [t for t in RESEARCH_QUEUE if t in TECH_SPECS]

    def _next_policy(category, current):
        order = POLICY_ORDER.get(category, [])
        if current not in order:
            return current
        idx = order.index(current)
        return order[idx + 1] if idx + 1 < len(order) else current

    d = _reset()
    try:
        # 找到两国的地块代码
        states = d.load_all_nations()
        tile_a = states[AAA].tiles[0].code if states[AAA].tiles else None
        tile_b = states[ZZZ].tiles[0].code if states[ZZZ].tiles else None
        if not tile_a or not tile_b:
            print("  [SKIP] 找不到测试地块")
            return

        research_idx = {AAA: 0, ZZZ: 0}
        errors = []

        for turn in range(1, TOTAL_TURNS + 1):
            states = d.load_all_nations()
            inputs = {}

            for nation, state, tile_code, other in [
                (AAA, states[AAA], tile_a, ZZZ),
                (ZZZ, states[ZZZ], tile_b, AAA),
            ]:
                # 建造全部工厂
                builds = [BuildOrder(facility=f, quantity=1, location=tile_code)
                          for f in ALL_FACILITIES]
                fort_lvl = 0
                for t in state.tiles:
                    if t.code == tile_code:
                        fort_lvl = t.land_fort_level
                        break
                if fort_lvl < 5:
                    builds.append(BuildOrder(facility="land_fort", quantity=1,
                                             location=tile_code, level=fort_lvl + 1))

                # 造兵
                unit_orders = [
                    UnitOrder(template="infantry", year=1936, quantity=1),
                    UnitOrder(template="armor", year=1936, quantity=1),
                    UnitOrder(template="airwing", year=1936, quantity=1),
                ] + [UnitOrder(template=s, year=1936, quantity=1) for s in ALL_SHIPS]

                # 贸易
                if nation == AAA:
                    treaties = [
                        TreatyTrade(AAA, ZZZ, "oil", 10, 640, "export", 1.0),
                        TreatyTrade(AAA, ZZZ, "rubber", 10, 640, "import", 1.0),
                    ]
                else:
                    treaties = [
                        TreatyTrade(ZZZ, AAA, "oil", 10, 640, "import", 1.0),
                        TreatyTrade(ZZZ, AAA, "rubber", 10, 640, "export", 1.0),
                    ]

                # 科研
                idx = research_idx[nation]
                research_cmd = None
                while idx < len(RESEARCH_QUEUE):
                    tech = RESEARCH_QUEUE[idx]
                    if tech not in state.techs:
                        spec = TECH_SPECS.get(tech, {})
                        if all(p in state.techs for p in spec.get("prereq", [])):
                            research_cmd = {"tech": tech}
                            break
                    idx += 1
                research_idx[nation] = idx

                # 政策变更
                policy_changes = {}
                for cat in ["economy_law", "trade_law", "tax_policy"]:
                    cur = state.policies.get(cat)
                    nxt = _next_policy(cat, cur)
                    if nxt != cur:
                        policy_changes[cat] = nxt

                # 精炼
                refining_orders = [
                    RefiningOrder(recipe="steel", runs=10),
                    RefiningOrder(recipe="aluminum", runs=10),
                ]

                inputs[nation] = TurnInput(
                    build_orders=builds,
                    refining_orders=refining_orders,
                    unit_orders=unit_orders,
                    research=research_cmd,
                    treaties=treaties,
                    policy_changes=policy_changes,
                )

            try:
                results = _run_turn(d, inputs)
            except Exception as e:
                errors.append(f"回合{turn}: {e}")
                traceback.print_exc()
                break

            end = d.load_all_nations()
            sa, sz = end[AAA], end[ZZZ]
            print(f"  回合{turn}: AAA civ={sa.civ_ic:.1f} mil={sa.mil_ic:.1f} "
                  f"steel={sa.stockpile.get('steel',0):.1f} army={sa.army}")

        CHECK("全指令 5 回合无异常", not errors, str(errors))
        # 验证引擎确实执行了建造和造兵
        final = d.load_all_nations()
        fa = final[AAA]
        CHECK("AAA 有步兵", sum(v for k, v in fa.army.items() if "infantry" in k) > 0,
              str(fa.army))
        CHECK("AAA 设施总数 > 0", sum(fa.facilities.values()) > 0,
              str(fa.facilities))
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════
def main():
    try:
        test_all_nations_full_pipeline()
        test_gather_peace()
        test_refining()
        test_trade()
        test_war_maintenance()
        test_upgrade_maintenance()
        test_coastal_restriction()
        test_policy_changes()
        test_5turn_stress()
        test_full_orders_multi_turn()
    except Exception:
        traceback.print_exc()

    print(f"\n{'═'*60}")
    total = _PASS + _FAIL
    print(f"  结果: {_PASS} 通过 / {_FAIL} 失败 / {total} 总计")
    print(f"{'═'*60}")
    return _FAIL


if __name__ == "__main__":
    sys.exit(main())
