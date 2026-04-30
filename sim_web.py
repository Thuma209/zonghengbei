"""
sim_web.py — 推演组 Streamlit 网页端

启动方法：
    streamlit run sim_web.py

五个页面：
  1. 地块参数修改 — 输入地块代码后直接编辑
  2. 国家数据界面 — 查看/修改各国全部数据
  3. 回合日志     — 执行推演 + 查看各国日志与警报 + 推演后快照
  4. 航线安全系数 — 编辑各国首都大洲与航道安全度
  5. 精神定义     — 增删改国家精神条目与修正值
"""

import json
import os
import sys
import pandas as pd
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from Database.db_manager import DatabaseManager
from static.sea_routes import ZONE_NAMES, _PARENT_ZONE, continent_to_zone, get_route as _get_route_static

# ── 中文翻译表 ────────────────────────────────────────────────────────────
RESOURCE_CN = {
    "steel": "钢铁", "aluminum": "铝", "coal": "煤炭", "iron": "生铁",
    "bauxite": "铝土矿", "tungsten": "钨", "chromium": "铬", "rubber": "橡胶",
    "oil": "石油", "rare_materials": "稀有材料",
    "artillery": "火炮产能", "engine": "发动机产能",
    "tank": "坦克产能", "aircraft": "飞机产能",
}
FACILITY_CN = {
    "civilian_factory": "民用工厂", "military_factory": "军事工厂",
    "dockyard": "船坞", "artillery_foundry": "火炮铸造厂",
    "engine_factory": "发动机工厂", "tank_assembly": "坦克组装厂",
    "aircraft_assembly": "飞机组装厂", "steel_mill": "钢铁厂",
    "aluminum_refinery": "铝精炼厂", "synthetic_oil_refinery": "合成油提炼厂",
    "synthetic_rubber_plant": "合成橡胶厂", "thermal_power_plant": "火力发电厂",
    "land_fort": "陆地要塞", "coastal_fort": "海岸要塞",
}
UNIT_CN = {
    "infantry": "步兵师", "armor": "装甲师", "airwing": "飞行队",
    "submarine": "潜艇", "carrier": "航空母舰", "battleship": "主力舰", "screen": "屏卫舰",
}
TECH_CN = {
    "industrial_1": "工业科技1级", "industrial_2": "工业科技2级",
    "industrial_3": "工业科技3级", "industrial_4": "工业科技4级",
    "industrial_5": "工业科技5级",
    "resource_1": "资源科技1级", "resource_2": "资源科技2级",
    "resource_3": "资源科技3级", "resource_4": "资源科技4级",
    "resource_5": "资源科技5级",
    "electronics_1": "电子科技1级", "electronics_2": "电子科技2级",
    "electronics_3": "电子科技3级", "electronics_4": "电子科技4级",
    "electronics_5": "电子科技5级",
    "infantry_1": "步兵科技1级", "infantry_2": "步兵科技2级",
    "infantry_3": "步兵科技3级", "infantry_4": "步兵科技4级",
    "armor_1": "装甲科技1级", "armor_2": "装甲科技2级",
    "armor_3": "装甲科技3级", "armor_4": "装甲科技4级",
    "aircraft_1": "飞机科技1级", "aircraft_2": "飞机科技2级",
    "aircraft_3": "飞机科技3级", "aircraft_4": "飞机科技4级",
    "submarine_1": "潜艇科技1级", "submarine_2": "潜艇科技2级",
    "submarine_3": "潜艇科技3级", "submarine_4": "潜艇科技4级",
    "carrier_1": "航母科技1级", "carrier_2": "航母科技2级",
    "carrier_3": "航母科技3级", "carrier_4": "航母科技4级",
    "battleship_1": "主力舰科技1级", "battleship_2": "主力舰科技2级",
    "battleship_3": "主力舰科技3级", "battleship_4": "主力舰科技4级",
    "screen_1": "屏卫舰科技1级", "screen_2": "屏卫舰科技2级",
    "screen_3": "屏卫舰科技3级", "screen_4": "屏卫舰科技4级",
}
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
POLICY_CAT_CN = {
    "economy_law": "经济法", "trade_law": "贸易法", "tax_policy": "税收政策",
}

CN_TO_EN_RES = {v: k for k, v in RESOURCE_CN.items()}
CN_TO_EN_FAC = {v: k for k, v in FACILITY_CN.items()}


def _cn(mapping: dict, key: str) -> str:
    return mapping.get(key) or key


# ── 全局设置 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="推演组控制台", layout="wide")

