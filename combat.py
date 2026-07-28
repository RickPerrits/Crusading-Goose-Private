import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE
from database import (
    damage_character_by_discord_user_id,
    get_bonus_day,
    get_character,
    heal_character_full_by_discord_user_id,
)
from items import POTIONS


NAT_20_MESSAGES = [
    "🔥 **NAT 20!** The dice gods are smiling!",
    "⚔️ **CRITICAL SUCCESS!** That could not have gone better!",
    "🌟 **NAT 20!** A legendary moment unfolds!",
    "🎯 **Perfect roll!** Absolute mastery!",
    "👑 **NAT 20!** You were born for this moment!",
]

NAT_1_MESSAGES = [
    "💀 **NAT 1!** Fate has betrayed you.",
    "🍌 **Critical failure!** You somehow make it worse.",
    "😵 **NAT 1!** Disaster arrives right on cue.",
    "🪦 **Critical fail!** The dice have chosen violence.",
    "🤦 **NAT 1!** That was impressively unfortunate.",
]

HIT_MESSAGES = [
    "✅ **Hit!** Clean and effective.",
    "🗡️ **Solid strike!** That one lands.",
    "🎯 **Hit!** Right where it needed to go.",
    "⚔️ **Success!** A telling blow connects.",
]

MISS_MESSAGES = [
    "❌ **Miss!** Just off the mark.",
    "💨 **Miss!** Nothing but air.",
    "😬 **Miss!** That could have gone better.",
    "🌫️ **Miss!** Close, but not enough.",
]


dice_pattern = re.compile(r"([+-]?)(\d*)d(\d+)|([+-]?\d+)")


def roll_dice_expression(expression: str):
    expression = expression.replace(" ", "").lower()
    matches = list(dice_pattern.finditer(expression))

    total = 0
    breakdown = []

    for match in matches:
        sign, num_dice, die_size, flat_number = match.groups()

        if flat_number:
            value = int(flat_number)
            total += value
            if value >= 0:
                breakdown.append(f"+{value}" if breakdown else str(value))
            else:
                breakdown.append(str(value))
            continue

        sign_multiplier = -1 if sign == "-" else 1
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        subtotal = sum(rolls) * sign_multiplier
        total += subtotal

        prefix = "-" if sign_multiplier == -1 else "+"
        if not breakdown:
            prefix = "-" if sign_multiplier == -1 else ""

        breakdown.append(f"{prefix}{num_dice}d{die_size}{rolls}")

    return total, " ".join(breakdown)


def roll_single_d20():
    value = random.randint(1, 20)
    return value, f"1d20[{value}]"


def get_attack_roll(potion_effect):
    if potion_effect == "attack_becomes_11":
        d20_roll, d20_breakdown = roll_single_d20()
        return 11, f"{d20_breakdown}. 🍀 Lucky! It's an 11!"

    if potion_effect == "disadvantage":
        roll_one, breakdown_one = roll_single_d20()
        roll_two, breakdown_two = roll_single_d20()
        lower_roll = min(roll_one, roll_two)

        return (
            lower_roll,
            f"{breakdown_one}, {breakdown_two}\n"
            f"🤢 Disadvantage! Using {lower_roll}.",
        )

    d20_roll, d20_breakdown = roll_single_d20()
    return d20_roll, d20_breakdown


def get_nat_text(d20_roll):
    if d20_roll == 20:
        return "\n" + random.choice(NAT_20_MESSAGES)
    if d20_roll == 1:
        return "\n" + random.choice(NAT_1_MESSAGES)
    return ""


def get_hit_or_miss_text(hit):
    if hit:
        return "\n" + random.choice(HIT_MESSAGES)
    return "\n" + random.choice(MISS_MESSAGES)


def get_todays_bonus_potion(discord_user_id=None):
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    month = eastern_now.strftime("%Y-%m")
    day = eastern_now.day

    potion_key = get_bonus_day(month, day, discord_user_id)

    if potion_key is None:
        return None

    return POTIONS[potion_key]


