from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class BuildOrder:
    facility: str
    quantity: int = 1
    location: str = ""
    level: int = 0  # for forts

@dataclass
class RefiningOrder:
    recipe: str
    runs: float = 1.0
    bonus_chromium: float = 0.0

@dataclass
class UnitOrder:
    template: str
    year: int
    quantity: int = 1

@dataclass
class TreatyTrade:
    nation: str
    partner: str
    resource: str
    quantity: float
    price_per_unit: float
    side: str  # "import" or "export"
    route_safety: float = 1.0
    note: str = ""
    kind: str = "resource"  # resource | military | loan
    action: str = "submit"  # submit | cancel
    agreement_id: str = ""
    recurring: bool = False
    unit_template: str = ""
    unit_year: int = 0
    interest_rate: float = 0.0
    turns: int = 0
    principal: float = 0.0

@dataclass
class TurnInput:
    build_orders: List[BuildOrder] = field(default_factory=list)
    refining_orders: List[RefiningOrder] = field(default_factory=list)
    unit_orders: List[UnitOrder] = field(default_factory=list)
    research: Optional[Dict] = None  # {"tech": str, "payment": float}
    treaties: List[TreatyTrade] = field(default_factory=list)
    policy_changes: Dict[str, str] = field(default_factory=dict)