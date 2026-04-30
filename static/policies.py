# static/policies.py
# 仅包含三类政策：economy_law, trade_law, tax_policy
# 完全符合手册规定，无硬编码默认值。

POLICY_SPECS = {
    "economy_law": {
        "isolationism": {
            "alpha1": 0.45,
            "pct": {"research_speed": -0.15, "mil_output": -0.10, "civ_output": -0.15},
            "abs": {"military_facility_fixed": -4}
        },
        "consumer_economy": {
            "alpha1": 0.40,
            "pct": {"research_speed": -0.10, "mil_output": -0.05, "civ_output": -0.10},
            "abs": {"military_facility_fixed": -3}
        },
        "civilian_economy": {
            "alpha1": 0.35,
            "pct": {"research_speed": -0.05, "mil_output": -0.02, "civ_output": 0.05},
            "abs": {"military_facility_fixed": -2}
        },
        "early_mobilization": {
            "alpha1": 0.30,
            "pct": {"mil_output": 0.02, "civ_output": -0.05},
            "abs": {"military_facility_fixed": -1, "stability_delta": -2.5}
        },
        "partial_mobilization": {
            "alpha1": 0.25,
            "pct": {"research_speed": 0.05, "mil_output": 0.07, "civ_output": -0.10},
            "abs": {"military_facility_fixed": 1, "stability_delta": -5.0}
        },
        "war_economy": {
            "alpha1": 0.20,
            "pct": {"research_speed": 0.10, "mil_output": 0.12, "civ_output": -0.15},
            "abs": {"military_facility_fixed": 2, "stability_delta": -7.5}
        },
        "total_mobilization": {
            "alpha1": 0.15,
            "pct": {"research_speed": 0.15, "mil_output": 0.15, "civ_output": -0.25},
            "abs": {"military_facility_fixed": 3, "stability_delta": -12.5}
        },
    },
    "trade_law": {
        "export_focus": {
            "export_ratio": 0.70,
            "pct": {"resource_output": 0.05, "research_speed": 0.15, "consumer_goods_delta": 0.02}
        },
        "free_trade": {
            "export_ratio": 0.50,
            "pct": {"resource_output": 0.03, "research_speed": 0.10, "consumer_goods_delta": 0.01}
        },
        "trade_protection": {
            "export_ratio": 0.25,
            "pct": {"resource_output": 0.01, "research_speed": -0.05},
            "abs": {"resource_factory_fixed": 0.5}
        },
        "closed_economy": {
            "export_ratio": 0.00,
            "pct": {"research_speed": -0.15},
            "abs": {"resource_factory_fixed": 1.0, "stability_delta": -2.5}
        },
    },
    "tax_policy": {
        "minimum_tax": {
            "pct": {"consumer_goods_delta": -0.02, "civ_output": 0.10, "mil_output": -0.10, "research_speed": 0.05},
            "abs": {"stability_delta": 10.0}
        },
        "low_tax": {
            "pct": {"consumer_goods_delta": -0.01, "civ_output": 0.05, "mil_output": -0.05},
            "abs": {"stability_delta": 5.0}
        },
        "average_tax": {
            "pct": {"civ_output": 0.02, "research_speed": -0.05},
            "abs": {}
        },
        "high_tax": {
            "pct": {"civ_output": -0.05, "mil_output": 0.05, "research_speed": -0.05},
            "abs": {"stability_delta": -5.0}
        },
        "maximum_tax": {
            "pct": {"consumer_goods_delta": 0.01, "mil_output": 0.10, "research_speed": -0.10},
            "abs": {"stability_delta": -10.0}
        },
    }
}

POLICY_ORDER = {
    "economy_law": [
        "isolationism", "consumer_economy", "civilian_economy",
        "early_mobilization", "partial_mobilization", "war_economy", "total_mobilization"
    ],
    "trade_law": ["export_focus", "free_trade", "trade_protection", "closed_economy"],
    "tax_policy": ["minimum_tax", "low_tax", "average_tax", "high_tax", "maximum_tax"],
}