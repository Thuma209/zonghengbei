RECIPE_SPECS = {
    "steel": {
        "facility": "steel_mill",
        "inputs": {"iron": 40, "coal": 10, "power": 5},
        "outputs": {"steel": 24},
        "chromium_bonus": 6,
        "chromium_cap": 1,
        "tech_required": None
    },
    "aluminum": {
        "facility": "aluminum_refinery",
        "inputs": {"bauxite": 30, "power": 15},
        "outputs": {"aluminum": 16},
        "tech_required": None
    },
    "oil": {
        "facility": "synthetic_oil_refinery",
        "inputs": {"coal": 16, "power": 20},
        "outputs": {"oil": 2.5},
        "tech_required": "resource_2"
    },
    "rubber": {
        "facility": "synthetic_rubber_plant",
        "inputs": {"power": 30},
        "outputs": {"rubber": 10},
        "tech_required": "resource_2"
    }
}