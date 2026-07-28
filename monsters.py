import math
import random
import re

from monster_data import MONSTERS


MONTHLY_WORKOUTS_PER_PLAYER = 10


def get_threat_level(hit_points: int) -> int:
    if hit_points <= 30:
        return 6
    if hit_points <= 60:
        return 5
    if hit_points <= 100:
        return 4
    if hit_points <= 200:
        return 3
    if hit_points <= 300:
        return 2

    return 1


def get_strongest_allowed_threat_level(average_level: float) -> int:
    if average_level <= 1:
        return 6
    if average_level <= 2:
        return 5
    if average_level <= 4:
        return 4
    if average_level <= 9:
        return 3
    if average_level <= 14:
        return 2

    return 1


def get_eligible_monsters(
    average_level: float,
    allow_restricted: bool = False,
) -> list[dict]:
    strongest_allowed = get_strongest_allowed_threat_level(average_level)
    eligible_monsters = []

    for monster in MONSTERS:
        threat_level = get_threat_level(monster["hit_points"])

        if threat_level < strongest_allowed:
            continue

        if (
            not allow_restricted
            and monster.get("source_type") == "restricted"
        ):
            continue

        eligible_monsters.append({
            **monster,
            "threat_level": threat_level,
        })

    return eligible_monsters


def choose_monster(
    average_level: float,
    allow_restricted: bool = False,
) -> dict | None:
    eligible_monsters = get_eligible_monsters(
        average_level,
        allow_restricted=allow_restricted,
    )

    if not eligible_monsters:
        return None

    return random.choice(eligible_monsters)


def get_average_die_roll(dice_expression: str | None) -> float:
    if not dice_expression:
        return 0.0

    match = re.fullmatch(r"(\d+)d(\d+)", dice_expression.strip().lower())

    if not match:
        raise ValueError(f"Unsupported dice expression: {dice_expression}")

    number_of_dice = int(match.group(1))
    die_size = int(match.group(2))
    return number_of_dice * ((die_size + 1) / 2)


def get_party_average_level(characters: list[dict]) -> float:
    if not characters:
        return 0.0

    return sum(character["level"] for character in characters) / len(characters)


def calculate_monster_quantity(monster: dict, characters: list[dict]) -> int:
    total_monthly_damage = 0.0

    for character in characters:
        average_damage_per_workout = (
            get_average_die_roll(character["damage_die"])
            + get_average_die_roll(character.get("helper_dice"))
        )
        total_monthly_damage += (
            average_damage_per_workout * MONTHLY_WORKOUTS_PER_PLAYER
        )

    quantity = math.floor(total_monthly_damage / monster["hit_points"])
    return max(1, quantity)