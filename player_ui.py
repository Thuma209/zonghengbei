import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# PyInstaller frozen exe: 以 exe 所在目录为项目根
if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Database.db_manager import DatabaseManager
from static.facilities import FACILITY_SPECS
from static.policies import POLICY_ORDER
from static.recipes import RECIPE_SPECS
from static.techs import TECH_SPECS
from static.units import UNIT_TEMPLATES
from utils.turn_json_pipeline import (
    PayloadValidationError,
    list_active_agreements,
    preview_turn_from_json_payload,
    run_turn_from_json_payload,
    save_json_file,
)
from phases.phase_05_research import get_available_level

# ─── 汉化映射表 ──────────────────────────────────────────
FACILITY_CN = {
    "civilian_factory": "民用工厂", "military_factory": "军用工厂", "dockyard": "船坞",
    "artillery_foundry": "火炮铸造厂", "engine_factory": "发动机工厂",
    "tank_assembly": "坦克装配厂", "aircraft_assembly": "飞机装配厂",
    "steel_mill": "炼钢厂", "aluminum_refinery": "炼铝厂",
    "synthetic_oil_refinery": "合成炼油厂", "synthetic_rubber_plant": "合成橡胶厂",
    "thermal_power_plant": "发电厂", "land_fort": "陆地要塞", "coastal_fort": "海岸要塞",
}
FACILITY_CN_REV = {v: k for k, v in FACILITY_CN.items()}

RESOURCE_CN = {
    "iron": "生铁", "coal": "煤炭", "bauxite": "铝土", "steel": "钢",
    "aluminum": "铝", "oil": "石油", "chromium": "铬", "tungsten": "钨", "rubber": "橡胶",
}
RESOURCE_CN_REV = {v: k for k, v in RESOURCE_CN.items()}

SPECIAL_CN = {"artillery": "火炮", "engine": "发动机", "tank": "坦克", "aircraft": "飞机"}

UNIT_CN = {
    "infantry": "步兵", "armor": "装甲", "airwing": "航空联队",
    "submarine": "潜艇", "carrier": "航母", "battleship": "战列舰", "screen": "护卫舰",
}
UNIT_CN_REV = {v: k for k, v in UNIT_CN.items()}

RECIPE_CN = {"steel": "炼钢", "aluminum": "炼铝", "oil": "合成石油", "rubber": "合成橡胶"}
RECIPE_CN_REV = {v: k for k, v in RECIPE_CN.items()}

TRADE_KIND_CN = {"resource": "资源", "military": "军事", "loan": "贷款"}
TRADE_KIND_CN_REV = {v: k for k, v in TRADE_KIND_CN.items()}

TRADE_SIDE_CN = {"import": "进口", "export": "出口"}
TRADE_SIDE_CN_REV = {v: k for k, v in TRADE_SIDE_CN.items()}

POLICY_CAT_CN = {"economy_law": "经济法案", "trade_law": "贸易法案", "tax_policy": "税收政策"}
POLICY_CN = {
    "isolationism": "孤立主义", "consumer_economy": "消费品经济",
    "civilian_economy": "民用经济", "early_mobilization": "前期动员",
    "partial_mobilization": "部分动员", "war_economy": "战时经济",
    "total_mobilization": "全面动员",
    "export_focus": "出口导向", "free_trade": "自由贸易",
    "trade_protection": "贸易保护", "closed_economy": "封闭经济",
    "minimum_tax": "最低税率", "low_tax": "低税率", "average_tax": "平均税率",
    "high_tax": "高税率", "maximum_tax": "最高税率",
}
POLICY_CN_REV = {v: k for k, v in POLICY_CN.items()}

TECH_CN = {}
_TECH_CAT_CN = {
    "industrial": "工业科技", "resource": "资源科技", "electronics": "电子学",
    "infantry": "步兵科技", "armor": "装甲科技", "aircraft": "空军科技",
    "submarine": "潜艇科技", "carrier": "航母科技", "battleship": "战列舰科技", "screen": "护卫舰科技",
}
for _tk in TECH_SPECS:
    _parts = _tk.rsplit("_", 1)
    _cat, _lvl = _parts[0], _parts[1] if len(_parts) > 1 else ""
    TECH_CN[_tk] = f"{_TECH_CAT_CN.get(_cat, _cat)} Lv.{_lvl}"
TECH_CN_REV = {v: k for k, v in TECH_CN.items()}


def _cn(mapping, key):
    return mapping.get(key, key)


# ─── 单位科技解锁映射 unit_type -> [(tech_key, year), ...] ───
UNIT_UNLOCK_MAP = {}
for _tkey, _tspec in TECH_SPECS.items():
    for _unlock in _tspec.get("unlocks", []):
        _parts = _unlock.rsplit("_", 1)
        if len(_parts) == 2:
            try:
                _utype, _uyear = _parts[0], int(_parts[1])
                UNIT_UNLOCK_MAP.setdefault(_utype, []).append((_tkey, _uyear))
            except ValueError:
                pass


def get_max_unit_year(unit_type_en: str, nation_techs: set) -> int:
    """返回该国已解锁的兵种最高年份，默认1936"""
    entries = UNIT_UNLOCK_MAP.get(unit_type_en, [])
    max_year = 1936
    for tech_key, year in entries:
        if tech_key in nation_techs:
            max_year = max(max_year, year)
    return max_year


# ─── 修正键汉化 ───
MODIFIER_CN = {
    "civ_output": "民用产出%", "mil_output": "军备产出%", "research_speed": "科研速度%",
    "resource_output": "资源开采%", "power_output": "发电%",
    "stability_delta": "稳定度", "war_support_delta": "战争支持",
    "military_facility_fixed": "军事设施固定加成", "artillery_tank_fixed": "炮/坦固定加成",
    "resource_factory_fixed": "资源厂固定加成", "consumer_goods_delta": "消费品系数",
    "special_output_fixed": "特殊产能（绝对加成）",
}


def _estimate_war_maintenance(state, research_tech: str = None):
    """计算本回合维护费，完全对齐 phase_07 逻辑：
    - 升级档（本回合研究对应军种科技）：陆20% / 海6% / 空10%（战时/和平均收）
    - 战时基础档：陆10% / 海3% / 空5%
    - 和平且非升级档：0
    返回: (mil_ic, nav_ic, resources: dict, special_cap: dict)
    """
    from static.units import SPECIAL_CAPACITIES
    from collections import defaultdict

    is_war = state.war_status == "war"

    # 本回合研究的科技会升级哪些军种
    upgraded_types: set[str] = set()
    if research_tech:
        spec = TECH_SPECS.get(research_tech, {})
        if not spec.get("skip_maintenance_upgrade", False):
            for unlock_key in spec.get("unlocks", []):
                upgraded_types.add(unlock_key.rsplit("_", 1)[0])

    total_mods = state.modifiers.total()
    reduce_land  = min(1.0, max(0.0, total_mods.get("maint_reduction_land",  0.0)))
    reduce_naval = min(1.0, max(0.0, total_mods.get("maint_reduction_naval", 0.0)))
    reduce_air   = min(1.0, max(0.0, total_mods.get("maint_reduction_air",   0.0)))

    mil_ic = 0.0
    nav_ic = 0.0
    res_maint = defaultdict(float)
    cap_maint = defaultdict(float)

    def _accum(unit_dict, ic_pool, base_rate, upgrade_rate, reduce):
        nonlocal mil_ic, nav_ic
        for unit_key, count in unit_dict.items():
            parts = unit_key.rsplit("_", 1)
            if len(parts) != 2:
                continue
            unit_type = parts[0]
            try:
                tpl = UNIT_TEMPLATES.get((unit_type, int(parts[1])))
            except ValueError:
                continue
            if not tpl:
                continue
            # 完全对齐 phase_07
            if unit_type in upgraded_types:
                rate = upgrade_rate
            elif is_war:
                rate = base_rate
            else:
                rate = 0.0
            if rate == 0.0:
                continue
            eff = rate * (1.0 - reduce)
            if ic_pool == "mil":
                mil_ic += tpl["ic_cost"] * count * eff
            else:
                nav_ic += tpl["ic_cost"] * count * eff
            for res, amt in tpl["resources"].items():
                total_r = amt * count * eff
                if res in SPECIAL_CAPACITIES:
                    cap_maint[res] += total_r
                else:
                    res_maint[res] += total_r

    _accum(state.army,     "mil", base_rate=0.10, upgrade_rate=0.20, reduce=reduce_land)
    _accum(state.navy,     "nav", base_rate=0.03, upgrade_rate=0.06, reduce=reduce_naval)
    _accum(state.airforce, "mil", base_rate=0.05, upgrade_rate=0.10, reduce=reduce_air)

    # 战时石油消耗（与 phase_07 一致，仅战时）
    if is_war:
        oil = 0.0
        for unit_key, count in state.army.items():
            if "armor" in unit_key or unit_key.startswith("infantry_1945"):
                oil += count * 2.5
        for unit_key, count in state.navy.items():
            if "battleship" in unit_key:  oil += count * 1.0
            elif "carrier"  in unit_key:  oil += count * 0.8
            elif "screen"   in unit_key:  oil += count * 0.15
            elif "submarine" in unit_key: oil += count * 0.1
        for unit_key, count in state.airforce.items():
            if "airwing" in unit_key:     oil += count * 0.2
        if oil > 0:
            res_maint["oil"] += oil

    return mil_ic, nav_ic, dict(res_maint), dict(cap_maint)


