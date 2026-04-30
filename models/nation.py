from dataclasses import dataclass, field
from typing import Dict, List, Set
from .modifiers import ModifierSources
from .tile import Tile

@dataclass
class NationState:
    code: str
    name: str
    year: float = 1938
    war_status: str = "peace"
    stability: float = 50.0
    war_support: float = 50.0

    civ_ic: float = 0.0
    mil_ic: float = 0.0
    nav_ic: float = 0.0

    stockpile: Dict[str, float] = field(default_factory=dict)
    facilities: Dict[str, int] = field(default_factory=dict)

    army: Dict[str, int] = field(default_factory=dict)
    navy: Dict[str, int] = field(default_factory=dict)
    airforce: Dict[str, int] = field(default_factory=dict)

    techs: Set[str] = field(default_factory=set)
    research: Dict = field(default_factory=lambda: {"current": None, "progress": 0.0, "stockpile": 0.0})

    policies: Dict[str, str] = field(default_factory=dict)
    queued_policies: Dict[str, str] = field(default_factory=dict)

    spirits: List[str] = field(default_factory=list)   # 当前激活的国家精神key列表

    capital_zone: str = ""                              # 首都所在大洲 zone key（来自 sea_routes）
    route_safety: Dict[str, float] = field(default_factory=dict)  # {route_key: 0~1}

    modifiers: ModifierSources = field(default_factory=ModifierSources)

    pending_builds: List[Dict] = field(default_factory=list)
    tiles: List[Tile] = field(default_factory=list)

    temp: Dict = field(default_factory=dict, repr=False)
