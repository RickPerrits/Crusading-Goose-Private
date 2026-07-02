import discord
from discord.ext import commands, tasks
import random
import re
from database import (
    setup_database,
    save_bonus_day,
    get_bonus_day,
    generate_monthly_bonus_days,
)

from datetime import datetime
from zoneinfo import ZoneInfo

def game_is_open():
    eastern_now = datetime.now(ZoneInfo("America/New_York"))
    return 1 <= eastern_now.day <= 28

intents = discord.Intents.default()
intents.message_content = True

ALLOWED_GUILD_ID = 1191364494971125780
ALLOWED_CHANNEL_IDS = {
    1191366125099950221,
}

bot = commands.Bot(command_prefix="!", intents=intents)

CHARACTERS = {
    "patrick": {
        "attack_die": "1d20",
        "helper_dice": "6d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": False,
    },
    "cassie": {
        "attack_die": "1d20",
        "helper_dice": "6d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": False,
    },
    "jay": {
        "attack_die": "1d20",
        "helper_dice": "4d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": False,
    },
    "josh": {
        "attack_die": "1d20",
        "helper_dice": "1d4",
        "damage_die": "1d10",
        "hit_threshold": 11,
        "dead": False, 
    },
    "meg": {
        "attack_die": "1d20",
        "helper_dice": None,
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": False,
    },
    "caty": {
        "attack_die": "1d20",
        "helper_dice": "8d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": False,
    },
    "ryan": {
        "attack_die": "1d20",
        "helper_dice": None,
        "damage_die": "1d8",
        "hit_threshold": 11,
        "dead": True,
    },
}

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

USER_BINDINGS = {}

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

dice_pattern = re.compile(r'([+-]?)(\d*)d(\d+)|([+-]?\d+)')


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
            f"{breakdown_one}, {breakdown_two}\n🤢 Disadvantage! Using {lower_roll}."
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