# ── 数据库连接 ────────────────────────────────────────────────────────────
DB_DIR = os.path.join(PROJECT_ROOT, "Database")
DEFAULT_DB = os.path.join(DB_DIR, "game.db")


@st.cache_resource
def get_db(path: str) -> DatabaseManager:
    return DatabaseManager(path)


def _db() -> DatabaseManager:
    path = st.session_state.get("db_path", DEFAULT_DB)
    return get_db(path)


def _reload():
    """清除缓存，强制重新加载数据库。"""
    st.cache_resource.clear()
def exportDataByNation(nation_name: str, output_path: str = None):
    db = _db()

    # 👇 这里调用你数据库自带的查询方法（最关键！）
    raw_data = db.exportDataByNation(nation_name)  # 你原来的方法

    # 👇 把 sqlite 游标结果转成 列表+字典
    datas = []
    columns = [desc[0] for desc in raw_data.description]  # 拿到列名
    for row in raw_data.fetchall():
        datas.append(dict(zip(columns, row)))

    if not datas:
        print(f"❌ 未找到国家：{nation_name}")
        return None

    # 👇 直接导出 Excel
    df = pd.DataFrame(datas)

    if not output_path:
        output_path = f"{nation_name}_导出数据.xlsx"

    df.to_excel(output_path, index=False)
    print(f"✅ 导出成功：{output_path}")
    return output_path

# ── 侧边栏 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("推演组控制台")
    db_path = st.text_input("数据库路径", value=DEFAULT_DB, key="db_path")
    if st.button("🔄 重新加载数据库"):
        _reload()
        st.rerun()
    st.divider()
    tab_choice = st.radio(
        "功能页面",
        ["回合日志", "地块参数修改", "国家数据", "航线安全系数"],
        label_visibility="collapsed",
    )


