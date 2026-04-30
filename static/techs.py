TECH_SPECS = {
    # === 工业科技（共5级，每级 +10%军工/+5%民工/+1军事设施产能/+5稳定） ===
    "industrial_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "effects_pct": {"civ_output": 0.05},
        "effects_abs": {"military_facility_fixed": 1.0, "stability_delta": 5.0}
    },
    "industrial_2": {
        "year": 1939, "cost": 1000, "prereq": ["industrial_1"],
        "effects_pct": {"mil_output": 0.10, "civ_output": 0.05},
        "effects_abs": {"military_facility_fixed": 1.0, "stability_delta": 5.0}
    },
    "industrial_3": {
        "year": 1942, "cost": 1000, "prereq": ["industrial_2"],
        "effects_pct": {"mil_output": 0.10, "civ_output": 0.05},
        "effects_abs": {"military_facility_fixed": 1.0, "stability_delta": 5.0}
    },
    "industrial_4": {
        "year": 1945, "cost": 1000, "prereq": ["industrial_3"],
        "effects_pct": {"mil_output": 0.10, "civ_output": 0.05},
        "effects_abs": {"military_facility_fixed": 1.0, "stability_delta": 5.0}
    },
    "industrial_5": {
        "year": 1948, "cost": 1000, "prereq": ["industrial_4"],
        "effects_pct": {"mil_output": 0.10, "civ_output": 0.05},
        "effects_abs": {"military_facility_fixed": 1.0, "stability_delta": 5.0}
    },
    # === 资源科技（共5级，1级仅+5%开采；2-4级额外+5%发电/+2资源厂产出/+1炮坦产能；5级无效果仅通知推演组） ===
    "resource_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "effects_pct": {"resource_output": 0.05}
    },
    "resource_2": {
        "year": 1939, "cost": 1000, "prereq": ["resource_1"],
        "effects_pct": {"resource_output": 0.05, "power_output": 0.05},
        "effects_abs": {"resource_factory_fixed": 2.0, "artillery_tank_fixed": 1.0}
    },
    "resource_3": {
        "year": 1942, "cost": 1000, "prereq": ["resource_2"],
        "effects_pct": {"resource_output": 0.05, "power_output": 0.05},
        "effects_abs": {"resource_factory_fixed": 2.0, "artillery_tank_fixed": 1.0}
    },
    "resource_4": {
        "year": 1945, "cost": 1000, "prereq": ["resource_3"],
        "effects_pct": {"resource_output": 0.05, "power_output": 0.05},
        "effects_abs": {"resource_factory_fixed": 2.0, "artillery_tank_fixed": 1.0}
    },
    "resource_5": {
        "year": 1948, "cost": 1000, "prereq": ["resource_4"],
        "notify_only": True,  # 无自动效果，研究完成时通知推演组手动处理
        "effects_pct": {},
        "effects_abs": {}
    },
    # === 电子学（共5级，每级 +5%科研速度） ===
    "electronics_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "effects_pct": {"research_speed": 0.05}
    },
    "electronics_2": {
        "year": 1939, "cost": 1000, "prereq": ["electronics_1"],
        "effects_pct": {"research_speed": 0.05}
    },
    "electronics_3": {
        "year": 1942, "cost": 1000, "prereq": ["electronics_2"],
        "effects_pct": {"research_speed": 0.05}
    },
    "electronics_4": {
        "year": 1945, "cost": 1000, "prereq": ["electronics_3"],
        "effects_pct": {"research_speed": 0.05}
    },
    "electronics_5": {
        "year": 1948, "cost": 1000, "prereq": ["electronics_4"],
        "effects_pct": {"research_speed": 0.05}
    },
    # === 步兵科技（共4级；1942→1945升级维护费不变） ===
    "infantry_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["infantry_1936"]
    },
    "infantry_2": {
        "year": 1939, "cost": 1000, "prereq": ["infantry_1"],
        "unlocks": ["infantry_1939"]
    },
    "infantry_3": {
        "year": 1942, "cost": 1000, "prereq": ["infantry_2"],
        "unlocks": ["infantry_1942"]
    },
    "infantry_4": {
        "year": 1945, "cost": 1000, "prereq": ["infantry_3"],
        "unlocks": ["infantry_1945"],
        "skip_maintenance_upgrade": True  # 手册注：步兵1942→1945升级维护费不变
    },
    # === 装甲科技（共4级） ===
    "armor_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["armor_1936"]
    },
    "armor_2": {
        "year": 1939, "cost": 1000, "prereq": ["armor_1"],
        "unlocks": ["armor_1939"]
    },
    "armor_3": {
        "year": 1942, "cost": 1000, "prereq": ["armor_2"],
        "unlocks": ["armor_1942"]
    },
    "armor_4": {
        "year": 1945, "cost": 1000, "prereq": ["armor_3"],
        "unlocks": ["armor_1945"]
    },
    # === 空军科技（共4级） ===
    "aircraft_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["airwing_1936"]
    },
    "aircraft_2": {
        "year": 1939, "cost": 1000, "prereq": ["aircraft_1"],
        "unlocks": ["airwing_1939"]
    },
    "aircraft_3": {
        "year": 1942, "cost": 1000, "prereq": ["aircraft_2"],
        "unlocks": ["airwing_1942"]
    },
    "aircraft_4": {
        "year": 1945, "cost": 1000, "prereq": ["aircraft_3"],
        "unlocks": ["airwing_1945"]
    },
    # === 潜艇科技（共4级） ===
    "submarine_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["submarine_1936"]
    },
    "submarine_2": {
        "year": 1939, "cost": 1000, "prereq": ["submarine_1"],
        "unlocks": ["submarine_1939"]
    },
    "submarine_3": {
        "year": 1942, "cost": 1000, "prereq": ["submarine_2"],
        "unlocks": ["submarine_1942"]
    },
    "submarine_4": {
        "year": 1945, "cost": 1000, "prereq": ["submarine_3"],
        "unlocks": ["submarine_1945"]
    },
    # === 航母科技（共4级） ===
    "carrier_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["carrier_1936"]
    },
    "carrier_2": {
        "year": 1939, "cost": 1000, "prereq": ["carrier_1"],
        "unlocks": ["carrier_1939"]
    },
    "carrier_3": {
        "year": 1942, "cost": 1000, "prereq": ["carrier_2"],
        "unlocks": ["carrier_1942"]
    },
    "carrier_4": {
        "year": 1945, "cost": 1000, "prereq": ["carrier_3"],
        "unlocks": ["carrier_1945"]
    },
    # === 战列舰科技（共4级） ===
    "battleship_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["battleship_1936"]
    },
    "battleship_2": {
        "year": 1939, "cost": 1000, "prereq": ["battleship_1"],
        "unlocks": ["battleship_1939"]
    },
    "battleship_3": {
        "year": 1942, "cost": 1000, "prereq": ["battleship_2"],
        "unlocks": ["battleship_1942"]
    },
    "battleship_4": {
        "year": 1945, "cost": 1000, "prereq": ["battleship_3"],
        "unlocks": ["battleship_1945"]
    },
    # === 屏卫舰科技（共4级） ===
    "screen_1": {
        "year": 1936, "cost": 1000, "prereq": [],
        "unlocks": ["screen_1936"]
    },
    "screen_2": {
        "year": 1939, "cost": 1000, "prereq": ["screen_1"],
        "unlocks": ["screen_1939"]
    },
    "screen_3": {
        "year": 1942, "cost": 1000, "prereq": ["screen_2"],
        "unlocks": ["screen_1942"]
    },
    "screen_4": {
        "year": 1945, "cost": 1000, "prereq": ["screen_3"],
        "unlocks": ["screen_1945"]
    },
}