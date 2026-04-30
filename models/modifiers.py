from dataclasses import dataclass, field
from typing import Dict

@dataclass
class ModifierSources:
    policy: Dict[str, float] = field(default_factory=dict)
    tech: Dict[str, float] = field(default_factory=dict)
    spirit: Dict[str, float] = field(default_factory=dict)
    stability: Dict[str, float] = field(default_factory=dict)
    power_penalty: Dict[str, float] = field(default_factory=dict)
    temporary: Dict[str, float] = field(default_factory=dict)

    def total(self) -> Dict[str, float]:
        result = {}
        for src in [self.policy, self.tech, self.spirit, self.stability, self.power_penalty, self.temporary]:
            for k, v in src.items():
                result[k] = result.get(k, 0.0) + v
        return result
