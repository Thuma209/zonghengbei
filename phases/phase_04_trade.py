import hashlib
import json
from static.sea_routes import get_route


def _to_record(t):
    return {
        "nation": getattr(t, "nation", ""),
        "partner": getattr(t, "partner", ""),
        "side": getattr(t, "side", "import"),
        "kind": getattr(t, "kind", "resource"),
        "action": getattr(t, "action", "submit"),
        "agreement_id": getattr(t, "agreement_id", ""),
        "recurring": bool(getattr(t, "recurring", True)),
        "resource": getattr(t, "resource", ""),
        "quantity": float(getattr(t, "quantity", 0.0)),
        "price_per_unit": float(getattr(t, "price_per_unit", 0.0)),
        "route_safety": float(getattr(t, "route_safety", 1.0)),
        "note": getattr(t, "note", ""),
        "unit_template": getattr(t, "unit_template", ""),
        "unit_year": int(getattr(t, "unit_year", 0) or 0),
        "interest_rate": float(getattr(t, "interest_rate", 0.0)),
        "turns": int(getattr(t, "turns", 0) or 0),
        "principal": float(getattr(t, "principal", 0.0)),
    }


def _canonical_id(rec):
    payload = {
        "kind": rec["kind"],
        "a": min(rec["nation"], rec["partner"]),
        "b": max(rec["nation"], rec["partner"]),
        "resource": rec["resource"],
        "quantity": rec["quantity"],
        "price_per_unit": rec["price_per_unit"],
        "unit_template": rec["unit_template"],
        "unit_year": rec["unit_year"],
        "principal": rec["principal"],
        "interest_rate": rec["interest_rate"],
        "turns": rec["turns"],
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return f"AGR-{rec['kind']}-{digest}"


def _pair_match(a, b):
    if a["nation"] != b["partner"] or a["partner"] != b["nation"]:
        return False
    if a["side"] == b["side"]:
        return False
    if a["kind"] != b["kind"]:
        return False
    if a["kind"] == "resource":
        return (
            a["resource"] == b["resource"]
            and a["quantity"] == b["quantity"]
            and a["price_per_unit"] == b["price_per_unit"]
        )
    if a["kind"] == "military":
        return (
            a["unit_template"] == b["unit_template"]
            and a["unit_year"] == b["unit_year"]
            and a["quantity"] == b["quantity"]
            and a["price_per_unit"] == b["price_per_unit"]
        )
    if a["kind"] == "loan":
        return (
            a["principal"] == b["principal"]
            and a["interest_rate"] == b["interest_rate"]
            and a["turns"] == b["turns"]
        )
    return False


def _army_bucket(state, template):
    if template in ("submarine", "carrier", "battleship", "screen"):
        return state.navy
    if template == "airwing":
        return state.airforce
    return state.army


def _execute_resource(states, imp, all_tiles: dict = None):
    imp_state = states[imp["nation"]]
    exp_state = states[imp["partner"]]
    cost = imp["quantity"] * imp["price_per_unit"]
    if imp_state.temp["civ_ic"] < cost:
        imp_state.temp["logs"].append(
            f"贸易失败: 民用IC不足，需要 {cost:.1f}，可用 {imp_state.temp['civ_ic']:.1f}"
        )
        return
    if exp_state.stockpile.get(imp["resource"], 0) < imp["quantity"]:
        exp_state.temp["logs"].append(
            f"贸易失败: {imp['resource']} 库存不足，需要 {imp['quantity']}，仅有 {exp_state.stockpile.get(imp['resource'], 0):.1f}"
        )
        return

    imp_state.temp["civ_ic"] -= cost
    exp_state.temp["civ_ic"] += cost
    # 航线安全度：运用进口方首都大洲 ↔ 出口方首都大洲的航线（考虑陆路通道控制权）
    _route = get_route(imp_state.capital_zone, exp_state.capital_zone,
                       nation_tag=imp_state.code, all_tiles=all_tiles)
    sea_safety = imp_state.route_safety.get(_route, 1.0) if _route else 1.0
    arrived = imp["quantity"] * sea_safety
    imp_state.stockpile[imp["resource"]] = imp_state.stockpile.get(imp["resource"], 0) + arrived
    exp_state.stockpile[imp["resource"]] -= imp["quantity"]
    imp_state.temp["logs"].append(f"进口 {imp['quantity']} {imp['resource']} 从 {imp['partner']}")
    exp_state.temp["logs"].append(f"出口 {imp['quantity']} {imp['resource']} 到 {imp['nation']}")


def _execute_military(states, imp, all_tiles: dict = None):
    imp_state = states[imp["nation"]]
    exp_state = states[imp["partner"]]

    qty = int(imp["quantity"])
    cost = qty * imp["price_per_unit"]
    unit_key = f"{imp['unit_template']}_{imp['unit_year']}"

    exp_pool = _army_bucket(exp_state, imp["unit_template"])
    imp_pool = _army_bucket(imp_state, imp["unit_template"])

    if imp_state.temp["civ_ic"] < cost:
        imp_state.temp["logs"].append(f"军贸失败: 民用IC不足，需要 {cost:.1f}，可用 {imp_state.temp['civ_ic']:.1f}")
        return
    if exp_pool.get(unit_key, 0) < qty:
        exp_state.temp["logs"].append(f"军贸失败: {unit_key} 数量不足，需要 {qty}，仅有 {exp_pool.get(unit_key, 0)}")
        return

    exp_pool[unit_key] -= qty
    if exp_pool[unit_key] <= 0:
        exp_pool.pop(unit_key, None)
    # 航线安全度应用于军事贸易：按进口方首都航线安全度截笔单位数量（考虑陆路通道控制权）
    _route = get_route(imp_state.capital_zone, exp_state.capital_zone,
                       nation_tag=imp_state.code, all_tiles=all_tiles)
    sea_safety = imp_state.route_safety.get(_route, 1.0) if _route else 1.0
    arrived_qty = max(0, int(qty * sea_safety))
    imp_pool[unit_key] = imp_pool.get(unit_key, 0) + arrived_qty

    imp_state.temp["civ_ic"] -= cost
    exp_state.temp["civ_ic"] += cost
    imp_state.temp["logs"].append(f"军贸成功: 从 {imp['partner']} 进口 {arrived_qty} x {unit_key}"
                                   + (f"（航线损耗: {qty - arrived_qty}）" if arrived_qty < qty else ""))
    exp_state.temp["logs"].append(f"军贸成功: 向 {imp['nation']} 出口 {qty} x {unit_key}")


def _execute_loan(states, imp):
    borrower = states[imp["nation"]]
    lender = states[imp["partner"]]
    principal = imp["principal"]

    if lender.temp["civ_ic"] < principal:
        lender.temp["logs"].append(
            f"贷款失败: 出借方民用IC不足，需要 {principal:.1f}，可用 {lender.temp['civ_ic']:.1f}"
        )
        return

    lender.temp["civ_ic"] -= principal
    borrower.temp["civ_ic"] += principal
    borrower.temp["logs"].append(
        f"贷款到账: 从 {imp['partner']} 获得 {principal:.1f} IC，利率 {imp['interest_rate']:.2f}，期限 {imp['turns']} 回合"
    )
    lender.temp["logs"].append(
        f"发放贷款: 向 {imp['nation']} 提供 {principal:.1f} IC，利率 {imp['interest_rate']:.2f}，期限 {imp['turns']} 回合"
    )


def _settle_loan_maturity(states, db):
    if not db:
        return
    active = db.list_active_agreements()
    for a in active:
        if a.get("kind") != "loan":
            continue

        payload = a.get("payload", {})
        if not payload.get("disbursed", False):
            continue

        turns_left = int(payload.get("turns_left", payload.get("turns", 0)))
        borrower_code = a["nation"]
        lender_code = a["partner"]
        borrower = states.get(borrower_code)
        lender = states.get(lender_code)
        if not borrower or not lender:
            continue

        if turns_left > 0:
            payload["turns_left"] = turns_left - 1
            db.update_agreement_payload(a["id"], payload)
            continue

        principal = float(payload.get("principal", 0.0))
        rate = float(payload.get("interest_rate", 0.0))
        due = principal * (1.0 + rate)

        if borrower.temp["civ_ic"] >= due:
            borrower.temp["civ_ic"] -= due
            lender.temp["civ_ic"] += due
            borrower.temp["logs"].append(
                f"贷款到期已偿还: 协定 {a['id']}，支付 {due:.1f} IC"
            )
            lender.temp["logs"].append(
                f"贷款到期已收回: 协定 {a['id']}，收回 {due:.1f} IC"
            )
            db.close_agreement(a["id"], "completed")
        else:
            borrower.temp["logs"].append(
                f"【推演组注意】贷款到期违约: 协定 {a['id']}，应付 {due:.1f}，可用 {borrower.temp['civ_ic']:.1f}"
            )
            lender.temp["logs"].append(
                f"【推演组注意】贷款到期未收回: 协定 {a['id']}，应收 {due:.1f}"
            )
            payload["turns_left"] = 0
            payload["overdue"] = True
            db.update_agreement_payload(a["id"], payload)


def apply(states, all_treaties, db=None):
    # 先结算到期贷款（每回合自动）
    _settle_loan_maturity(states, db)

    # 构建全局地块字典（用于陆路通道控制权检查）
    all_tiles = {t.code: t for s in states.values() for t in s.tiles}

    records = [_to_record(t) for t in all_treaties]

    # 处理取消协定
    cancels = [r for r in records if r["action"] == "cancel"]
    for c in cancels:
        if not db or not c["agreement_id"]:
            states[c["nation"]].temp["logs"].append("取消协定失败: 缺少数据库接口或agreement_id")
            continue
        ok = db.cancel_agreement(c["agreement_id"])
        if ok:
            states[c["nation"]].temp["logs"].append(f"协定已取消: {c['agreement_id']}")
        else:
            states[c["nation"]].temp["logs"].append(f"取消协定失败: 未找到有效协定 {c['agreement_id']}")

    submits = [r for r in records if r["action"] == "submit"]

    # 每回合自动执行长期协定
    recurring_exec = []
    if db:
        active = db.list_active_agreements()
        for a in active:
            if a.get("kind") == "loan":
                # 贷款仅在签订当回合放款，后续由到期逻辑处理
                continue
            p = a.get("payload", {})
            rec = {
                "nation": a["nation"],
                "partner": a["partner"],
                "side": a["side"],
                "kind": a["kind"],
                "action": "submit",
                "agreement_id": a["id"],
                "recurring": True,
                "resource": p.get("resource", ""),
                "quantity": float(p.get("quantity", 0.0)),
                "price_per_unit": float(p.get("price_per_unit", 0.0)),
                "route_safety": float(p.get("route_safety", 1.0)),
                "note": a.get("note", ""),
                "unit_template": p.get("unit_template", ""),
                "unit_year": int(p.get("unit_year", 0) or 0),
                "interest_rate": float(p.get("interest_rate", 0.0)),
                "turns": int(p.get("turns", 0) or 0),
                "principal": float(p.get("principal", 0.0)),
            }
            recurring_exec.append(rec)

    # 匹配当回合提交的双边协定
    matched_exec = []
    used = set()
    for i, a in enumerate(submits):
        if i in used:
            continue
        for j in range(i + 1, len(submits)):
            if j in used:
                continue
            b = submits[j]
            if not _pair_match(a, b):
                continue
            used.add(i)
            used.add(j)

            imp = a if a["side"] == "import" else b
            exp = b if imp is a else a
            matched_exec.append(imp)

            if db and imp["kind"] != "loan" and (a.get("recurring", True) or b.get("recurring", True)):
                agid = imp.get("agreement_id") or exp.get("agreement_id") or _canonical_id(imp)
                recurring_flag = bool(imp.get("recurring", True) or exp.get("recurring", True))
                db.upsert_agreement(
                    {
                        "id": agid,
                        "kind": imp["kind"],
                        "nation": imp["nation"],
                        "partner": imp["partner"],
                        "side": "import",
                        "recurring": recurring_flag,
                        "payload": {
                            "resource": imp["resource"],
                            "quantity": imp["quantity"],
                            "price_per_unit": imp["price_per_unit"],
                            "route_safety": imp["route_safety"],
                            "unit_template": imp["unit_template"],
                            "unit_year": imp["unit_year"],
                            "interest_rate": imp["interest_rate"],
                            "turns": imp["turns"],
                            "turns_left": imp["turns"],
                            "principal": imp["principal"],
                            "disbursed": imp["kind"] != "loan",
                        },
                        "created_turn": states[imp["nation"]].year,
                        "note": imp.get("note", ""),
                    }
                )
                states[imp["nation"]].temp["logs"].append(f"协定生效: {agid}")

            break

    # 对未能配对的提交记录警告（单边提交不执行）
    for i, t in enumerate(submits):
        if i not in used:
            nation = t["nation"]
            partner = t["partner"]
            kind = t["kind"]
            side = t["side"]
            if kind == "resource":
                detail = f"{t['resource']} x{t['quantity']} @{t['price_per_unit']}"
            elif kind == "military":
                detail = f"{t['unit_template']}_{t['unit_year']} x{t['quantity']} @{t['price_per_unit']}"
            elif kind == "loan":
                detail = f"本金{t['principal']} 利率{t['interest_rate']} {t['turns']}回合"
            else:
                detail = ""
            msg = (
                f"【推演组注意】贸易未配对，本回合不执行: "
                f"{nation}({side}) ↔ {partner}，{kind}，{detail}。"
                f"对方未提交方向相反且条款一致的指令。"
            )
            if nation in states:
                states[nation].temp["logs"].append(msg)

    # 执行（先长期，再当回合即时提交；去重防止长期协定被重复执行）
    seen_ids = set()
    all_exec = recurring_exec + matched_exec
    for imp in all_exec:
        agid = imp.get("agreement_id")
        if agid:
            if agid in seen_ids:
                continue
            seen_ids.add(agid)
        if imp["kind"] == "resource":
            _execute_resource(states, imp, all_tiles)
        elif imp["kind"] == "military":
            _execute_military(states, imp, all_tiles)
        elif imp["kind"] == "loan":
            _execute_loan(states, imp)

            if db:
                agid = imp.get("agreement_id") or _canonical_id(imp)
                payload = {
                    "resource": imp["resource"],
                    "quantity": imp["quantity"],
                    "price_per_unit": imp["price_per_unit"],
                    "route_safety": imp["route_safety"],
                    "unit_template": imp["unit_template"],
                    "unit_year": imp["unit_year"],
                    "interest_rate": imp["interest_rate"],
                    "turns": imp["turns"],
                    "turns_left": imp["turns"],
                    "principal": imp["principal"],
                    "disbursed": True,
                }
                db.upsert_agreement(
                    {
                        "id": agid,
                        "kind": "loan",
                        "nation": imp["nation"],
                        "partner": imp["partner"],
                        "side": "import",
                        "recurring": False,
                        "payload": payload,
                        "created_turn": states[imp["nation"]].year,
                        "note": imp.get("note", ""),
                    }
                )