# ======================================================================
#  Tab 1: 地块参数修改
# ======================================================================
def page_tile():
    st.header("地块参数修改")
    db = _db()

    # 加载所有地块代码供搜索
    rows = db.conn.execute("SELECT code, name, controller FROM tile ORDER BY code").fetchall()
    tile_codes = [r["code"] for r in rows]

    s_col, r_col = st.columns([4, 1])
    with s_col:
        search_q = st.text_input("搜索地块（输入代码或名称的一部分）", key="tile_search",
                                 placeholder="如 CHN、东北、沿海…")
    with r_col:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("刷新列表"):
            _reload()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    q = search_q.strip().lower()
    filtered_rows = [r for r in rows if q in r["code"].lower() or q in r["name"].lower()] if q else rows
    filtered_codes = [r["code"] for r in filtered_rows]

    if not filtered_codes:
        st.warning("没有匹配的地块，请修改搜索条件。")
        return

    selected_code = st.selectbox(
        f"选择地块（共 {len(filtered_codes)} / {len(rows)} 个）",
        filtered_codes,
        format_func=lambda c: next(
            (f"{r['code']} — {r['name']} [{r['controller']}]" for r in filtered_rows if r['code'] == c), c
        ),
        key="tile_select",
    )

    if not selected_code:
        return

    # 加载该地块
    row = db.conn.execute("SELECT * FROM tile WHERE code=?", (selected_code,)).fetchone()
    if not row:
        st.error(f"找不到地块: {selected_code}")
        return
    data = dict(row)

    st.subheader(f"{data['name']}（{data['code']}）")

    # 基本属性
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        new_controller = st.text_input("控制国", value=data["controller"], key="tile_ctrl")
    with c2:
        occ_opts = ["核心", "占领"]
        cur_occ = data["occupation_type"]
        # 兼容旧数据：core/puppet/occupied → 对应中文
        _occ_norm = {"core": "核心", "傀儡": "占领", "puppet": "占领", "occupied": "占领"}
        cur_occ = _occ_norm.get(cur_occ, cur_occ)
        occ_idx = occ_opts.index(cur_occ) if cur_occ in occ_opts else 0
        new_occ = st.selectbox("占领类型", occ_opts, index=occ_idx, key="tile_occ")
    with c3:
        new_land_fort = st.number_input("陆地要塞等级", min_value=0, max_value=10,
                                        value=data["land_fort_level"], key="tile_lf")
    with c4:
        new_coast_fort = st.number_input("海岸要塞等级", min_value=0, max_value=10,
                                         value=data["coastal_fort_level"], key="tile_cf")

    c5, c6 = st.columns(2)
    with c5:
        new_continent = st.text_input("所属地域（地块类型）", value=data["continent"] or "", key="tile_continent")
    with c6:
        new_is_coastal = st.checkbox("是否沿海", value=bool(data["is_coastal"]), key="tile_coastal")

    # 资源编辑
    st.subheader("资源")
    resources = json.loads(data["resources"]) if data["resources"] else {}
    res_cols = st.columns(5)
    new_resources = {}
    for i, (rk, rv) in enumerate(sorted(resources.items())):
        with res_cols[i % 5]:
            new_val = st.number_input(
                _cn(RESOURCE_CN, rk), value=float(rv), step=0.5,
                key=f"tile_res_{rk}", format="%.1f",
            )
            new_resources[rk] = new_val

    # 添加新资源
    with st.expander("添加资源"):
        all_res = [k for k in RESOURCE_CN if k not in resources]
        if all_res:
            add_res = st.selectbox("资源种类", all_res,
                                   format_func=lambda k: _cn(RESOURCE_CN, k), key="tile_add_res")
            add_amt = st.number_input("数量", value=0.0, step=0.5, key="tile_add_amt")
            if st.button("添加", key="tile_add_res_btn"):
                new_resources[add_res] = add_amt
                # 直接写入
                all_r = {**new_resources}
                db.conn.execute("UPDATE tile SET resources=? WHERE code=?",
                                (json.dumps(all_r), selected_code))
                db.conn.commit()
                st.success(f"已添加 {_cn(RESOURCE_CN, str(add_res))}")
                _reload()
                st.rerun()

    # 工厂编辑
    st.subheader("工厂")
    factories = json.loads(data["factories"]) if data["factories"] else {}
    # 排除误入的堡垒 key（堡垒有专门字段）
    factories = {k: v for k, v in factories.items() if k not in ("land_fort", "coastal_fort")}
    fac_cols = st.columns(4)
    new_factories = {}
    for i, (fk, fv) in enumerate(sorted(factories.items())):
        with fac_cols[i % 4]:
            new_fac_val = st.number_input(
                _cn(FACILITY_CN, fk), value=int(fv), step=1,
                key=f"tile_fac_{fk}",
            )
            new_factories[fk] = new_fac_val

    # 添加新工厂
    with st.expander("添加工厂"):
        all_fac = [k for k in FACILITY_CN if k not in factories and k not in ("land_fort", "coastal_fort")]
        if all_fac:
            add_fac = st.selectbox("工厂种类", all_fac,
                                   format_func=lambda k: _cn(FACILITY_CN, k), key="tile_add_fac")
            add_fac_amt = st.number_input("数量", value=0, step=1, key="tile_add_fac_amt")
            if st.button("添加", key="tile_add_fac_btn"):
                new_factories[add_fac] = add_fac_amt
                all_f = {**new_factories}
                db.conn.execute("UPDATE tile SET factories=? WHERE code=?",
                                (json.dumps(all_f), selected_code))
                db.conn.commit()
                st.success(f"已添加 {_cn(FACILITY_CN, str(add_fac))}")
                _reload()
                st.rerun()

    # 保存按钮
    if st.button("💾 保存地块修改", type="primary"):
        db.conn.execute("""
            UPDATE tile SET controller=?, occupation_type=?,
            resources=?, factories=?,
            land_fort_level=?, coastal_fort_level=?,
            continent=?, is_coastal=?
            WHERE code=?
        """, (
            new_controller, new_occ,
            json.dumps(new_resources), json.dumps(new_factories),
            new_land_fort, new_coast_fort,
            new_continent, int(new_is_coastal),
            selected_code,
        ))
        db.conn.commit()
        st.success("地块已保存！")
        _reload()
        st.rerun()


