CLASS_RULES = {
    "wizard": {"damage_die": "1d6", "starting_hp": 6},
    "sorcerer": {"damage_die": "1d6", "starting_hp": 6},

    "warlock": {"damage_die": "1d8", "starting_hp": 8},
    "rogue": {"damage_die": "1d8", "starting_hp": 8},
    "monk": {"damage_die": "1d8", "starting_hp": 8},
    "cleric": {"damage_die": "1d8", "starting_hp": 8},
    "druid": {"damage_die": "1d8", "starting_hp": 8},
    "bard": {"damage_die": "1d8", "starting_hp": 8},

    "ranger": {"damage_die": "1d10", "starting_hp": 10},
    "paladin": {"damage_die": "1d10", "starting_hp": 10},
    "fighter": {"damage_die": "1d10", "starting_hp": 10},

    "barbarian": {"damage_die": "1d12", "starting_hp": 12},
}


def get_helper_dice_for_level(level):
    helper_count = level - 1

    if helper_count <= 0:
        return None

    return f"{helper_count}d4"


def get_damage_die_for_class(class_name):
    class_key = class_name.lower()

    if class_key not in CLASS_RULES:
        raise ValueError(f"Unknown class: {class_name}")

    return CLASS_RULES[class_key]["damage_die"]