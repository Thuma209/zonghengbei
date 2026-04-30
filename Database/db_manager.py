import sqlite3
import json
from typing import Dict, List
from models.nation import NationState
from models.tile import Tile
from models.modifiers import ModifierSources

class DatabaseManager:
    def __init__(self, db_path: str = "game.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agreement (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                nation TEXT NOT NULL,
                partner TEXT NOT NULL,
                side TEXT NOT NULL,
                recurring INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                payload TEXT DEFAULT '{}',
                created_turn REAL DEFAULT 0,
                note TEXT DEFAULT ''
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS spirit_definition (
                key  TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                desc TEXT NOT NULL DEFAULT '',
                modifiers TEXT NOT NULL DEFAULT '{}'
            )
        """)
        # 自动迁移：为旧数据库添加 spirits / capital_zone / route_safety 列
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(nation)")}
        if "spirits" not in existing:
            self.conn.execute("ALTER TABLE nation ADD COLUMN spirits TEXT DEFAULT '[]'")
        if "capital_zone" not in existing:
            self.conn.execute("ALTER TABLE nation ADD COLUMN capital_zone TEXT DEFAULT ''")
        if "route_safety" not in existing:
            self.conn.execute("ALTER TABLE nation ADD COLUMN route_safety TEXT DEFAULT '{}'")
        self.conn.commit()
        # 首次初始化：若定义表为空则种入内嵌默认值
        if self.conn.execute("SELECT COUNT(*) FROM spirit_definition").fetchone()[0] == 0:
            from static.spirits import _DEFAULT_SPECS
            self._seed_spirit_definitions(_DEFAULT_SPECS)
        # 自动迁移：将 spirit_definition.modifiers 中旧键 special_output_pct 改名为 special_output_fixed
        for _row in self.conn.execute("SELECT key, modifiers FROM spirit_definition").fetchall():
            _mods = json.loads(_row["modifiers"])
            if "special_output_pct" in _mods:
                _mods["special_output_fixed"] = _mods.pop("special_output_pct")
                self.conn.execute("UPDATE spirit_definition SET modifiers=? WHERE key=?",
                                  (json.dumps(_mods), _row["key"]))
        # 自动迁移：将 _DEFAULT_SPECS 中新增的 modifier 键补入已有 DB 条目（不覆盖已有值）
        from static.spirits import _DEFAULT_SPECS as _DS
        for _key, _dspec in _DS.items():
            _dbrow = self.conn.execute(
                "SELECT modifiers FROM spirit_definition WHERE key=?", (_key,)
            ).fetchone()
            if _dbrow is None:
                continue
            _mods = json.loads(_dbrow["modifiers"])
            _changed = False
            for _mk, _mv in _dspec.get("modifiers", {}).items():
                if _mk not in _mods:
                    _mods[_mk] = _mv
                    _changed = True
            if _changed:
                self.conn.execute("UPDATE spirit_definition SET modifiers=? WHERE key=?",
                                  (json.dumps(_mods), _key))
        self.conn.commit()

    def _seed_spirit_definitions(self, specs: dict):
        for key, spec in specs.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO spirit_definition (key, name, desc, modifiers) VALUES (?,?,?,?)",
                (key, spec.get("name", ""), spec.get("desc", ""), json.dumps(spec.get("modifiers", {})))
            )

    def load_spirit_definitions(self) -> dict:
        """从 DB 读取全部精神定义，返回与 SPIRIT_SPECS 格式相同的 dict。"""
        result = {}
        for row in self.conn.execute("SELECT key, name, desc, modifiers FROM spirit_definition ORDER BY rowid"):
            result[row["key"]] = {
                "name": row["name"],
                "desc": row["desc"],
                "modifiers": json.loads(row["modifiers"]),
            }
        return result

    def save_all_spirit_definitions(self, specs: dict):
        """Replace 所有定义（先清表再全量写入）。"""
        self.conn.execute("DELETE FROM spirit_definition")
        self._seed_spirit_definitions(specs)
        self.conn.commit()

    def save_spirit_definition(self, key: str, spec: dict):
        """Upsert 单条精神定义。"""
        self.conn.execute(
            "INSERT OR REPLACE INTO spirit_definition (key, name, desc, modifiers) VALUES (?,?,?,?)",
            (key, spec.get("name", ""), spec.get("desc", ""), json.dumps(spec.get("modifiers", {})))
        )
        self.conn.commit()

    def delete_spirit_definition(self, key: str):
        self.conn.execute("DELETE FROM spirit_definition WHERE key=?", (key,))
        self.conn.commit()

    def exportDataByNation(self, nation: str):
        cur = self.conn.execute("select * from tile where continent =?", (nation,))
        return cur

    def load_all_nations(self) -> Dict[str, NationState]:
        nations = {}
        cur = self.conn.execute("SELECT * FROM nation")
        for row in cur:
            data = dict(row)
            state = NationState(
                code=data["code"],
                name=data["name"],
                year=data["year"],
                war_status=data["war_status"],
                stability=data["stability"],
                war_support=data["war_support"],
                civ_ic=data["civ_ic"],
                mil_ic=data["mil_ic"],
                nav_ic=data["nav_ic"],
                stockpile=json.loads(data["stockpile"]),
                facilities={},  # 先设为空，后面从地块累加
                pending_builds=json.loads(data["pending_builds"]),
                techs=set(json.loads(data["techs"])),
                research=json.loads(data["research"]),
                army=json.loads(data["army"]),
                navy=json.loads(data["navy"]),
                airforce=json.loads(data["airforce"]),
                policies=json.loads(data["policies"]),
                queued_policies=json.loads(data["queued_policies"]),
                spirits=json.loads(data["spirits"]) if data["spirits"] else [],
                capital_zone={"north_america": "americas", "south_america": "americas"}.get(
                    data.get("capital_zone") or "", data.get("capital_zone") or ""),
                route_safety=json.loads(data["route_safety"]) if data.get("route_safety") else {},
                modifiers=ModifierSources(
                    policy=json.loads(data["modifiers_policy"]),
                    tech=json.loads(data["modifiers_tech"]),
                    spirit=json.loads(data["modifiers_spirit"]),
                    stability=json.loads(data["modifiers_stability"]),
                    power_penalty=json.loads(data["modifiers_power_penalty"]),
                    temporary=json.loads(data["modifiers_temporary"]),
                )
            )
            total_facilities = {}
            cur2 = self.conn.execute("SELECT * FROM tile WHERE controller = ?", (state.code,))
            for t in cur2:
                tdata = dict(t)
                # 累加该地块的工厂数量
                tile_factories = json.loads(tdata["factories"]) if tdata["factories"] else {}
                for fac, count in tile_factories.items():
                    total_facilities[fac] = total_facilities.get(fac, 0) + count
                # 构建 Tile 对象（保持原有逻辑）
                state.tiles.append(Tile(
                    code=tdata["code"],
                    name=tdata["name"],
                    continent=tdata["continent"],
                    is_coastal=bool(tdata["is_coastal"]),
                    controller=tdata["controller"],
                    occupation_type=tdata["occupation_type"],
                    resources=json.loads(tdata["resources"]),
                    factories=tile_factories,
                    land_fort_level=tdata["land_fort_level"],
                    coastal_fort_level=tdata["coastal_fort_level"],
                ))
            # 用汇总总数覆盖 facilities 字段
            state.facilities = total_facilities
            nations[state.code] = state
        return nations

    def save_nation(self, state: NationState):
        self.conn.execute("""
            UPDATE nation SET
                year=?, war_status=?, stability=?, war_support=?,
                civ_ic=?, mil_ic=?, nav_ic=?,
                stockpile=?, facilities=?, pending_builds=?,
                techs=?, research=?, army=?, navy=?, airforce=?,
                policies=?, queued_policies=?, spirits=?,
                capital_zone=?, route_safety=?,
                modifiers_policy=?, modifiers_tech=?, modifiers_spirit=?,
                modifiers_stability=?, modifiers_power_penalty=?, modifiers_temporary=?
            WHERE code=?
        """, (
            state.year, state.war_status, state.stability, state.war_support,
            state.civ_ic, state.mil_ic, state.nav_ic,
            json.dumps(state.stockpile), json.dumps(state.facilities), json.dumps(state.pending_builds),
            json.dumps(list(state.techs)), json.dumps(state.research),
            json.dumps(state.army), json.dumps(state.navy), json.dumps(state.airforce),
            json.dumps(state.policies), json.dumps(state.queued_policies), json.dumps(state.spirits),
            state.capital_zone, json.dumps(state.route_safety),
            json.dumps(state.modifiers.policy), json.dumps(state.modifiers.tech), json.dumps(state.modifiers.spirit),
            json.dumps(state.modifiers.stability), json.dumps(state.modifiers.power_penalty), json.dumps(state.modifiers.temporary),
            state.code
        ))
        for tile in state.tiles:
            self.conn.execute("""
                UPDATE tile SET
                    occupation_type=?, resources=?, factories=?,
                    land_fort_level=?, coastal_fort_level=?
                WHERE code=?
            """, (
                tile.occupation_type, json.dumps(tile.resources), json.dumps(tile.factories),
                tile.land_fort_level, tile.coastal_fort_level, tile.code
            ))
        self.conn.commit()

    def close(self):
        self.conn.close()

    def set_nation_spirits(self, nation_code: str, spirits: list):
        """直接更新某国的国家精神列表（推演组专用）。"""
        from utils.modifiers import compute_spirit_modifiers
        new_mods = compute_spirit_modifiers(spirits)
        self.conn.execute(
            "UPDATE nation SET spirits=?, modifiers_spirit=? WHERE code=?",
            (json.dumps(spirits), json.dumps(new_mods), nation_code)
        )
        self.conn.commit()

    def get_nation_spirits(self, nation_code: str) -> list:
        row = self.conn.execute("SELECT spirits FROM nation WHERE code=?", (nation_code,)).fetchone()
        if row:
            return json.loads(row["spirits"]) if row["spirits"] else []
        return []

    def upsert_agreement(self, agreement: dict):
        self.conn.execute(
            """
            INSERT INTO agreement (id, kind, nation, partner, side, recurring, status, payload, created_turn, note)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind=excluded.kind,
                nation=excluded.nation,
                partner=excluded.partner,
                side=excluded.side,
                recurring=excluded.recurring,
                status='active',
                payload=excluded.payload,
                created_turn=excluded.created_turn,
                note=excluded.note
            """,
            (
                agreement["id"],
                agreement["kind"],
                agreement["nation"],
                agreement["partner"],
                agreement["side"],
                1 if agreement.get("recurring", True) else 0,
                json.dumps(agreement.get("payload", {})),
                float(agreement.get("created_turn", 0)),
                agreement.get("note", ""),
            ),
        )
        self.conn.commit()

    def cancel_agreement(self, agreement_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE agreement SET status='cancelled' WHERE id=? AND status='active'",
            (agreement_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def close_agreement(self, agreement_id: str, status: str = "completed") -> bool:
        cur = self.conn.execute(
            "UPDATE agreement SET status=? WHERE id=? AND status='active'",
            (status, agreement_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def update_agreement_payload(self, agreement_id: str, payload: dict) -> bool:
        cur = self.conn.execute(
            "UPDATE agreement SET payload=? WHERE id=? AND status='active'",
            (json.dumps(payload), agreement_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_active_agreements(self, nation_code: str | None = None) -> List[dict]:
        if nation_code:
            cur = self.conn.execute(
                "SELECT * FROM agreement WHERE status='active' AND (nation=? OR partner=?) ORDER BY id",
                (nation_code, nation_code),
            )
        else:
            cur = self.conn.execute("SELECT * FROM agreement WHERE status='active' ORDER BY id")
        rows = []
        for row in cur:
            d = dict(row)
            d["recurring"] = bool(d.get("recurring", 1))
            d["payload"] = json.loads(d.get("payload") or "{}")
            rows.append(d)
        return rows