# ======================================================================
#  Tab 2: 国家数据界面
# ======================================================================
def page_nation():
    st.header("国家数据")

    db = _db()
    nations = db.load_all_nations()
    if not nations:
        st.warning("数据库中无国家数据")
        return

    codes = list(nations.keys())
    sel = st.selectbox("选择国家", codes,
                       format_func=lambda c: f"{c} — {nations[c].name}", key="nation_sel")
    if sel is None:
        return
    s = nations[sel]

    # ── 基本信息 ──
    st.subheader("基本信息")
    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        new_year = st.number_input("年份", value=float(s.year), step=0.5, format="%.1f", key="n_year")
    with bc2:
        war_opts = ["peace", "war"]
        new_war = st.selectbox("战争状态", war_opts,
                               index=war_opts.index(s.war_status) if s.war_status in war_opts else 0,
                               key="n_war")
    with bc3:
        new_stab = st.number_input("稳定度", value=s.stability, step=1.0, format="%.1f", key="n_stab")
    with bc4:
        new_ws = st.number_input("战争支持度", value=s.war_support, step=1.0, format="%.1f", key="n_ws")

    # ── IC ──
    st.subheader("工业产能 (IC)")
    ic1, ic2, ic3 = st.columns(3)
    with ic1:
        new_civ = st.number_input("民用IC", value=s.civ_ic, step=1.0, format="%.2f", key="n_civ")
    with ic2:
        new_mil = st.number_input("军用IC", value=s.mil_ic, step=1.0, format="%.2f", key="n_mil")
    with ic3:
        new_nav = st.number_input("海军IC", value=s.nav_ic, step=1.0, format="%.2f", key="n_nav")

    # ── 库存 ──
    st.subheader("资源库存")
    stock_cols = st.columns(5)
    new_stock = {}
    for i, (rk, rv) in enumerate(sorted(s.stockpile.items())):
        with stock_cols[i % 5]:
            new_stock[rk] = st.number_input(
                _cn(RESOURCE_CN, rk), value=float(rv), step=1.0,
                format="%.1f", key=f"n_stock_{rk}",
            )

    # ── 科研 ──
    st.subheader("科研")
    r1, r2, r3 = st.columns(3)
    with r1:
        cur_tech = s.research.get("current") or ""
        new_cur_tech = st.text_input("当前研究", value=cur_tech, key="n_res_cur")
    with r2:
        new_progress = st.number_input("进度", value=float(s.research.get("progress", 0)),
                                       step=0.1, format="%.2f", key="n_res_prog")
    with r3:
        new_res_stock = st.number_input("科研储备", value=float(s.research.get("stockpile", 0)),
                                        step=1.0, format="%.1f", key="n_res_stock")

    # ── 已研发科技 ──
    st.subheader("已研发科技")
    techs_display = ", ".join(_cn(TECH_CN, t) for t in sorted(s.techs)) if s.techs else "（无）"
    st.text(techs_display)

    with st.expander("编辑科技列表"):
        all_techs = sorted(TECH_CN.keys())
        new_techs = st.multiselect(
            "已研发科技（多选）", all_techs,
            default=sorted(s.techs),
            format_func=lambda k: _cn(TECH_CN, k),
            key="n_techs",
        )

    # ── 政策 ──
    st.subheader("政策")
    pc1, pc2, pc3 = st.columns(3)
    new_policies = {}
    economy_opts = ["isolationism", "consumer_economy", "civilian_economy",
                    "early_mobilization", "partial_mobilization", "war_economy", "total_mobilization"]
    trade_opts = ["export_focus", "free_trade", "trade_protection", "closed_economy"]
    tax_opts = ["minimum_tax", "low_tax", "average_tax", "high_tax", "maximum_tax"]
    with pc1:
        cur_econ = s.policies.get("economy_law", "civilian_economy")
        new_policies["economy_law"] = st.selectbox(
            "经济法", economy_opts,
            index=economy_opts.index(cur_econ) if cur_econ in economy_opts else 0,
            format_func=lambda k: _cn(POLICY_CN, k), key="n_pol_econ",
        )
    with pc2:
        cur_trade = s.policies.get("trade_law", "free_trade")
        new_policies["trade_law"] = st.selectbox(
            "贸易法", trade_opts,
            index=trade_opts.index(cur_trade) if cur_trade in trade_opts else 0,
            format_func=lambda k: _cn(POLICY_CN, k), key="n_pol_trade",
        )
    with pc3:
        cur_tax = s.policies.get("tax_policy", "average_tax")
        new_policies["tax_policy"] = st.selectbox(
            "税收政策", tax_opts,
            index=tax_opts.index(cur_tax) if cur_tax in tax_opts else 0,
            format_func=lambda k: _cn(POLICY_CN, k), key="n_pol_tax",
        )

    # ── 国家精神 ──
    st.subheader("国家精神")
    spirits_display = ", ".join(s.spirits) if s.spirits else "（无）"
    st.text(spirits_display)
    # with st.expander("编辑国家精神"):
    #     spirit_defs = db.load_spirit_definitions()
    #     all_spirit_keys = sorted(spirit_defs.keys())
    #     new_spirits = st.multiselect(
    #         "激活的精神（多选）", all_spirit_keys,
    #         default=s.spirits,
    #         format_func=lambda k: spirit_defs.get(k, {}).get("name", k),
    #         key="n_spirits",
    #     )
    with st.expander("编辑国家精神"):
        spirit_defs = db.load_spirit_definitions()
        all_spirit_keys = sorted(spirit_defs.keys())

        # 👇 只保留有效的精神，过滤掉不存在的（核心修复）
        valid_spirits = [s for s in s.spirits if s in all_spirit_keys]

        new_spirits = st.multiselect(
            "激活的精神（多选）", all_spirit_keys,
            default=valid_spirits,  # 👈 替换这一行
            format_func=lambda k: spirit_defs.get(k, {}).get("name", k),
            key="n_spirits",
        )
    # ── 军队 ──
    st.subheader("军队")
    mc1, mc2, mc3 = st.columns(3)
    new_army = {}
    new_navy = {}
    new_airforce = {}
    with mc1:
        st.markdown("**陆军**")
        for uk, uv in sorted(s.army.items()):
            new_army[uk] = st.number_input(uk, value=int(uv), step=1, key=f"n_army_{uk}")
    with mc2:
        st.markdown("**海军**")
        for uk, uv in sorted(s.navy.items()):
            new_navy[uk] = st.number_input(uk, value=int(uv), step=1, key=f"n_navy_{uk}")
    with mc3:
        st.markdown("**空军**")
        for uk, uv in sorted(s.airforce.items()):
            new_airforce[uk] = st.number_input(uk, value=int(uv), step=1, key=f"n_air_{uk}")

    # ── 设施总数 ──
    st.subheader("设施总计")
    fac_cols = st.columns(4)
    new_fac = {}
    for i, (fk, fv) in enumerate(sorted(s.facilities.items())):
        with fac_cols[i % 4]:
            new_fac[fk] = st.number_input(
                _cn(FACILITY_CN, fk), value=int(fv), step=1, key=f"n_fac_{fk}",
            )

    # ── 保存 ──
    if st.button("💾 保存国家数据修改", type="primary"):
        s.year = new_year
        s.war_status = new_war or s.war_status
        s.stability = new_stab
        s.war_support = new_ws
        s.civ_ic = new_civ
        s.mil_ic = new_mil
        s.nav_ic = new_nav
        s.stockpile = new_stock
        s.research = {"current": new_cur_tech or None, "progress": new_progress, "stockpile": new_res_stock}
        s.techs = set(new_techs)
        s.policies = new_policies
        s.spirits = new_spirits
        s.army = {k: v for k, v in new_army.items() if v > 0}
        s.navy = {k: v for k, v in new_navy.items() if v > 0}
        s.airforce = {k: v for k, v in new_airforce.items() if v > 0}
        s.facilities = new_fac
        db.save_nation(s)
        # 精神需要单独更新修正
        db.set_nation_spirits(sel, new_spirits)  # type: ignore[arg-type]
        st.success(f"{s.name} 数据已保存！")
        _reload()
        st.rerun()
    if st.button("导出最新国家数据信息", type="primary"):
        name = s.name
        exportDataByNation(name)
    # ── 精神定义编辑器（放在国家数据页底部）─────────────────────────────
    st.divider()
    show_spirit_editor = st.checkbox("⚙️ 展开精神定义管理（增删改精神模板与修正值）",
                                     key="show_spirit_editor")
    if show_spirit_editor:
        _section_spirit_defs(db)


