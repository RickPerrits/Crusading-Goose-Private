"""Item data for Goose Quest.

This file contains potions and will later contain weapons,
scrolls, shop prices, and other usable items.
"""

POTIONS = {
    "healing": {
        "name": "Potion of Healing",
        "emoji": "❤️",
        "description": "All Hail the Healers! Restore yourself to full health!",
        "effect": "heal_full",
    },

    "speed": {
        "name": "Potion of Speed",
        "emoji": "⚡",
        "description": "Immediately make a second attack, at the risk of taking damage from both attacks.",
        "effect": "extra_attack",
    },

    "sharpness": {
        "name": "Oil of Sharpness",
        "emoji": "🗡️",
        "description": "Looking Sharp! +4 Attack and +4 Damage today.",
        "effect": "plus_four",
    },

    "luck": {
        "name": "Potion of Luck",
        "emoji": "🍀",
        "description": "Your attack roll becomes 11! Were you saved from a nat1? Or robbed of a Nat20? Maybe! It doesn't matter, today your roll is an 11!",
        "effect": "attack_becomes_11",
    },

    "grossness": {
        "name": "Potion of Grossness",
        "emoji": "🤢",
        "description": "Whoops, wrong potion, you now Attack at Disadvantage.",
        "effect": "disadvantage",
    },

    "invulnerability": {
        "name": "Potion of Invulnerability",
        "emoji": "🛡️",
        "description": "You take no damage today!",
        "effect": "no_damage_taken",
    },

    "possibilities": {
        "name": "Potion of Possibilities",
        "emoji": "🎲",
        "description": "Reroll one previous roll.",
        "effect": "reroll_previous",
    },

    "wealth": {
        "name": "Potion of Wealth",
        "emoji": "💰",
        "description": "All items in the shop are sold for Half Price!",
        "effect": "sale",
    },
}