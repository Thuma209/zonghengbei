CREATE TABLE IF NOT EXISTS spirit_definition (
    key  TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    desc TEXT NOT NULL DEFAULT '',
    modifiers TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS nation (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER DEFAULT 1938,
    war_status TEXT DEFAULT 'peace',
    stability REAL DEFAULT 50.0,
    war_support REAL DEFAULT 50.0,
    civ_ic REAL DEFAULT 0.0,
    mil_ic REAL DEFAULT 0.0,
    nav_ic REAL DEFAULT 0.0,
    stockpile TEXT DEFAULT '{}',
    facilities TEXT DEFAULT '{}',
    pending_builds TEXT DEFAULT '[]',
    techs TEXT DEFAULT '[]',
    research TEXT DEFAULT '{"current": null, "progress": 0.0, "stockpile": 0.0}',
    army TEXT DEFAULT '{}',
    navy TEXT DEFAULT '{}',
    airforce TEXT DEFAULT '{}',
    policies TEXT DEFAULT '{}',
    queued_policies TEXT DEFAULT '{}',
    spirits TEXT DEFAULT '[]',
    capital_zone TEXT DEFAULT '',
    route_safety TEXT DEFAULT '{}',
    modifiers_policy TEXT DEFAULT '{}',
    modifiers_tech TEXT DEFAULT '{}',
    modifiers_spirit TEXT DEFAULT '{}',
    modifiers_stability TEXT DEFAULT '{}',
    modifiers_power_penalty TEXT DEFAULT '{}',
    modifiers_temporary TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tile (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    continent TEXT,
    is_coastal INTEGER DEFAULT 0,
    controller TEXT,
    occupation_type TEXT DEFAULT '核心',
    resources TEXT DEFAULT '{}',
    factories TEXT DEFAULT '{}',
    land_fort_level INTEGER DEFAULT 0,
    coastal_fort_level INTEGER DEFAULT 0,
    FOREIGN KEY (controller) REFERENCES nation(code)
);

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
);