def _section_spirit_defs(db):
    """精神定义编辑器，嵌入国家数据页。"""
    if "spirit_specs" not in st.session_state:
        specs = db.load_spirit_definitions()
        if not specs:
            from static.spirits import _DEFAULT_SPECS
            import copy as _cp
            specs = _cp.deepcopy(dict(_DEFAULT_SPECS))
        st.session_state["spirit_specs"] = specs

    specs = st.session_state["spirit_specs"]
    spirit_keys = list(specs.keys())

    col_list, col_edit = st.columns([1, 3])

    with col_list:
        st.markdown("**精神列表**")
        spirit_labels = [f"{specs[k].get('name', k)}" for k in spirit_keys]
        sel_idx = st.selectbox(
            "选择精神", range(len(spirit_keys)),
            format_func=lambda i: f"{spirit_labels[i]}  [{spirit_keys[i]}]",
            key="sd_sel",
        ) if spirit_keys else None

        with st.expander("新建精神"):
            new_key = st.text_input("英文ID键（如 usa_new_deal）", key="sd_new_key")
            if st.button("创建", key="sd_create"):
                nk = new_key.strip()
                if nk and nk not in specs:
                    specs[nk] = {"name": nk, "desc": "", "modifiers": {}}
                    st.session_state["spirit_specs"] = specs
                    st.rerun()
                elif nk in specs:
                    st.error("该键已存在")

        if sel_idx is not None and st.button("🗑 删除选中", key="sd_del"):
            del specs[spirit_keys[sel_idx]]
            st.session_state["spirit_specs"] = specs
            st.rerun()

    with col_edit:
        if sel_idx is None:
            st.info("暂无精神定义，请先创建。")
            return

        key = spirit_keys[sel_idx]
        spec = specs[key]
        st.caption(f"ID: {key}")
        new_name = st.text_input("名称", value=spec.get("name", ""), key="sd_name")
        new_desc = st.text_area("描述", value=spec.get("desc", ""), key="sd_desc", height=60)

        st.markdown("**修正项**")
        mods = spec.get("modifiers", {})
        new_mods = {}
        for mk, mv in sorted(mods.items()):
            mc1, mc2, mc3 = st.columns([3, 2, 1])
            with mc1:
                st.text(f"{mk}（{MOD_KEY_CN.get(mk, mk)}）")
            with mc2:
                new_mods[mk] = st.number_input(
                    f"值##{mk}", value=float(mv), step=0.01, format="%.4f",
                    key=f"sd_mod_{key}_{mk}", label_visibility="collapsed",
                )
            with mc3:
                if st.button("✕", key=f"sd_moddel_{key}_{mk}"):
                    del mods[mk]
                    spec["modifiers"] = mods
                    st.session_state["spirit_specs"] = specs
                    st.rerun()

        with st.expander("添加修正项"):
            avail = [k for k in MOD_KEY_CN if k not in mods]
            if avail:
                add_k = st.selectbox("修正种类", avail,
                                     format_func=lambda k: f"{k}（{MOD_KEY_CN[k]}）",
                                     key="sd_add_k")
                add_v = st.number_input("数值", value=0.0, step=0.01,
                                        format="%.4f", key="sd_add_v")
                if st.button("添加修正", key="sd_add_btn"):
                    mods[add_k] = add_v
                    spec["modifiers"] = mods
                    st.session_state["spirit_specs"] = specs
                    st.rerun()

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("💾 暂存修改", key="sd_save"):
                spec["name"] = new_name
                spec["desc"] = new_desc
                spec["modifiers"] = new_mods
                specs[key] = spec
                st.session_state["spirit_specs"] = specs
                st.success("已暂存（未写入DB）")
        with bc2:
            if st.button("📤 写入DB并生效", type="primary", key="sd_write"):
                spec["name"] = new_name
                spec["desc"] = new_desc
                spec["modifiers"] = new_mods
                specs[key] = spec
                db.save_all_spirit_definitions(specs)
                import static.spirits as _spirits_mod
                _spirits_mod.SPIRIT_SPECS.clear()
                _spirits_mod.SPIRIT_SPECS.update(specs)
                st.session_state["spirit_specs"] = specs
                st.success(f"已写入DB（{len(specs)} 条）")
                _reload()