def resolve_single_attack(
    character_name: str,
    potion_effect,
    combat_state,
    attack_label=None,
):
    profile = get_character(character_name)

    if profile is None:
        return {
            "hit": False,
            "damage_dealt": 0,
            "attack_roll": None,
            "text": (
                f"❌ I couldn't find a character named "
                f"**{character_name.title()}**."
            ),
        }

    hit_threshold = profile["hit_threshold"]

    d20_roll, d20_breakdown = get_attack_roll(potion_effect)
    nat_text = get_nat_text(d20_roll)

    helper_total = 0
    helper_breakdown = ""
    damage_breakdown = ""
    base_damage_breakdown = ""

    attack_total_without_helpers = d20_roll + combat_state["attack_bonus"]
    original_hit = attack_total_without_helpers >= hit_threshold

    if original_hit:
        hit = True

        if profile["helper_dice"]:
            helper_total, helper_breakdown = roll_dice_expression(
                profile["helper_dice"]
            )

        base_damage_total, base_damage_breakdown = roll_dice_expression(
            profile["damage_die"]
        )

    else:
        if profile["helper_dice"]:
            helper_total, helper_breakdown = roll_dice_expression(
                profile["helper_dice"]
            )

        attack_total = (
            d20_roll
            + helper_total
            + combat_state["attack_bonus"]
        )
        hit = attack_total >= hit_threshold

        if hit:
            damage_total, damage_breakdown = roll_dice_expression(
                profile["damage_die"]
            )
        else:
            damage_breakdown = "none"

    flavor_text = get_hit_or_miss_text(hit)

    attack_bonus_display = (
        f" +{combat_state['attack_bonus']}"
        if combat_state["attack_bonus"]
        else ""
    )

    if original_hit:
        attack_display = f"{d20_breakdown}{attack_bonus_display}"
    else:
        attack_display = (
            f"{d20_breakdown}{attack_bonus_display} {helper_breakdown}"
        ).strip()

    damage_bonus_display = (
        f" +{combat_state['damage_bonus']}"
        if combat_state["damage_bonus"] and hit
        else ""
    )

    if hit:
        if original_hit:
            total_damage = (
                base_damage_total
                + helper_total
                + combat_state["damage_bonus"]
            )

            damage_display = (
                f"{base_damage_breakdown} "
                f"{helper_breakdown}"
                f"{damage_bonus_display}"
            ).strip()

        else:
            total_damage = damage_total + combat_state["damage_bonus"]
            damage_display = (
                f"{damage_breakdown}{damage_bonus_display}"
            ).strip()

    else:
        total_damage = 0
        damage_display = "none"

    label_text = f"{attack_label}\n" if attack_label else ""

    if d20_roll == 1:
        total_damage = 0
        damage_display = "none"

    attack_text = (
        f"{label_text}"
        f"Attack: {attack_display}\n"
        f"Damage: **{total_damage} Total** ({damage_display})"
    )

    if d20_roll in (20, 1):
        attack_text += nat_text
    else:
        attack_text += flavor_text

    return {
        "hit": hit,
        "damage_dealt": total_damage,
        "attack_roll": d20_roll,
        "text": attack_text,
    }


def add_counterattack_text(response, profile, combat_state):
    if combat_state["invulnerable"]:
        return (
            response
            + "\n🛡️ The monster strikes back, but your "
            "invulnerability protects you!"
        )

    counter_damage = 1
    damage_result = damage_character_by_discord_user_id(
        profile["discord_user_id"],
        counter_damage,
    )

    if damage_result:
        response += (
            f"\n💥 The monster strikes back! You took "
            f"**{counter_damage} HP** damage and are now at "
            f"**{damage_result['new_hp']}/"
            f"{damage_result['character']['max_hp']} HP**."
            "\n🪿 Don’t give up — the Goose still believes in you!"
        )

    return response


def run_character_attack(character_name: str):
    profile = get_character(character_name)

    if profile is None:
        return (
            f"❌ I couldn't find a character named "
            f"**{character_name.title()}**."
        )

    todays_potion = get_todays_bonus_potion()
    potion_effect = todays_potion["effect"] if todays_potion else None

    combat_state = {
        "attack_bonus": 0,
        "damage_bonus": 0,
        "invulnerable": False,
    }

    manual_bonus_note = None

    if potion_effect == "no_damage_taken":
        combat_state["invulnerable"] = True

    elif potion_effect == "plus_four":
        combat_state["attack_bonus"] += 4
        combat_state["damage_bonus"] += 4

    elif potion_effect == "heal_full":
        healed_character = heal_character_full_by_discord_user_id(
            profile["discord_user_id"]
        )

        if healed_character:
            profile = healed_character
            manual_bonus_note = (
                "❤️ You restore yourself to full health! "
                f"HP: **{healed_character['current_hp']}/"
                f"{healed_character['max_hp']}**"
            )

    elif potion_effect == "reroll_previous":
        manual_bonus_note = (
            "🎲 Reroll tracking is not automated yet. "
            "Contact the GM to reroll one previous roll."
        )

    elif potion_effect == "sale":
        manual_bonus_note = (
            "💰 Shop prices are not tracked by the bot yet. "
            "The GM will honor today's half-price sale."
        )

    if todays_potion:
        response = (
            "🧪 **BONUS DAY!**\n\n"
            f"{todays_potion['emoji']} **{todays_potion['name']}**\n"
            f"{todays_potion['description']}\n\n"
        )
    else:
        response = ""

    if manual_bonus_note:
        response += manual_bonus_note + "\n\n"

    if profile.get("dead", False):
        return (
            f"☠️ **{character_name.title()}**, your character has perished. "
            "Please contact the GM to create a new character."
        )

    if profile["current_hp"] <= 0 and potion_effect != "heal_full":
        response += (
            f"💤 **{character_name.title()}** is unconscious!\n"
            "You can still record the workout, but you cannot deal damage "
            "until healed.\n"
            "Damage: **0 Total** (unconscious)"
        )
        return response

    response += f"🎲 **{character_name.title()}** attacks!\n"

    if potion_effect == "extra_attack":
        first_attack = resolve_single_attack(
            character_name,
            None,
            combat_state,
            attack_label="⚡ **First Attack**",
        )

        second_attack = resolve_single_attack(
            character_name,
            None,
            combat_state,
            attack_label="⚡ **Second Attack**",
        )

        response += (
            f"{first_attack['text']}\n\n"
            f"{second_attack['text']}"
        )

        for attack_result in (first_attack, second_attack):
            if not attack_result["hit"]:
                response = add_counterattack_text(
                    response,
                    profile,
                    combat_state,
                )

    else:
        attack_result = resolve_single_attack(
            character_name,
            potion_effect,
            combat_state,
        )

        response += attack_result["text"]

        if not attack_result["hit"]:
            response = add_counterattack_text(
                response,
                profile,
                combat_state,
            )

    if combat_state["invulnerable"]:
        response += (
            "\n🛡️ You are invulnerable today and take no damage "
            "from this attack!"
        )

    return response