def resolve_single_attack(character_name: str, potion_effect, combat_state, attack_label=None):
    profile = CHARACTERS[character_name]
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
            helper_total, helper_breakdown = roll_dice_expression(profile["helper_dice"])
        else:
            helper_total, helper_breakdown = 0, ""

        base_damage_total, base_damage_breakdown = roll_dice_expression(profile["damage_die"])

    else:
        if profile["helper_dice"]:
            helper_total, helper_breakdown = roll_dice_expression(profile["helper_dice"])
        else:
            helper_total, helper_breakdown = 0, ""

        attack_total = d20_roll + helper_total + combat_state["attack_bonus"]
        hit = attack_total >= hit_threshold

        if hit:
            damage_total, damage_breakdown = roll_dice_expression(profile["damage_die"])
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
        attack_display = f"{d20_breakdown}{attack_bonus_display} {helper_breakdown}".strip()

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
            total_damage = (
                damage_total
                + combat_state["damage_bonus"]
            )

            damage_display = (
                f"{damage_breakdown}"
                f"{damage_bonus_display}"
            ).strip()

    else:
        total_damage = 0
        damage_display = "none"

    label_text = f"{attack_label}\n" if attack_label else ""

    attack_text = (
        f"{label_text}"
        f"Attack: {attack_display}\n"
        f"Damage: **{total_damage} Total**\n"
        f"({damage_display})"
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

def run_character_attack(character_name: str):
    profile = CHARACTERS[character_name]

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
        manual_bonus_note = "❤️ Healing is not tracked by the bot yet, but today you restore yourself to full health!"

    elif potion_effect == "reroll_previous":
        manual_bonus_note = "🎲 Reroll tracking is not automated yet. Contact the GM to reroll one previous roll."

    elif potion_effect == "extra_attack":
        pass

    elif potion_effect == "attack_becomes_11":
        pass
    
    elif potion_effect == "sale":
        manual_bonus_note = "💰 Shop prices are not tracked by the bot yet. The GM will honor today's half-price sale."

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

    response += f"🎲 **{character_name.title()}** attacks!\n"

    if potion_effect == "extra_attack":
        first_attack = resolve_single_attack(
            character_name,
            None,
            combat_state,
            attack_label="⚡ **First Attack**"
        )

        second_attack = resolve_single_attack(
            character_name,
            None,
            combat_state,
            attack_label="⚡ **Second Attack**"
        )

        response += (
            f"{first_attack['text']}\n\n"
            f"{second_attack['text']}"
        )

    else:
        attack_result = resolve_single_attack(
            character_name,
            potion_effect,
            combat_state
        )

        response += attack_result["text"]

    if combat_state["invulnerable"]:
        response += "\n🛡️ You are invulnerable today and take no damage from this attack!"

    return response

def get_current_month_key():
    eastern_now = datetime.now(ZoneInfo("America/New_York"))
    return eastern_now.strftime("%Y-%m")

def get_todays_bonus_potion(discord_user_id=None):
    eastern_now = datetime.now(ZoneInfo("America/New_York"))
    month = eastern_now.strftime("%Y-%m")
    day = eastern_now.day

    potion_key = get_bonus_day(month, day, discord_user_id)

    if potion_key is None:
        return None

    return POTIONS[potion_key]

@tasks.loop(hours=1)
async def monthly_bonus_picker():
    eastern_now = datetime.now(ZoneInfo("America/New_York"))

    if eastern_now.day != 1:
        return

    month = eastern_now.strftime("%Y-%m")

    created = generate_monthly_bonus_days(
        month,
        list(POTIONS.keys())
    )

    if created:
        print(f"Monthly bonus days generated for {month}.")

@bot.command()
async def pickbonus(ctx):
    month = get_current_month_key()

    created = generate_monthly_bonus_days(
        month,
        list(POTIONS.keys())
    )

    if created:
        await ctx.send(
            "🎁 **This month's bonus days have been secretly chosen and saved!**\n"
            "The rewards will be revealed on the day they appear."
        )
    else:
        await ctx.send(
            "🎁 Bonus days have already been chosen for this month."
        )
    
@bot.command()
async def roll(ctx, *, expression: str = "1d20"):
    try:
        total, breakdown = roll_dice_expression(expression)
        await ctx.send(
            f"🎲 **{ctx.author.display_name}** rolled `{expression}`\n"
            f"Breakdown: {breakdown}\n"
            f"**Total: {total}**"
        )
    except Exception as e:
        await ctx.send(f"That roll format looks wrong. Error: {e}")


@bot.command()
async def bindme(ctx, character_name: str):
    character_name = character_name.lower()

    if character_name not in CHARACTERS:
        await ctx.send(f"There is no saved character named **{character_name}**.")
        return

    USER_BINDINGS[ctx.author.id] = character_name
    await ctx.send(f"✅ **{ctx.author.display_name}** is now bound to **{character_name.title()}**.")


@bot.command()
async def me(ctx):
    if not game_is_open():
        await ctx.send("The hunt is over for this month. Rest up — we begin again on the 1st.")
        return

    character_name = USER_BINDINGS.get(ctx.author.id)

    if not character_name:
        await ctx.send("You are not bound to a character yet. Use `!bindme patrick` first.")
        return

    await ctx.send(run_character_attack(character_name))


@bot.command()
async def unbindme(ctx):
    if ctx.author.id in USER_BINDINGS:
        old_name = USER_BINDINGS.pop(ctx.author.id)
        await ctx.send(f"❌ **{ctx.author.display_name}** is no longer bound to **{old_name.title()}**.")
    else:
        await ctx.send("You do not have a bound character right now.")


@bot.command()
async def mybind(ctx):
    character_name = USER_BINDINGS.get(ctx.author.id)

    if character_name:
        await ctx.send(f"**{ctx.author.display_name}** is currently bound to **{character_name.title()}**.")
    else:
        await ctx.send("You are not currently bound to any character.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    setup_database()

    if not monthly_bonus_picker.is_running():
        monthly_bonus_picker.start()
    
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild is None:
        return

    if message.guild.id != ALLOWED_GUILD_ID:
        return

    if message.content.startswith("!"):
        parts = message.content[1:].strip().split(maxsplit=1)

        command_name = parts[0].lower()
        extra_text = parts[1] if len(parts) > 1 else None

        if command_name in CHARACTERS:
            if not game_is_open():
                await message.channel.send(
                    "The hunt is over for this month. Rest up — we begin again on the 1st."
                )
                return

            response = run_character_attack(command_name)
            await message.channel.send(response)
            return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

import os

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is not set.")

bot.run(TOKEN)