# ======================================================================
#  Tab 3: 回合日志
# ======================================================================
def page_logs():
    st.header("回合日志")
    db = _db()

    st.subheader("执行推演")
    uploaded_files = st.file_uploader(
        "上传玩家指令 JSON 文件（可多选）", type=["json"],
        accept_multiple_files=True, key="json_upload",
    )

    if st.button("▶ 执行推演", type="primary", disabled=not uploaded_files):
        # 合并所有 JSON
        merged_inputs = {}
        for f in (uploaded_files or []):
            try:
                data = json.loads(f.read().decode("utf-8"))
                inputs = data.get("inputs", data)
                if isinstance(inputs, dict):
                    merged_inputs.update(inputs)
            except Exception as e:
                st.error(f"文件 {f.name} 解析失败: {e}")
                return

        payload = {"inputs": merged_inputs}

        try:
            from utils.turn_json_pipeline import run_turn_from_json_payload, PayloadValidationError
            db_path = st.session_state.get("db_path", DEFAULT_DB)
            _reload()  # 清缓存，避免旧连接
            result = run_turn_from_json_payload(db_path, payload)

            if result.get("warnings"):
                for w in result["warnings"]:
                    st.warning(w)

            st.session_state["last_results"] = result.get("results", {})
            st.session_state["last_snapshot"] = result.get("snapshot", {})
            st.success("推演执行成功！")
            _reload()
        except Exception as e:
            import traceback
            st.error(f"推演执行失败: {e}")
            st.code(traceback.format_exc())
            return

    st.divider()

    # ── 显示日志 ──
    results = st.session_state.get("last_results", {})
    if not results:
        st.info("暂无推演结果。请上传 JSON 文件并执行推演。")
        return

    nations = _db().load_all_nations()

    # 重大事项汇总
    alerts = []
    for code, data in results.items():
        logs = data.get("logs", [])
        name = nations[code].name if code in nations else code
        for line in logs:
            if "【推演组注意】" in line:
                alerts.append(f"**{name}**: {line}")
            elif "维护" in line and "不足" in line:
                alerts.append(f"⚠️ **{name}**: {line}")
            elif "科研槽满" in line or "stockpile" in line:
                alerts.append(f"🔬 **{name}**: {line}")
            elif "超前" in line:
                alerts.append(f"🚀 **{name}**: {line}")

    if alerts:
        st.subheader("⚠️ 重大事项")
        for a in alerts:
            st.markdown(a)
        st.divider()

    # 各国日志 + 快照
    st.subheader("各国日志")
    snapshot = st.session_state.get("last_snapshot", {})
    nation_tabs = st.tabs([f"{nations[c].name} ({c})" if c in nations else c
                           for c in results.keys()])
    for tab, (code, data) in zip(nation_tabs, results.items()):
        with tab:
            logs = data.get("logs", [])
            if not logs:
                st.info("本回合无日志")
            else:
                for line in logs:
                    if "【推演组注意】" in line:
                        st.markdown(f"🔴 {line}")
                    elif "失败" in line:
                        st.markdown(f"🟡 {line}")
                    elif "成功" in line:
                        st.markdown(f"🟢 {line}")
                    else:
                        st.text(line)

            # ── 推演后快照 ──
            snap = snapshot.get(code, {})
            if snap:
                st.divider()
                st.markdown("**推演后状态**")
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.metric("年份", snap.get("year", ""))
                    st.metric("稳定度", f"{snap.get('stability', 0):.1f}")
                with sc2:
                    st.metric("民用IC", f"{float(snap.get('civ_ic', 0)):.2f}")
                    st.metric("军用IC", f"{float(snap.get('mil_ic', 0)):.2f}")
                with sc3:
                    st.metric("海军IC", f"{float(snap.get('nav_ic', 0)):.2f}")
                    st.metric("战争支持", f"{snap.get('war_support', 0):.1f}")

                sp = snap.get("stockpile", {})
                if sp:
                    sp_parts = [f"{_cn(RESOURCE_CN, k)}: {float(v):.1f}"
                                for k, v in sorted(sp.items()) if float(v) > 0.001]
                    if sp_parts:
                        st.markdown("**仓库:** " + ", ".join(sp_parts))

                fac = snap.get("facilities", {})
                if fac:
                    fac_parts = [f"{_cn(FACILITY_CN, k)}: {int(v)}"
                                 for k, v in sorted(fac.items()) if int(v) > 0]
                    if fac_parts:
                        st.markdown("**设施:** " + ", ".join(fac_parts))

                techs_s = snap.get("techs", [])
                if techs_s:
                    st.markdown("**科技:** " + ", ".join(
                        str(_cn(TECH_CN, t)) for t in sorted(techs_s)))

                pol = snap.get("policies", {})
                if pol:
                    pol_parts = [f"{_cn(POLICY_CAT_CN, c)}: {_cn(POLICY_CN, v)}"
                                 for c, v in sorted(pol.items())]
                    st.markdown("**政策:** " + ", ".join(pol_parts))

                army = snap.get("army", {})
                navy = snap.get("navy", {})
                air = snap.get("airforce", {})

                def _fmt_snap_units(d):
                    parts = []
                    for k, v in sorted(d.items()):
                        if int(v) <= 0:
                            continue
                        tpl, yr = (k.rsplit("_", 1) if "_" in k else (k, "?"))
                        parts.append(f"{_cn(UNIT_CN, tpl)}{yr}年型 x{int(v)}")
                    return parts

                all_units = _fmt_snap_units(army) + _fmt_snap_units(navy) + _fmt_snap_units(air)
                if all_units:
                    st.markdown("**部队:** " + ", ".join(all_units))


