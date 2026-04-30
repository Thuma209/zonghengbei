from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class FacilitySpec:
    build_cost: float
    power_use: float = 0.0
    power_gen: float = 0.0
    ic_output: float = 0.0
    tungsten_use: float = 0.0
    special_output: Optional[Dict[str, float]] = None

FACILITY_SPECS = {
    "civilian_factory": FacilitySpec(800, 8, 0, 64, 0.1),
    "military_factory": FacilitySpec(800, 10, 0, 30, 0.1),
    "dockyard": FacilitySpec(2400, 30, 0, 45, 0.1),
    "artillery_foundry": FacilitySpec(500, 6, 0, 0, 0, {"artillery": 7}),
    "engine_factory": FacilitySpec(750, 6, 0, 0, 0, {"engine": 7}),
    "tank_assembly": FacilitySpec(1000, 6, 0, 0, 0, {"tank": 6}),
    "aircraft_assembly": FacilitySpec(1000, 6, 0, 0, 0, {"aircraft": 6}),
    "steel_mill": FacilitySpec(480, 5),
    "aluminum_refinery": FacilitySpec(480, 15),
    "synthetic_oil_refinery": FacilitySpec(2500, 20),
    "synthetic_rubber_plant": FacilitySpec(3000, 30),
    "thermal_power_plant": FacilitySpec(800, 0, 150),
}

INDUSTRIAL = ("civilian_factory", "military_factory", "dockyard")
MIL_SPECIAL = ("artillery_foundry", "engine_factory", "tank_assembly", "aircraft_assembly")