def _projected_ic(state):
    """计算本回合预计可用IC（上轮剩余+本轮工厂产出，含所有修正），不修改原始state"""
    import copy
    from phases.phase_01_apply_queued import apply as _apply_queued
    from phases.phase_02_gather import apply as _gather
    tmp = copy.deepcopy(state)
    tmp.temp = {"logs": []}
    _apply_queued(tmp)   # 先应用排队政策，确保 modifier 基于最新政策计算
    _gather(tmp)
    return tmp.temp["civ_ic"], tmp.temp["mil_ic"], tmp.temp["nav_ic"]


def _effective_facilities(state) -> dict:
    """按占领系数折算的有效工厂数量（核心=1.0，占领=0.5），从 tiles 汇总。"""
    result: dict[str, float] = {}
    for tile in state.tiles:
        occ_coeff = 1.0 if tile.occupation_type in ("核心", "core") else 0.5
        for fac, count in tile.factories.items():
            result[fac] = result.get(fac, 0.0) + count * occ_coeff
    return result


def _localize_preview_cn(result: dict) -> str:
    """将 preview_turn_from_json_payload 返回的 dict 格式化为中文可读文本"""
    lines = []
    if not result.get("ok"):
        lines.append("【预估失败】")
        return "\n".join(lines)

    warnings = result.get("warnings", [])
    if warnings:
        lines.append("【警告】")
        for w in warnings:
            lines.append(f"  ⚠ {w}")
        lines.append("")

    preview = result.get("preview", {})
    if not preview:
        return "\n".join(lines) or "(无数据)"

    nation = preview.get("nation", "")
    lines.append(f"=== 沙盒预估结果：{nation} ===")
    lines.append(f"年份：{preview.get('year_before')} → {preview.get('year_after')}")
    lines.append("")

    ic = preview.get("ic_delta", {})
    ic_lines = []
    if abs(ic.get("civ_ic", 0)) > 1e-6:
        ic_lines.append(f"  民用IC: {ic['civ_ic']:+.2f}")
    if abs(ic.get("mil_ic", 0)) > 1e-6:
        ic_lines.append(f"  军用IC: {ic['mil_ic']:+.2f}")
    if abs(ic.get("nav_ic", 0)) > 1e-6:
        ic_lines.append(f"  船坞IC: {ic['nav_ic']:+.2f}")
    if ic_lines:
        lines.append("[IC变化]")
        lines.extend(ic_lines)
        lines.append("")

    stock_delta = preview.get("stockpile_delta", {})
    if stock_delta:
        lines.append("[库存变化]")
        for k, v in sorted(stock_delta.items()):
            lines.append(f"  {_cn(RESOURCE_CN, k)}: {v:+.2f}")
        lines.append("")

    fac_delta = preview.get("facilities_delta", {})
    if fac_delta:
        lines.append("[设施变化]")
        for k, v in sorted(fac_delta.items()):
            lines.append(f"  {_cn(FACILITY_CN, k)}: {v:+.0f}")
        lines.append("")

    army_delta = preview.get("army_delta", {})
    if army_delta:
        lines.append("[陆军产出]")
        for k, v in sorted(army_delta.items()):
            lines.append(f"  {k}: {v:+.2f}")
        lines.append("")

    navy_delta = preview.get("navy_delta", {})
    if navy_delta:
        lines.append("[海军产出]")
        for k, v in sorted(navy_delta.items()):
            lines.append(f"  {k}: {v:+.2f}")
        lines.append("")

    airforce_delta = preview.get("airforce_delta", {})
    if airforce_delta:
        lines.append("[空军产出]")
        for k, v in sorted(airforce_delta.items()):
            lines.append(f"  {k}: {v:+.2f}")
        lines.append("")

    rsd = preview.get("research_stockpile_delta", 0)
    if abs(rsd) > 1e-6:
        lines.append(f"[科研槽变化]  {rsd:+.0f} IC")
        lines.append("")

    techs_added = preview.get("techs_added", [])
    if techs_added:
        lines.append("[本回合完成科技]")
        for t in techs_added:
            lines.append(f"  ✓ {_cn(TECH_CN, t)}")
        lines.append("")

    qp = preview.get("queued_policies", {})
    if qp:
        lines.append("[排队政策]")
        for cat, val in sorted(qp.items()):
            lines.append(f"  {_cn(POLICY_CAT_CN, cat)}: {_cn(POLICY_CN, val)}")
        lines.append("")

    logs = preview.get("logs", [])
    if logs:
        lines.append("[运行日志]")
        for log in logs:
            lines.append(f"  {log}")

    return "\n".join(lines)


def _localize_run_result_cn(result: dict) -> str:
    """将 run_turn_from_json_payload 返回的 dict 格式化为中文可读文本"""
    lines = []
    if not result.get("ok"):
        lines.append("【推演失败】")
        return "\n".join(lines)

    warnings = result.get("warnings", [])
    if warnings:
        lines.append("【警告】")
        for w in warnings:
            lines.append(f"  ⚠ {w}")
        lines.append("")

    lines.append("=== 推演完成，数据已写入 ===")
    lines.append("")

    results = result.get("results", {})
    for nation, nr in sorted(results.items()):
        logs = nr.get("logs", []) if isinstance(nr, dict) else []
        if logs:
            lines.append(f"[{nation} 运行日志]")
            for log in logs:
                lines.append(f"  {log}")
            lines.append("")

    snapshot = result.get("snapshot", {})
    for nation, snap in sorted(snapshot.items()):
        lines.append(f"[{nation} 推演后状态]")
        lines.append(f"  年份: {snap.get('year')}")
        lines.append(f"  民用IC: {float(snap.get('civ_ic', 0)):.2f}")
        lines.append(f"  军用IC: {float(snap.get('mil_ic', 0)):.2f}")
        lines.append(f"  船坞IC: {float(snap.get('nav_ic', 0)):.2f}")
        lines.append(f"  稳定度: {float(snap.get('stability', 0)):.2f}")
        lines.append(f"  战争支持: {float(snap.get('war_support', 0)):.2f}")
        stockpile = snap.get("stockpile", {})
        if stockpile:
            lines.append("  库存:")
            for k, v in sorted(stockpile.items()):
                if abs(float(v)) > 1e-6:
                    lines.append(f"    {_cn(RESOURCE_CN, k)}: {float(v):.2f}")
        techs = snap.get("techs", [])
        if techs:
            lines.append(f"  已研科技: {', '.join(_cn(TECH_CN, t) for t in sorted(techs))}")
        lines.append("")

    return "\n".join(lines)


class PlayerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("经济指令面板")
        self.geometry("1380x860")

        self.db_path_var = tk.StringVar(value=os.path.join(PROJECT_ROOT, "Database", "game.db"))
        self.nation_var = tk.StringVar(value="")
        self.turn_var = tk.IntVar(value=1)

        self.current_state = None
        self.states_cache = {}

        self.trade_orders = []
        self.refining_orders = []
        self.build_orders = []
        self.unit_orders = []
        self.research_cmd = None

        self.sheet_frames = {}
        self._active_sheet = "trade"

        self._build_layout()
        self.refresh_states()

    def _build_layout(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Button(top, text="📂 导入Excel", command=self.import_excel).pack(side="left", padx=3)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(top, text="国家代码:").pack(side="left", padx=(4, 2))
        self.nation_combo = ttk.Combobox(top, textvariable=self.nation_var, width=12, state="readonly")
        self.nation_combo.pack(side="left")
        self.nation_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_nation_changed())

        ttk.Label(top, text="回合:").pack(side="left", padx=(14, 2))
        ttk.Spinbox(top, from_=1, to=999, textvariable=self.turn_var, width=6).pack(side="left")

        ttk.Button(top, text="刷新状态", command=self.refresh_states).pack(side="left", padx=8)
        ttk.Button(top, text="沙盒预估", command=self.preview_turn).pack(side="left", padx=3)
        ttk.Button(top, text="导出JSON", command=self.export_json).pack(side="left", padx=3)
        ttk.Button(top, text="提交推演", command=self.run_once).pack(side="left", padx=3)

        sheet_bar = tk.Frame(self, bg="#ecf0f1")
        sheet_bar.pack(fill="x", padx=8, pady=(4, 0))
        self.sheet_buttons = {}
        _tab_labels = [
            ("trade", "📊 贸易与资源"),
            ("civil", "🏗 民用建设"),
            ("mil", "⚔ 军事生产"),
            ("internal", "📋 内政与科研"),
        ]
        for key, label in _tab_labels:
            btn = tk.Button(
                sheet_bar, text=label, relief="flat", bd=0,
                font=("Microsoft YaHei", 10), cursor="hand2",
                bg="#ecf0f1", fg="#566573", activebackground="#d5dbdb",
                command=lambda k=key: self.show_sheet(k),
            )
            btn.pack(side="left", padx=2, pady=4, ipadx=12, ipady=4)
            self.sheet_buttons[key] = btn

        # ── 内容区 + 日志区：竖向可拖动分割 ──────────────────────────
        paned = tk.PanedWindow(self, orient="vertical", sashwidth=6,
                               sashrelief="flat", bg="#bdc3c7", bd=0)
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        content = ttk.Frame(paned)
        paned.add(content, stretch="always", minsize=300)
        self.content = content

        self.sheet_frames["trade"] = self._build_trade_sheet(content)
        self.sheet_frames["civil"] = self._build_civil_sheet(content)
        self.sheet_frames["mil"] = self._build_military_sheet(content)
        self.sheet_frames["internal"] = self._build_internal_sheet(content)

        for frame in self.sheet_frames.values():
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        log_frame = ttk.LabelFrame(paned, text="预估 / 日志")
        paned.add(log_frame, stretch="never", minsize=60)
        self.output_text = tk.Text(log_frame, height=7)
        sb = ttk.Scrollbar(log_frame, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.output_text.pack(fill="both", expand=True)
        self._setup_text_widget(self.output_text)

        self.show_sheet("trade")

    def _build_trade_sheet(self, parent):
        frame = ttk.Frame(parent)

        left = ttk.Frame(frame)
        left.pack(side="left", fill="both", expand=True)

        form = ttk.LabelFrame(left, text="贸易协定")
        form.pack(fill="x", pady=4)

        self.trade_kind_var = tk.StringVar(value="资源")
        self.trade_side_var = tk.StringVar(value="进口")
        self.trade_partner_var = tk.StringVar()
        self.trade_resource_var = tk.StringVar(value="钢")
        self.trade_qty_var = tk.StringVar(value="10")
        self.trade_price_var = tk.StringVar(value="640")
        self.trade_note_var = tk.StringVar()
        self.trade_recurring_var = tk.BooleanVar(value=True)
        self.trade_unit_template_var = tk.StringVar(value="步兵")
        self.trade_unit_year_var = tk.StringVar(value="1936")
        self.trade_principal_var = tk.StringVar(value="1000")
        self.trade_interest_var = tk.StringVar(value="0.05")
        self.trade_turns_var = tk.StringVar(value="4")

        row1 = ttk.Frame(form)
        row1.pack(fill="x", padx=6, pady=4)
        ttk.Label(row1, text="类型").pack(side="left")
        ttk.Combobox(row1, width=10, textvariable=self.trade_kind_var, state="readonly",
                     values=list(TRADE_KIND_CN.values())).pack(side="left", padx=3)
        ttk.Label(row1, text="方向").pack(side="left", padx=(10, 0))
        ttk.Combobox(row1, width=10, textvariable=self.trade_side_var, state="readonly",
                     values=list(TRADE_SIDE_CN.values())).pack(side="left", padx=3)
        ttk.Label(row1, text="对象国").pack(side="left", padx=(10, 0))
        ttk.Entry(row1, textvariable=self.trade_partner_var, width=10).pack(side="left", padx=3)
        ttk.Checkbutton(row1, text="长期协定", variable=self.trade_recurring_var).pack(side="left", padx=(10, 0))

        row2 = ttk.Frame(form)
        row2.pack(fill="x", padx=6, pady=4)
        ttk.Label(row2, text="资源").pack(side="left")
        ttk.Combobox(row2, width=12, textvariable=self.trade_resource_var,
                     values=list(RESOURCE_CN.values())).pack(side="left", padx=3)
        ttk.Label(row2, text="数量").pack(side="left", padx=(10, 0))
        ttk.Entry(row2, textvariable=self.trade_qty_var, width=10).pack(side="left", padx=3)
        ttk.Label(row2, text="单价").pack(side="left", padx=(10, 0))
        ttk.Entry(row2, textvariable=self.trade_price_var, width=10).pack(side="left", padx=3)
        ttk.Label(row2, text="备注").pack(side="left", padx=(10, 0))
        ttk.Entry(row2, textvariable=self.trade_note_var, width=18).pack(side="left", padx=3)
        ttk.Button(row2, text="添加贸易", command=self.add_trade_order).pack(side="left", padx=8)
        ttk.Button(row2, text="删除选中", command=self.remove_trade_order).pack(side="left", padx=4)

        row3 = ttk.Frame(form)
        row3.pack(fill="x", padx=6, pady=4)
        ttk.Label(row3, text="军队模板").pack(side="left")
        unit_names = [_cn(UNIT_CN, t) for t in sorted(set(t for t, _y in UNIT_TEMPLATES.keys()))]
        trade_unit_combo = ttk.Combobox(row3, width=10, textvariable=self.trade_unit_template_var,
                     values=unit_names)
        trade_unit_combo.pack(side="left", padx=3)
        self._trade_unit_year_auto = 1936
        trade_unit_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_trade_unit_year())
        ttk.Label(row3, text="贷款本金").pack(side="left", padx=(8, 0))
        ttk.Entry(row3, textvariable=self.trade_principal_var, width=10).pack(side="left", padx=3)
        ttk.Label(row3, text="利率").pack(side="left", padx=(6, 0))
        ttk.Entry(row3, textvariable=self.trade_interest_var, width=7).pack(side="left", padx=3)
        ttk.Label(row3, text="期限(回合)").pack(side="left", padx=(6, 0))
        ttk.Entry(row3, textvariable=self.trade_turns_var, width=6).pack(side="left", padx=3)

        self.trade_list = tk.Listbox(left, height=9)
        self.trade_list.pack(fill="both", expand=True, pady=4)

        refine = ttk.LabelFrame(left, text="精炼指令")
        refine.pack(fill="x", pady=4)

        self.refine_recipe_var = tk.StringVar(value="炼钢")
        self.refine_runs_var = tk.StringVar(value="1")
        self.refine_chromium_var = tk.StringVar(value="0")

        rr = ttk.Frame(refine)
        rr.pack(fill="x", padx=6, pady=5)
        ttk.Label(rr, text="配方").pack(side="left")
        ttk.Combobox(rr, textvariable=self.refine_recipe_var,
                     values=[_cn(RECIPE_CN, k) for k in RECIPE_SPECS],
                     width=14, state="readonly").pack(side="left", padx=3)
        ttk.Label(rr, text="次数").pack(side="left", padx=(10, 0))
        ttk.Entry(rr, textvariable=self.refine_runs_var, width=10).pack(side="left", padx=3)
        ttk.Label(rr, text="铬加成").pack(side="left", padx=(10, 0))
        ttk.Entry(rr, textvariable=self.refine_chromium_var, width=10).pack(side="left", padx=3)
        ttk.Button(rr, text="添加精炼", command=self.add_refining_order).pack(side="left", padx=8)
        ttk.Button(rr, text="删除选中", command=self.remove_refining_order).pack(side="left", padx=4)

        self.refine_info_label = ttk.Label(refine, text="", foreground="blue")
        self.refine_info_label.pack(fill="x", padx=6, pady=(0, 4))

        self.refining_list = tk.Listbox(left, height=7)
        self.refining_list.pack(fill="both", expand=True, pady=4)

        right = ttk.Frame(frame)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        agr = ttk.LabelFrame(right, text="当前协定")
        agr.pack(fill="x", pady=4)
        self.active_agreement_list = tk.Listbox(agr, height=8)
        self.active_agreement_list.pack(fill="x", padx=4, pady=4)
        arow = ttk.Frame(agr)
        arow.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(arow, text="刷新协定", command=self.refresh_active_agreements).pack(side="left", padx=2)
        ttk.Button(arow, text="加入取消队列", command=self.queue_cancel_selected_agreement).pack(side="left", padx=2)

        self.trade_summary = tk.Text(right, height=30)
        self.trade_summary.pack(fill="both", expand=True)
        self._setup_text_widget(self.trade_summary)

        return frame

    def _build_civil_sheet(self, parent):
        frame = ttk.Frame(parent)

        form = ttk.LabelFrame(frame, text="建造指令")
        form.pack(fill="x", pady=4)

        fac_cn_list = [_cn(FACILITY_CN, k) for k in list(FACILITY_SPECS.keys()) + ["land_fort", "coastal_fort"]]
        self.build_facility_var = tk.StringVar(value="民用工厂")
        self.build_location_var = tk.StringVar()
        self.build_qty_var = tk.StringVar(value="1")
        self.build_level_var = tk.StringVar(value="1")

        row = ttk.Frame(form)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Label(row, text="设施类型").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self.build_facility_var,
            values=fac_cn_list,
            width=20,
            state="readonly",
        ).pack(side="left", padx=3)
        ttk.Label(row, text="地块代码").pack(side="left", padx=(10, 0))
        ttk.Entry(row, textvariable=self.build_location_var, width=12).pack(side="left", padx=3)
        ttk.Label(row, text="数量").pack(side="left", padx=(10, 0))
        ttk.Entry(row, textvariable=self.build_qty_var, width=8).pack(side="left", padx=3)
        ttk.Label(row, text="等级(要塞)").pack(side="left", padx=(10, 0))
        ttk.Entry(row, textvariable=self.build_level_var, width=8).pack(side="left", padx=3)
        ttk.Button(row, text="添加建造", command=self.add_build_order).pack(side="left", padx=8)
        ttk.Button(row, text="删除选中", command=self.remove_build_order).pack(side="left", padx=4)

        self.build_list = tk.Listbox(frame, height=13)
        self.build_list.pack(fill="both", expand=True, pady=5)

        self.civil_summary = tk.Text(frame, height=14)
        self.civil_summary.pack(fill="both", expand=True)
        self._setup_text_widget(self.civil_summary)
        return frame

    def _build_military_sheet(self, parent):
        frame = ttk.Frame(parent)

        form = ttk.LabelFrame(frame, text="生产指令")
        form.pack(fill="x", pady=4)

        templates_en = sorted(set(t for t, _y in UNIT_TEMPLATES.keys()))
        templates_cn = [_cn(UNIT_CN, t) for t in templates_en]
        self.unit_template_var = tk.StringVar(value=templates_cn[0])
        self.unit_qty_var = tk.StringVar(value="1")
        self._unit_year_auto = 1936  # auto-computed, not editable

        row = ttk.Frame(form)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Label(row, text="模板").pack(side="left")
        unit_combo = ttk.Combobox(row, textvariable=self.unit_template_var, values=templates_cn,
                                   width=14, state="readonly")
        unit_combo.pack(side="left", padx=3)
        ttk.Label(row, text="数量").pack(side="left", padx=(10, 0))
        ttk.Entry(row, textvariable=self.unit_qty_var, width=10).pack(side="left", padx=3)
        ttk.Button(row, text="添加单位", command=self.add_unit_order).pack(side="left", padx=8)
        ttk.Button(row, text="删除选中", command=self.remove_unit_order).pack(side="left", padx=4)

        unit_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_unit_year())

        self.unit_list = tk.Listbox(frame, height=13)
        self.unit_list.pack(fill="both", expand=True, pady=5)

        self.military_summary = tk.Text(frame, height=14)
        self.military_summary.pack(fill="both", expand=True)
        self._setup_text_widget(self.military_summary)
        return frame

    def _build_internal_sheet(self, parent):
        frame = ttk.Frame(parent)

        pol = ttk.LabelFrame(frame, text="政策变更")
        pol.pack(fill="x", pady=4)

        self.policy_vars = {}
        for cat in ["economy_law", "trade_law", "tax_policy"]:
            row = ttk.Frame(pol)
            row.pack(fill="x", padx=6, pady=4)
            ttk.Label(row, text=POLICY_CAT_CN.get(cat, cat), width=18).pack(side="left")
            var = tk.StringVar(value="")
            self.policy_vars[cat] = var
            cn_options = [_cn(POLICY_CN, p) for p in POLICY_ORDER[cat]]
            ttk.Combobox(row, textvariable=var, values=cn_options, width=24, state="readonly").pack(side="left", padx=4)

        rs = ttk.LabelFrame(frame, text="科研")
        rs.pack(fill="x", pady=4)

        tech_cn_list = [_cn(TECH_CN, t) for t in sorted(TECH_SPECS.keys())]
        self.research_tech_var = tk.StringVar(value=tech_cn_list[0])

        rr = ttk.Frame(rs)
        rr.pack(fill="x", padx=6, pady=6)
        ttk.Label(rr, text="科技").pack(side="left")
        ttk.Combobox(rr, textvariable=self.research_tech_var, values=tech_cn_list,
                     width=24, state="readonly").pack(side="left", padx=4)
        self.research_cost_label = ttk.Label(rr, text="")
        self.research_cost_label.pack(side="left", padx=(10, 0))
        ttk.Button(rr, text="设定科研", command=self.set_research).pack(side="left", padx=8)
        ttk.Button(rr, text="清除科研", command=self.clear_research).pack(side="left", padx=3)

        rs_speed_row = ttk.Frame(rs)
        rs_speed_row.pack(fill="x", padx=6, pady=(0, 4))
        self.research_speed_label = ttk.Label(rs_speed_row, text="科研速度：加载中...", foreground="gray")
        self.research_speed_label.pack(side="left")

        def _on_tech_changed(*_args):
            tech_cn = self.research_tech_var.get()
            tech_en = TECH_CN_REV.get(tech_cn, tech_cn)
            spec = TECH_SPECS.get(tech_en)
            if not spec:
                self.research_cost_label.config(text="")
                return
            base = spec["cost"]
            # 计算超前惩罚
            if self.current_state:
                year = self.current_state.year
                already = tech_en in self.current_state.techs
            else:
                year = 1936
                already = False
            tech_level = int(tech_en.rsplit("_", 1)[-1]) if tech_en.rsplit("_", 1)[-1].isdigit() else 1
            available = get_available_level(year)
            ahead = max(0, tech_level - available)
            ahead_cost = int(base * (5 ** ahead))
            # 科研速度负加成 → 费用增加
            rspeed = 0.0
            if self.current_state:
                rspeed = self.current_state.modifiers.total().get("research_speed", 0.0)
            if rspeed < 0:
                actual = int(math.ceil(ahead_cost * (1 - rspeed) - 1e-9))
            else:
                actual = ahead_cost
            if already:
                self.research_cost_label.config(text="[已研究]", foreground="gray")
            elif ahead > 0 and rspeed < 0:
                self.research_cost_label.config(
                    text=f"基础 {base} IC → 超前{ahead}级 {ahead_cost} IC → 科研速度{rspeed*100:+.0f}% → 实际 {actual} IC",
                    foreground="red")
            elif ahead > 0:
                self.research_cost_label.config(
                    text=f"基础 {base} IC → 超前{ahead}级 → 实际 {actual} IC",
                    foreground="red")
            elif rspeed < 0:
                self.research_cost_label.config(
                    text=f"基础 {base} IC → 科研速度{rspeed*100:+.0f}% → 实际 {actual} IC",
                    foreground="red")
            else:
                self.research_cost_label.config(text=f"费用: {actual} IC", foreground="black")
        self.research_tech_var.trace_add("write", _on_tech_changed)
        _on_tech_changed()

        self.internal_summary = tk.Text(frame, height=28)
        self.internal_summary.pack(fill="both", expand=True)
        self._setup_text_widget(self.internal_summary)
        return frame

    # ── 文本格式化辅助 ────────────────────────────────────────────────
    def _setup_text_widget(self, widget):
        """为 Text 控件配置字体和格式化标签"""
        widget.configure(
            font=("Microsoft YaHei", 10), padx=10, pady=8,
            spacing1=1, spacing3=1, relief="flat", bd=1,
            bg="#fdfefe", selectbackground="#aed6f1",
        )
        widget.tag_configure("header",  font=("Microsoft YaHei", 12, "bold"), foreground="#1a5276", spacing1=6, spacing3=4)
        widget.tag_configure("section", font=("Microsoft YaHei", 10, "bold"), foreground="#2874a6", spacing1=6, spacing3=2)
        widget.tag_configure("warn",    font=("Microsoft YaHei", 10, "bold"), foreground="#c0392b")
        widget.tag_configure("good",    foreground="#1e8449", font=("Microsoft YaHei", 10, "bold"))
        widget.tag_configure("dim",     foreground="#95a5a6", font=("Microsoft YaHei", 9))
        widget.tag_configure("key",     foreground="#5d6d7e")
        widget.tag_configure("val_pos", foreground="#1e8449", font=("Microsoft YaHei", 10, "bold"))
        widget.tag_configure("val_neg", foreground="#c0392b", font=("Microsoft YaHei", 10, "bold"))
        widget.tag_configure("sep",     foreground="#d5dbdb")
        widget.tag_configure("highlight", background="#eaf2f8", font=("Microsoft YaHei", 10, "bold"))

    def _format_text(self, widget):
        """扫描 Text 内容并自动应用格式化标签"""
        import re
        content = widget.get("1.0", "end-1c")
        for i, line in enumerate(content.split("\n"), 1):
            ls, le = f"{i}.0", f"{i}.end"
            s = line.strip()
            if not s:
                continue
            # 大标题  ===...
            if s.startswith("==="):
                widget.tag_add("header", ls, le)
            # 分节  [...]
            elif s.startswith("[") and "]" in s and not s.startswith("[已"):
                widget.tag_add("section", ls, le)
            # 分隔线  ─
            elif s.startswith("─"):
                widget.tag_add("sep", ls, le)
            # 警告
            elif "⚠" in s:
                widget.tag_add("warn", ls, le)
            # 来源明细  └
            elif s.startswith("└") or s.startswith("▪"):
                widget.tag_add("dim", ls, le)
            # 顶层 key: value 行
            elif ":" in s and not s.startswith(" "):
                colon = line.index(":")
                widget.tag_add("key", ls, f"{i}.{colon + 1}")
            # 缩进数值行: 含 +/- 数字
            elif s.startswith(" "):
                m_pos = re.search(r'\+\d', line)
                m_neg = re.search(r'-\d', line)
                if m_pos:
                    widget.tag_add("val_pos", f"{i}.{m_pos.start()}", le)
                elif m_neg:
                    widget.tag_add("val_neg", f"{i}.{m_neg.start()}", le)

    def show_sheet(self, key):
        self._active_sheet = key
        for k, frame in self.sheet_frames.items():
            if k == key:
                frame.lift()
        for k, btn in self.sheet_buttons.items():
            if k == key:
                btn.configure(bg="#2874a6", fg="white", relief="solid", bd=1)
            else:
                btn.configure(bg="#ecf0f1", fg="#566573", relief="flat", bd=0)

    def pick_db(self):
        path = filedialog.askopenfilename(
            title="选择 game.db",
            filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*.*")],

            initialdir=os.path.dirname(self.db_path_var.get() or PROJECT_ROOT),
        )
        if path:
            self.db_path_var.set(path)
            self.refresh_states()

        def import_excel(self):
                    """从单国 Excel 导入数据到本地 game.db（自动识别国家，不校验当前选中）"""
        xlsx = filedialog.askopenfilename(
            title="选择你的国家 Excel 文件",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
            initialdir=PROJECT_ROOT,
        )
        if not xlsx:
            return

        from Database.excel_io import import_nation_excel
        db_path = self.db_path_var.get().strip()
        try:
            code, n_tiles, n_agr = import_nation_excel(xlsx, db_path)
            messagebox.showinfo(
                "导入成功",
                f"国家 {code}：{n_tiles} 个地块，{n_agr} 条协议\n"
                f"数据库：{db_path}",
            )
            self.refresh_states()
            # 自动选中新导入的国家
            if code in self.states_cache:
                self.nation_var.set(code)
                self.on_nation_changed()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def export_excel(self):
        """将当前国家数据从 game.db 导出到 Excel。"""
        code = self.nation_var.get()
        if not code:
            messagebox.showwarning("提示", "请先选择一个国家")
            return
        xlsx = filedialog.asksaveasfilename(
            title="导出 Excel",
            defaultextension=".xlsx",
            initialfile=f"{code}.xlsx",
            filetypes=[("Excel 文件", "*.xlsx")],
            initialdir=PROJECT_ROOT,
        )
        if not xlsx:
            return
        from Database.excel_io import export_nation_excel
        db_path = self.db_path_var.get().strip()
        try:
            export_nation_excel(db_path, xlsx, code)
            messagebox.showinfo("导出成功", f"已导出到：{xlsx}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

        def refresh_states(self):
            db_path = self.db_path_var.get().strip()
        if not db_path or not os.path.exists(db_path):
            self.nation_combo["values"] = []
            self.nation_var.set("")
            self.current_state = None
            self._clear_summaries()
            return

        db = DatabaseManager(db_path)
        try:
            self.states_cache = db.load_all_nations()
            import static.spirits as _spirits
            _spirits.reload_from_db(db)
        finally:
            db.close()

        # 显示所有存在的国家（无论是否为玩家国）
        codes = sorted(self.states_cache.keys())
        self.nation_combo["values"] = codes

        if codes:
            cur = self.nation_var.get()
            if cur not in codes:
                self.nation_var.set(codes[0])
        else:
            self.nation_var.set("")
            self.current_state = None
            self._clear_summaries()

        self.on_nation_changed()

    def on_nation_changed(self):
        code = self.nation_var.get()
        self.current_state = self.states_cache.get(code)
        if not self.current_state:
            return

        # 重算策政/稳定度/精神/科技修正
        from utils.modifiers import (compute_policy_modifiers, compute_stability_modifiers,
                                     compute_spirit_modifiers, compute_tech_modifiers)
        self.current_state.modifiers.policy    = compute_policy_modifiers(self.current_state.policies)
        self.current_state.modifiers.stability = compute_stability_modifiers(self.current_state.stability)
        self.current_state.modifiers.spirit    = compute_spirit_modifiers(self.current_state.spirits)
        self.current_state.modifiers.tech      = compute_tech_modifiers(self.current_state.techs)

        for cat, var in self.policy_vars.items():
            en_val = self.current_state.policies.get(cat, "")
            var.set(_cn(POLICY_CN, en_val))

        self._update_unit_year()
        self._update_trade_unit_year()
        self.refresh_active_agreements()
        self.refresh_summaries()

    def _update_unit_year(self):
        """根据当前国家科技，自动计算军事生产页的兵种年份"""
        if not self.current_state:
            return
        tmpl_cn = self.unit_template_var.get()
        tmpl_en = UNIT_CN_REV.get(tmpl_cn, tmpl_cn)
        year = get_max_unit_year(tmpl_en, self.current_state.techs)
        self._unit_year_auto = year

    def _update_trade_unit_year(self):
        """根据当前国家科技，自动计算贸易页军队模板年份"""
        if not self.current_state:
            return
        tmpl_cn = self.trade_unit_template_var.get()
        tmpl_en = UNIT_CN_REV.get(tmpl_cn, tmpl_cn)
        year = get_max_unit_year(tmpl_en, self.current_state.techs)
        self._trade_unit_year_auto = year

    def _get_own_tile_codes(self):
        if not self.current_state:
            return set()
        return {t.code for t in self.current_state.tiles}

    def add_trade_order(self):
        try:
            kind_cn = self.trade_kind_var.get()
            kind = TRADE_KIND_CN_REV.get(kind_cn, kind_cn)
            side_cn = self.trade_side_var.get()
            side = TRADE_SIDE_CN_REV.get(side_cn, side_cn)
            res_cn = self.trade_resource_var.get()
            resource = RESOURCE_CN_REV.get(res_cn, res_cn)
            unit_cn = self.trade_unit_template_var.get()
            unit_template = UNIT_CN_REV.get(unit_cn, unit_cn)

            item = {
                "action": "submit",
                "kind": kind,
                "nation": self.nation_var.get(),
                "partner": self.trade_partner_var.get().strip(),
                "side": side,
                "resource": resource,
                "quantity": float(self.trade_qty_var.get()),
                "price_per_unit": float(self.trade_price_var.get()),
                "note": self.trade_note_var.get().strip(),
                "recurring": bool(self.trade_recurring_var.get()),
                "unit_template": unit_template,
                "unit_year": self._trade_unit_year_auto,
                "principal": float(self.trade_principal_var.get() or "0"),
                "interest_rate": float(self.trade_interest_var.get() or "0"),
                "turns": int(self.trade_turns_var.get() or "0"),
            }

            self.trade_orders.append(item)
            if kind == "resource":
                display = f"{kind_cn} | {side_cn} | {self.trade_partner_var.get()} | {res_cn} ×{item['quantity']}"
            elif kind == "military":
                display = f"{kind_cn} | {side_cn} | {self.trade_partner_var.get()} | {_cn(UNIT_CN, unit_template)} ×{item['quantity']}"
            elif kind == "loan":
                display = f"{kind_cn} | {side_cn} | {self.trade_partner_var.get()} | 本金{item['principal']}"
            else:
                display = json.dumps(item, ensure_ascii=False)
            if item.get("recurring"):
                display = "[长期] " + display
            self.trade_list.insert("end", display)
            self.refresh_active_agreements()
            self.refresh_summaries()
        except Exception as e:
            messagebox.showerror("贸易指令错误", str(e))

    def refresh_active_agreements(self):
        if not hasattr(self, "active_agreement_list"):
            return
        self.active_agreement_list.delete(0, "end")
        code = self.nation_var.get().strip()
        db_path = self.db_path_var.get().strip()
        if not code or not os.path.exists(db_path):
            return
        try:
            rows = list_active_agreements(db_path, code)
            for row in rows:
                payload = row.get("payload", {})
                kind = row.get("kind", "")
                kind_cn = _cn(TRADE_KIND_CN, kind)
                if kind == "loan":
                    principal = payload.get("principal", 0)
                    interest_rate = payload.get("interest_rate", 0.0)
                    turns_left = payload.get("turns_left", payload.get("turns", "?"))
                    due_amount = round(principal * (1 + interest_rate), 2)
                    overdue = payload.get("overdue", False)
                    overdue_tag = " [逾期]" if overdue else ""
                    detail = f"贷款:{principal} | 剩余{turns_left}回合 | 到期还{due_amount}{overdue_tag}"
                elif kind == "resource":
                    detail = _cn(RESOURCE_CN, payload.get("resource", ""))
                elif kind == "military":
                    detail = _cn(UNIT_CN, payload.get("unit_template", ""))
                else:
                    detail = str(payload)
                text = f"{row['id']} | {kind_cn} | {row['nation']}→{row['partner']} | {detail}"
                self.active_agreement_list.insert("end", text)
        except Exception as e:
            self.active_agreement_list.insert("end", f"[错误] {e}")

        # 显示本回合待提交的长期协定
        pending = [o for o in self.trade_orders
                   if o.get("action", "submit") == "submit" and o.get("recurring")]
        if pending:
            self.active_agreement_list.insert("end", "── 待提交长期协定 ──")
            for o in pending:
                kind_cn = _cn(TRADE_KIND_CN, o.get("kind", "resource"))
                side_cn = _cn(TRADE_SIDE_CN, o.get("side", "import"))
                partner = o.get("partner", "")
                if o.get("kind") == "resource":
                    detail = f"{_cn(RESOURCE_CN, o.get('resource',''))} ×{o.get('quantity',0)}"
                elif o.get("kind") == "military":
                    detail = f"{_cn(UNIT_CN, o.get('unit_template',''))} ×{o.get('quantity',0)}"
                elif o.get("kind") == "loan":
                    detail = f"本金{o.get('principal',0)}"
                else:
                    detail = ""
                self.active_agreement_list.insert("end",
                    f"[待提交] {kind_cn} | {side_cn} | →{partner} | {detail}")

    def queue_cancel_selected_agreement(self):
        sel = self.active_agreement_list.curselection()
        if not sel:
            return
        line = self.active_agreement_list.get(sel[0])
        parts = [p.strip() for p in line.split("|")]
        agreement_id = parts[0]
        kind_cn = parts[1] if len(parts) > 1 else "资源"
        kind = TRADE_KIND_CN_REV.get(kind_cn, kind_cn)
        item = {
            "action": "cancel",
            "kind": kind,
            "nation": self.nation_var.get(),
            "partner": "",
            "side": "import",
            "agreement_id": agreement_id,
            "note": "cancel by ui",
        }
        self.trade_orders.append(item)
        self.trade_list.insert("end", f"[取消] {kind_cn} | 协定 {agreement_id}")
        self.refresh_summaries()

    def remove_trade_order(self):
        sel = self.trade_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.trade_list.delete(idx)
        self.trade_orders.pop(idx)
        self.refresh_summaries()

    def add_refining_order(self):
        try:
            recipe_cn = self.refine_recipe_var.get()
            recipe = RECIPE_CN_REV.get(recipe_cn, recipe_cn)
            item = {
                "recipe": recipe,
                "runs": float(self.refine_runs_var.get()),
                "bonus_chromium": float(self.refine_chromium_var.get()),
            }
            self.refining_orders.append(item)
            display = f"{recipe_cn} ×{item['runs']}"
            if item["bonus_chromium"]:
                display += f" (铬加成 {item['bonus_chromium']})"
            self.refining_list.insert("end", display)
            self.refresh_summaries()
        except Exception as e:
            messagebox.showerror("精炼指令错误", str(e))

    def remove_refining_order(self):
        sel = self.refining_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.refining_list.delete(idx)
        self.refining_orders.pop(idx)
        self.refresh_summaries()

    def add_build_order(self):
        try:
            fac_cn = self.build_facility_var.get()
            fac = FACILITY_CN_REV.get(fac_cn, fac_cn)
            location = self.build_location_var.get().strip()

            own_tiles = self._get_own_tile_codes()
            if own_tiles and location and location not in own_tiles:
                if not messagebox.askyesno("警告",
                        f"地块 {location} 不属于本国领土！\n确定要在此建造吗？"):
                    return

            item = {
                "facility": fac,
                "quantity": int(self.build_qty_var.get()),
                "location": location,
                "level": int(self.build_level_var.get() or "0"),
            }
            self.build_orders.append(item)
            display = f"{fac_cn} ×{item['quantity']} @ {location}"
            if fac in ("land_fort", "coastal_fort"):
                display += f" Lv.{item['level']}"
            self.build_list.insert("end", display)
            self.refresh_summaries()
        except Exception as e:
            messagebox.showerror("建造指令错误", str(e))

    def remove_build_order(self):
        sel = self.build_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.build_list.delete(idx)
        self.build_orders.pop(idx)
        self.refresh_summaries()

    def add_unit_order(self):
        try:
            tmpl_cn = self.unit_template_var.get()
            tmpl = UNIT_CN_REV.get(tmpl_cn, tmpl_cn)
            year = self._unit_year_auto
            item = {
                "template": tmpl,
                "year": year,
                "quantity": int(self.unit_qty_var.get()),
            }
            self.unit_orders.append(item)
            self.unit_list.insert("end", f"{tmpl_cn} {year} ×{item['quantity']}")
            self.refresh_summaries()
        except Exception as e:
            messagebox.showerror("生产指令错误", str(e))

    def remove_unit_order(self):
        sel = self.unit_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.unit_list.delete(idx)
        self.unit_orders.pop(idx)
        self.refresh_summaries()

    def set_research(self):
        tech_cn = self.research_tech_var.get()
        tech_en = TECH_CN_REV.get(tech_cn, tech_cn)
        spec = TECH_SPECS.get(tech_en)
        if not spec:
            messagebox.showerror("科研指令错误", f"未知科技: {tech_cn}")
            return
        if self.current_state and tech_en in self.current_state.techs:
            messagebox.showerror("科研指令错误", f"{tech_cn} 已研究完毕")
            return
        self.research_cmd = {"tech": tech_en}
        self.refresh_summaries()

    def clear_research(self):
        self.research_cmd = None
        self.refresh_summaries()

    def build_payload(self):
        nation = self.nation_var.get().strip()
        if not nation:
            raise ValueError("nation required")

        policy_changes = {}
        current_policies = self.current_state.policies if self.current_state else {}
        for cat, var in self.policy_vars.items():
            v = var.get().strip()
            if not v:
                continue
            en_val = POLICY_CN_REV.get(v, v)
            # 只有与当前生效政策不同时才加入 policy_changes
            if en_val != current_policies.get(cat):
                policy_changes[cat] = en_val

        one = {
            "build_orders": list(self.build_orders),
            "refining_orders": list(self.refining_orders),
            "unit_orders": list(self.unit_orders),
            "research": self.research_cmd,
            "treaties": list(self.trade_orders),
            "policy_changes": policy_changes,
        }

        payload = {
            "schema_version": 1,
            "turn": int(self.turn_var.get()),
            "inputs": {
                nation: one,
            },
            "meta": {
                "created_by": "player-ui",
            },
        }
        return payload

    def preview_turn(self):
        try:
            payload = self.build_payload()
            nation = self.nation_var.get().strip()
            result = preview_turn_from_json_payload(self.db_path_var.get().strip(), payload, nation)
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", _localize_preview_cn(result))
            self._format_text(self.output_text)
        except PayloadValidationError as e:
            msg = "校验错误:\n" + "\n".join([f"- {x}" for x in e.errors])
            if e.warnings:
                msg += "\n\n警告:\n" + "\n".join([f"- {x}" for x in e.warnings])
            messagebox.showerror("校验失败", msg)
        except Exception as e:
            messagebox.showerror("预估失败", str(e))

    def export_json(self):
        try:
            payload = self.build_payload()
            path = filedialog.asksaveasfilename(
                title="导出指令 JSON",
                defaultextension=".json",
                filetypes=[("JSON 文件", "*.json")],
                initialfile=f"turn_{self.turn_var.get()}_{self.nation_var.get() or 'nation'}.json",
            )
            if not path:
                return
            save_json_file(path, payload)
            messagebox.showinfo("保存成功", f"JSON 已导出:\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def run_once(self):
        try:
            payload = self.build_payload()
            if not messagebox.askyesno("确认", "确认提交本回合指令并写入数据库？"):
                return
            result = run_turn_from_json_payload(self.db_path_var.get().strip(), payload)
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", _localize_run_result_cn(result))
            self._format_text(self.output_text)
            self.refresh_states()
        except PayloadValidationError as e:
            msg = "校验错误:\n" + "\n".join([f"- {x}" for x in e.errors])
            if e.warnings:
                msg += "\n\n警告:\n" + "\n".join([f"- {x}" for x in e.warnings])
            messagebox.showerror("校验失败", msg)
        except Exception as e:
            messagebox.showerror("推演失败", str(e))

    def refresh_summaries(self):
        if not self.current_state:
            return

        # ── 预计IC（含修正，供各摘要面板使用）──
        proj_civ, proj_mil, proj_nav = _projected_ic(self.current_state)
        # 按占领系数折算的有效工厂数（核心=1.0，占领=0.5）
        eff_fac = _effective_facilities(self.current_state)

        # ── 精炼厂计数提示 ──
        if hasattr(self, "refine_info_label"):
            info_parts = []
            for rk, rs in RECIPE_SPECS.items():
                fac_key = rs["facility"]
                count = eff_fac.get(fac_key, 0.0)
                info_parts.append(f"{_cn(FACILITY_CN, fac_key)}: {count:.1f}座")
            self.refine_info_label.config(text="  |  ".join(info_parts))

        # ── 贸易页摘要 ──
        self.trade_summary.delete("1.0", "end")
        in_out = {}
        civ_net = 0.0
        for row in self.trade_orders:
            if row.get("action", "submit") != "submit":
                continue
            kind = row.get("kind", "resource")
            side = row.get("side")
            if kind == "resource":
                res = row.get("resource", "")
                qty = float(row.get("quantity", 0))
                if side == "import":
                    in_out[res] = in_out.get(res, 0.0) + qty
                    civ_net -= qty * float(row.get("price_per_unit", 0))
                elif side == "export":
                    in_out[res] = in_out.get(res, 0.0) - qty
                    civ_net += qty * float(row.get("price_per_unit", 0))
            elif kind == "military":
                qty = float(row.get("quantity", 0))
                price = float(row.get("price_per_unit", 0))
                if side == "import":
                    civ_net -= qty * price
                elif side == "export":
                    civ_net += qty * price
            elif kind == "loan":
                principal = float(row.get("principal", 0))
                if side == "import":
                    civ_net += principal
                elif side == "export":
                    civ_net -= principal

        lines = []
        lines.append(f"=== {self.current_state.code} ─ 贸易总览 ===")
        lines.append("")
        lines.append("[当前库存]")
        for k, v in sorted(self.current_state.stockpile.items()):
            lines.append(f"  {_cn(RESOURCE_CN, k)}: {v:.2f}")
        lines.append("")
        lines.append("[贸易净增估算]  (正=增加)")
        if in_out:
            for k, v in sorted(in_out.items()):
                lines.append(f"  {_cn(RESOURCE_CN, k)}: {v:+.2f}")
        else:
            lines.append("  (无)")
        lines.append("")
        lines.append(f"贸易民用IC流量估算: {civ_net:+.2f}")
        self.trade_summary.insert("1.0", "\n".join(lines))
        self._format_text(self.trade_summary)

        # ── 民用页摘要 ──
        self.civil_summary.delete("1.0", "end")
        build_cost = 0.0
        for row in self.build_orders:
            fac = row["facility"]
            qty = int(row.get("quantity", 1))
            if fac == "land_fort":
                lvl = int(row.get("level", 1))
                build_cost += 4000 + (lvl - 1) * 1000  # 要塞按单座计费
            elif fac == "coastal_fort":
                lvl = int(row.get("level", 1))
                build_cost += 5000 + (lvl - 1) * 1000  # 要塞按单座计费
            else:
                build_cost += FACILITY_SPECS[fac].build_cost * qty

        _fac_main   = [("civilian_factory","民工"), ("military_factory","军工"), ("dockyard","船坞")]
        _fac_spec   = [("artillery_foundry","火炮厂"), ("engine_factory","发动机厂"),
                       ("tank_assembly","坦克厂"), ("aircraft_assembly","飞机厂")]
        _fac_refine = [("steel_mill","炼钢厂"), ("aluminum_refinery","炼铝厂"),
                       ("synthetic_oil_refinery","炼油厂"), ("synthetic_rubber_plant","炼胶厂"),
                       ("thermal_power_plant","发电厂")]
        def _fac(k): return self.current_state.facilities.get(k, 0)
        c_lines = [
            f"=== 民用建设总览 ===",
            "",
            f"本回合预计民用IC: {proj_civ:.2f}  (上轮剩余: {self.current_state.civ_ic:.2f})",
            "",
            "[工厂布局]",
            "主力工厂:  " + "  ".join(f"{cn} {_fac(k)}" for k, cn in _fac_main),
        ]
        _spec_parts = [f"{cn} {_fac(k)}" for k, cn in _fac_spec if _fac(k) > 0]
        if _spec_parts:
            c_lines.append("特殊工厂:  " + "  ".join(_spec_parts))
        _refine_parts = [f"{cn} {_fac(k)}" for k, cn in _fac_refine if _fac(k) > 0]
        if _refine_parts:
            c_lines.append("精炼/动力: " + "  ".join(_refine_parts))
        c_lines.append(f"")
        c_lines.append(f"[建造费用]")
        c_lines.append(f"预计建造消耗: {build_cost:.2f}")
        balance = proj_civ - build_cost
        if balance < 0:
            c_lines.append(f"⚠ IC不足！差额: {balance:.2f}（建造将失败）")
        else:
            c_lines.append(f"简单余额 (民用IC − 预计消耗): {balance:.2f}")
        c_lines += ["", "[待提交建造指令]"]
        for row in self.build_orders:
            fac_cn = _cn(FACILITY_CN, row["facility"])
            c_lines.append(f"  - {fac_cn} ×{row.get('quantity',1)} @ {row.get('location','')}")
        self.civil_summary.insert("1.0", "\n".join(c_lines))
        self._format_text(self.civil_summary)

        # ── 军事页摘要 ──
        self.military_summary.delete("1.0", "end")
        mil_need = 0.0
        nav_need = 0.0
        special_need = {}
        stock_need = {}
        for row in self.unit_orders:
            key = (row["template"], int(row["year"]))
            qty = int(row.get("quantity", 1))
            spec = UNIT_TEMPLATES.get(key)
            if not spec:
                continue
            if spec["ic_type"] == "mil":
                mil_need += spec["ic_cost"] * qty
            else:
                nav_need += spec["ic_cost"] * qty
            for res, amt in spec["resources"].items():
                total = amt * qty
                if res in ("artillery", "engine", "tank", "aircraft"):
                    special_need[res] = special_need.get(res, 0.0) + total
                else:
                    stock_need[res] = stock_need.get(res, 0.0) + total

        current_special = {}
        _sp_mods = self.current_state.modifiers.total()
        _mil_fac_fixed = _sp_mods.get("military_facility_fixed", 0)
        _art_tank_fixed = _sp_mods.get("artillery_tank_fixed", 0)
        _special_out_fixed = _sp_mods.get("special_output_fixed", 0)
        for fac_key in ("artillery_foundry", "engine_factory", "tank_assembly", "aircraft_assembly"):
            count = eff_fac.get(fac_key, 0.0)
            sp = FACILITY_SPECS[fac_key]
            if sp.special_output:
                for cap_name, per_unit in sp.special_output.items():
                    bonus = _mil_fac_fixed + _special_out_fixed
                    if cap_name in ("artillery", "tank"):
                        bonus += _art_tank_fixed
                    current_special[cap_name] = current_special.get(cap_name, 0) + count * (per_unit + bonus)

        is_war = self.current_state.war_status == "war"
        # 完全对齐 phase_07：和平+非升级=0，战时=基础，升级=翻倍
        _research_tech = self.research_cmd.get("tech") if self.research_cmd else None
        war_mil_ic, war_nav_ic, war_res, war_cap = _estimate_war_maintenance(self.current_state, _research_tech)
        # 余量始终减实际维护费（和平无升级时维护费本身就是0）
        mil_balance = proj_mil - mil_need - war_mil_ic
        nav_balance = proj_nav - nav_need - war_nav_ic

        maint_label = "生产+维护后" if (war_mil_ic > 0 or war_nav_ic > 0) else "生产后"
        m_lines = [
            f"=== 军事生产总览 ===",
            "",
            "[IC 概况]",
            f"本回合预计军用IC: {proj_mil:.2f}  (上轮剩余: {self.current_state.mil_ic:.2f})",
            f"本回合预计船坞IC: {proj_nav:.2f}  (上轮剩余: {self.current_state.nav_ic:.2f})",
            f"预计生产消耗军用IC: {mil_need:.2f}    本回合维护军用IC: {war_mil_ic:.2f}",
            f"预计生产消耗船坞IC: {nav_need:.2f}    本回合维护船坞IC: {war_nav_ic:.2f}",
            f"军用IC余量（{maint_label}）: {mil_balance:.2f}" + ("  ⚠不足" if mil_balance < 0 else ""),
            f"船坞IC余量（{maint_label}）: {nav_balance:.2f}" + ("  ⚠不足" if nav_balance < 0 else ""),
        ]
        m_lines.append("")
        m_lines.append("[生产单位资源需求]")
        if stock_need:
            for k, v in sorted(stock_need.items()):
                have = float(self.current_state.stockpile.get(k, 0.0))
                m_lines.append(f"  {_cn(RESOURCE_CN, k)}: 需 {v:.2f} / 有 {have:.2f}")
        else:
            m_lines.append("  (无)")
        m_lines.append("")
        m_lines.append("[特殊产能需求]")
        if special_need:
            for k, v in sorted(special_need.items()):
                have = current_special.get(k, 0)
                m_lines.append(f"  {_cn(SPECIAL_CN, k)}: 需 {v:.2f} / 有 {have:.2f}")
        else:
            m_lines.append("  (无)")
        m_lines.append("")
        m_lines.append("[当前特殊产能]")
        if current_special:
            for k, v in sorted(current_special.items()):
                m_lines.append(f"  {_cn(SPECIAL_CN, k)}: {v:.2f}")
        else:
            m_lines.append("  (无)")

        # ── 维护费详情（完全对齐 phase_07，和平无升级时各项均为0） ──
        m_lines.append("")
        m_lines.append("[维护费详情]  (含精神减免)")
        _tmods = self.current_state.modifiers.total()
        rl = _tmods.get("maint_reduction_land",  0.0)
        rn = _tmods.get("maint_reduction_naval", 0.0)
        ra = _tmods.get("maint_reduction_air",   0.0)
        if rl > 0 or rn > 0 or ra > 0:
            m_lines.append(f"  陆军减免: {rl*100:.0f}%  海军减免: {rn*100:.0f}%  空军减免: {ra*100:.0f}%")
        if war_res:
            m_lines.append("  资源消耗:")
            for rk, rv in sorted(war_res.items()):
                have = self.current_state.stockpile.get(rk, 0.0)
                warn = "  ⚠不足" if have < rv else ""
                m_lines.append(f"    {_cn(RESOURCE_CN, rk)}: {rv:.2f}  （库存: {have:.1f}{warn}）")
        else:
            m_lines.append("  资源消耗: (无)")
        if war_cap:
            m_lines.append("  特殊产能消耗:")
            for ck, cv in sorted(war_cap.items()):
                m_lines.append(f"    {_cn(SPECIAL_CN, ck)}: {cv:.2f}")
        else:
            m_lines.append("  特殊产能消耗: (无)")

        self.military_summary.insert("1.0", "\n".join(m_lines))
        self._format_text(self.military_summary)

        # ── 内政页摘要 ──
        self.internal_summary.delete("1.0", "end")
        total_buffs = self.current_state.modifiers.total()
        i_lines = [
            f"=== 内政总览 ===",
            "",
            f"年份: {self.current_state.year}    战争状态: {self.current_state.war_status}",
            f"稳定度: {self.current_state.stability}    战争支持: {self.current_state.war_support}",
        ]
        _i_fac_all = [
            ("civilian_factory","民工"), ("military_factory","军工"), ("dockyard","船坞"),
            ("artillery_foundry","火炮厂"), ("engine_factory","发动机厂"),
            ("tank_assembly","坦克厂"), ("aircraft_assembly","飞机厂"),
            ("steel_mill","炼钢厂"), ("aluminum_refinery","炼铝厂"),
            ("synthetic_oil_refinery","炼油厂"), ("synthetic_rubber_plant","炼胶厂"),
            ("thermal_power_plant","发电厂"),
        ]
        _i_fac_parts = [
            f"{cn} {eff_fac.get(fk, 0.0):.1f}"
            for fk, cn in _i_fac_all
            if eff_fac.get(fk, 0.0) > 0
        ]
        i_lines.append("")
        if _i_fac_parts:
            i_lines.append("  " + "  ".join(_i_fac_parts[:6]))
            if len(_i_fac_parts) > 6:
                i_lines.append("  " + "  ".join(_i_fac_parts[6:]))
        else:
            i_lines.append("[工厂总数]")
            i_lines.append("  (无)")
        i_lines += [
            "",
            "[当前政策]",
        ]
        for k, v in sorted(self.current_state.policies.items()):
            i_lines.append(f"  {_cn(POLICY_CAT_CN, k)}: {_cn(POLICY_CN, v)}")
        i_lines.append("")
        i_lines.append("[排队政策]")
        for k, v in sorted(self.current_state.queued_policies.items()):
            i_lines.append(f"  {_cn(POLICY_CAT_CN, k)}: {_cn(POLICY_CN, v)}")
        if not self.current_state.queued_policies:
            i_lines.append("  (无)")

        # 本回合在UI里新选的政策变更
        cur_pol = self.current_state.policies
        pending_ui = {}
        for cat, var in self.policy_vars.items():
            v = var.get().strip()
            if not v:
                continue
            en_val = POLICY_CN_REV.get(v, v)
            if en_val != cur_pol.get(cat):
                pending_ui[cat] = en_val
        i_lines.append("")
        i_lines.append("[本回合政策变更指令]")
        if pending_ui:
            for k, v in sorted(pending_ui.items()):
                i_lines.append(f"  {_cn(POLICY_CAT_CN, k)}: {_cn(POLICY_CN, cur_pol.get(k, ''))} → {_cn(POLICY_CN, v)}")
        else:
            i_lines.append("  (无变更)")

        i_lines.append("")
        i_lines.append("[科研指令]")
        if self.research_cmd:
            tech_en = self.research_cmd["tech"]
            spec = TECH_SPECS.get(tech_en, {})
            base = spec.get("cost", 0)
            tech_level_str = tech_en.rsplit("_", 1)[-1]
            tech_level = int(tech_level_str) if tech_level_str.isdigit() else 1
            year = self.current_state.year if self.current_state else 1936
            ahead = max(0, tech_level - get_available_level(year))
            ahead_cost = int(base * (5 ** ahead)) if base else 0
            rspeed = total_buffs.get("research_speed", 0.0)
            if rspeed < 0:
                estimated = int(math.ceil(ahead_cost * (1 - rspeed) - 1e-9))
            else:
                estimated = ahead_cost
            parts = [f"基础 {base} IC"]
            if ahead > 0:
                parts.append(f"超前{ahead}级后 {ahead_cost} IC")
            if rspeed < 0:
                parts.append(f"科研速度{rspeed*100:+.0f}%惩罚后 {estimated} IC")
            if len(parts) > 1:
                i_lines.append(f"  {_cn(TECH_CN, tech_en)} ({' → '.join(parts)})")
            else:
                i_lines.append(f"  {_cn(TECH_CN, tech_en)} (预估费用 {estimated} IC)")
        else:
            i_lines.append("  (无)")

        i_lines.append("")
        i_lines.append("[国家精神]")
        from static.spirits import SPIRIT_SPECS
        if self.current_state.spirits:
            for k in self.current_state.spirits:
                spec = SPIRIT_SPECS.get(k, {})
                name = spec.get("name", k)
                desc = spec.get("desc", "")
                i_lines.append(f"  ▪ {name}")
                if desc:
                    i_lines.append(f"    {desc}")
        else:
            i_lines.append("  (无)")

        from utils.modifiers import compute_alpha1
        from static.policies import POLICY_SPECS
        alpha1_val = compute_alpha1(self.current_state, total_buffs)
        econ_key = self.current_state.policies.get("economy_law", "")
        base_alpha1 = POLICY_SPECS["economy_law"].get(econ_key, {}).get("alpha1", 0.35)

        _SRC_LABEL = {
            "policy": "政策", "tech": "科技", "spirit": "国家精神",
            "stability": "稳定度", "power_penalty": "电力惩罚", "temporary": "临时",
        }
        # 构建每个修正键的详细来源列表: {modifier_key: [(label, value), ...]}
        _pct_mod_keys = {
            "civ_output", "mil_output", "research_speed", "resource_output", "power_output",
            "consumer_goods_delta", "maint_reduction_land", "maint_reduction_naval", "maint_reduction_air",
        }

        def _fmt_mod(mk, mv):
            if mk in _pct_mod_keys:
                return f"{mv:+.1%}"
            return f"{mv:+.2f}"

        _item_sources = {}  # modifier_key -> [(label, value)]
        # 政策来源
        for _cat, _key in self.current_state.policies.items():
            if _cat not in POLICY_SPECS or _key not in POLICY_SPECS[_cat]:
                continue
            _spec = POLICY_SPECS[_cat][_key]
            _label = _cn(POLICY_CN, _key)
            for _mk, _mv in _spec.get("pct", {}).items():
                _item_sources.setdefault(_mk, []).append((_label, _mv))
            for _mk, _mv in _spec.get("abs", {}).items():
                _item_sources.setdefault(_mk, []).append((_label, _mv))
        # 科技来源
        from static.techs import TECH_SPECS as _TECH_SPECS_LOCAL
        for _tkey in sorted(self.current_state.techs):
            _tspec = _TECH_SPECS_LOCAL.get(_tkey)
            if not _tspec:
                continue
            _tlabel = _cn(TECH_CN, _tkey)
            for _mk, _mv in _tspec.get("effects_pct", {}).items():
                _item_sources.setdefault(_mk, []).append((_tlabel, _mv))
            for _mk, _mv in _tspec.get("effects_abs", {}).items():
                _item_sources.setdefault(_mk, []).append((_tlabel, _mv))
        # 精神来源
        for _skey in self.current_state.spirits:
            _sspec = SPIRIT_SPECS.get(_skey, {})
            _slabel = _sspec.get("name", _skey)
            for _mk, _mv in _sspec.get("modifiers", {}).items():
                _item_sources.setdefault(_mk, []).append((_slabel, _mv))
        # 稳定度来源
        for _mk, _mv in self.current_state.modifiers.stability.items():
            if abs(_mv) > 1e-9:
                _item_sources.setdefault(_mk, []).append((f"稳定度({int(self.current_state.stability)})", _mv))
        # 电力惩罚
        for _mk, _mv in self.current_state.modifiers.power_penalty.items():
            if abs(_mv) > 1e-9:
                _item_sources.setdefault(_mk, []).append(("电力惩罚", _mv))
        # 临时修正
        for _mk, _mv in self.current_state.modifiers.temporary.items():
            if abs(_mv) > 1e-9:
                _item_sources.setdefault(_mk, []).append(("临时修正", _mv))

        i_lines.append("")
        i_lines.append("[修正合计]  (来源明细)")
        for k in sorted(total_buffs.keys()):
            v = total_buffs[k]
            cn_name = _cn(MODIFIER_CN, k)
            if k == "consumer_goods_delta":
                i_lines.append(
                    f"  {cn_name}: {v:+.1%}  →  消费品系数: "
                    f"{_cn(POLICY_CN, econ_key)}基础 {base_alpha1:.0%} {v:+.1%} = {alpha1_val:.1%}"
                    f"（剩余 {1-alpha1_val:.1%} 进IC池）"
                )
            elif k in _pct_mod_keys:
                i_lines.append(f"  {cn_name}: {v:+.1%}")
            else:
                i_lines.append(f"  {cn_name}: {v:+.2f}")
            # 具体来源明细
            item_parts = _item_sources.get(k, [])
            if item_parts:
                sub = " | ".join(f"{lbl}: {_fmt_mod(k, mv)}" for lbl, mv in item_parts)
                i_lines.append(f"    └ {sub}")

        self.internal_summary.insert("1.0", "\n".join(i_lines))
        self._format_text(self.internal_summary)

        # ── 科研速度标签 ──
        if hasattr(self, "research_speed_label"):
            rspeed = total_buffs.get("research_speed", 0.0)
            if abs(rspeed) < 1e-9:
                self.research_speed_label.config(text="科研速度: ±0%", foreground="black")
            elif rspeed > 0:
                surplus = 1000 * rspeed
                self.research_speed_label.config(
                    text=f"科研速度: +{rspeed * 100:.1f}%  每次研究盈余: +{surplus:.0f} IC（累满1000可免费研发）",
                    foreground="blue")
            else:
                multiplier = 1 - rspeed
                self.research_speed_label.config(
                    text=f"科研速度: {rspeed * 100:.1f}%  科研费用×{multiplier:.2f}（每次费用增加）",
                    foreground="red")
        def _clear_summaries(self):
                """清空所有摘要面板"""
        for widget in (self.trade_summary, self.civil_summary,
                       self.military_summary, self.internal_summary):
            widget.delete("1.0", "end")

if __name__ == "__main__":
    app = PlayerUI()
    app.mainloop()