# ======================================================================
#  Tab 4: 航线安全系数
# ======================================================================

# 幻想乡子区域（用于控制程度 & 幻想乡专属航线展示）
_GENSOKYO_ZONES = ["koumakan", "hakugyokurou", "hakurei", "yakumo", "village"]


def page_routes():
    st.header("航线安全系数 & 控制程度")
    db = _db()
    nations = db.load_all_nations()
    if not nations:
        st.warning("数据库中无国家数据")
        return

    codes = list(nations.keys())
    sel = st.selectbox("选择国家", codes,
                       format_func=lambda c: f"{c} — {nations[c].name}", key="route_nation")
    if sel is None:
        return
    s = nations[sel]

    # 首都大洲
    zone_keys = list(ZONE_NAMES.keys())
    cur_zone = s.capital_zone
    zone_idx = zone_keys.index(cur_zone) if cur_zone in zone_keys else 0
    new_zone = st.selectbox(
        "首都大洲", zone_keys, index=zone_idx,
        format_func=lambda k: f"{ZONE_NAMES[k]} ({k})",
        key="route_zone",
    )

    # ── 常规航线安全系数 ─────────────────────────────────────────────────
    st.subheader("各大洲对航线安全系数（0.0 ~ 1.0）")
    st.caption("1.0 = 完全安全，0.0 = 完全封锁。陆路直连的大洲对不显示（始终 1.0）。")

    from itertools import combinations as _comb

    parent_zones = sorted(z for z in ZONE_NAMES if z not in _PARENT_ZONE)
    sea_pairs = []
    # 父大洲间
    for za, zb in _comb(parent_zones, 2):
        rk = _get_route_static(za, zb)
        if rk is not None:
            sea_pairs.append((za, zb, rk))
    # 子大洲↔直属父大洲（排除幻想乡五区域，单独展示）
    for sub_z, par_z in sorted(_PARENT_ZONE.items()):
        if sub_z in _GENSOKYO_ZONES:
            continue
        rk = _get_route_static(sub_z, par_z)
        if rk is not None:
            sea_pairs.append((sub_z, par_z, rk))

    new_safety = {}
    cols = st.columns(3)
    for i, (za, zb, rk) in enumerate(sea_pairs):
        label = f"{ZONE_NAMES.get(za, za)} ↔ {ZONE_NAMES.get(zb, zb)}"
        cur_val = float(s.route_safety.get(rk, 1.0))
        with cols[i % 3]:
            new_safety[rk] = st.slider(label, 0.0, 1.0, cur_val, 0.05, key=f"route_{rk}")

    # ── 控制程度（幻想乡五地点，与航线安全度同一机制）──────────────────
    st.subheader("控制程度（0.0 ~ 1.0）")
    st.caption("表示该国对各幻想乡地点的控制/通行程度，存储方式与航线安全系数相同。")

    gensokyo_route_pairs = []
    for gz in _GENSOKYO_ZONES:
        rk = _get_route_static(gz, "japan")
        if rk is not None:
            gensokyo_route_pairs.append((gz, rk))

    gcols = st.columns(3)
    for i, (gz, rk) in enumerate(gensokyo_route_pairs):
        label: str = ZONE_NAMES.get(gz) or gz
        cur_val = float(s.route_safety.get(rk, 1.0))
        with gcols[i % 3]:
            new_safety[rk] = st.slider(label, 0.0, 1.0, cur_val, 0.05, key=f"route_g_{rk}")

    # ── 保存 ─────────────────────────────────────────────────────────────
    if st.button("💾 保存航线 & 控制程度设置", type="primary"):
        save_safety = {k: v for k, v in new_safety.items() if abs(v - 1.0) > 0.001}
        db.conn.execute(
            "UPDATE nation SET capital_zone=?, route_safety=? WHERE code=?",
            (new_zone, json.dumps(save_safety), sel),
        )
        db.conn.commit()
        st.success(f"{s.name} 航线 & 控制程度已保存！")
        _reload()
        st.rerun()


