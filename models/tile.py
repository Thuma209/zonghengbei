from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Tile:
    code: str
    name: str
    continent: str
    is_coastal: bool
    controller: str
    occupation_type: str
    resources: Dict[str, float] = field(default_factory=dict)
    factories: Dict[str, int] = field(default_factory=dict)
    land_fort_level: int = 0
    coastal_fort_level: int = 0