# ======================================================================
#  Tab 5: 精神定义编辑器
# ======================================================================
MOD_KEY_CN = {
    "civ_output":              "民工产出 %",
    "mil_output":              "军备产出 %",
    "resource_output":         "资源产出 %",
    "power_output":            "电力产出 %",
    "research_speed":          "科研速度 %",
    "stability_delta":         "稳定度/回合（绝对值）",
    "war_support_delta":       "战争支持/回合（绝对值）",
    "consumer_goods_delta":    "消费品系数",
    "military_facility_fixed": "军事设施固定产能（每座工厂）",
    "artillery_tank_fixed":    "炮/坦固定产能（每座工厂）",
    "resource_factory_fixed":  "精炼工厂固定产出（每次运行）",
    "maint_reduction_land":    "陆军维护费减免 %",
    "maint_reduction_naval":   "海军维护费减免 %",
    "maint_reduction_air":     "空军维护费减免 %",
    "special_output_fixed":    "特殊产能（绝对加成）",
}


# ── 路由 ──────────────────────────────────────────────────────────────────
if tab_choice == "地块参数修改":
    page_tile()
elif tab_choice == "国家数据":
    page_nation()
elif tab_choice == "回合日志":
    page_logs()
elif tab_choice == "航线安全系数":
    page_routes()
