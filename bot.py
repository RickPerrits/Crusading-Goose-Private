import discord
from discord.ext import commands
import random
import re

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
        "helper_dice": "5d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
    },
    "cassie": {
        "attack_die": "1d20",
        "helper_dice": "5d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
    },
    "jay": {
        "attack_die": "1d20",
        "helper_dice": "3d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
    },
    "josh": {
        "attack_die": "1d20",
        "helper_dice": "1d4",
        "damage_die": "1d10",
        "hit_threshold": 11,
    },
    "meg": {
        "attack_die": "1d20",
        "helper_dice": None,
        "damage_die": "1d8",
        "hit_threshold": 11,
    },
    "caty": {
        "attack_die": "1d20",
        "helper_dice": "7d4",
        "damage_die": "1d8",
        "hit_threshold": 11,
    },
    "ryan": {
        "attack_die": "1d20",
        "helper_dice": None,
        "damage_die": "Need to make a new character",
        "hit_threshold": 11,
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

def run_character_attack(character_name: str):
    profile = CHARACTERS[character_name]

    hit_threshold = profile["hit_threshold"]

    d20_roll, d20_breakdown = roll_single_d20()
    nat_text = get_nat_text(d20_roll)

    helper_total = 0
    helper_breakdown = ""
    damage_breakdown = ""
    base_damage_breakdown = ""

    original_hit = d20_roll >= hit_threshold

    if original_hit:
        hit = True

        if profile["helper_dice"]:
            helper_total, helper_breakdown = roll_dice_expression(profile["helper_dice"])
        else:
            helper_total, helper_breakdown = 0, ""

        _, base_damage_breakdown = roll_dice_expression(profile["damage_die"])

    else:
        if profile["helper_dice"]:
            helper_total, helper_breakdown = roll_dice_expression(profile["helper_dice"])
        else:
            helper_total, helper_breakdown = 0, ""

        attack_total = d20_roll + helper_total
        hit = attack_total >= hit_threshold

        if hit:
            _, damage_breakdown = roll_dice_expression(profile["damage_die"])
        else:
            damage_breakdown = "none"

    flavor_text = get_hit_or_miss_text(hit)

    if original_hit:
        attack_display = d20_breakdown
    else:
        attack_display = f"{d20_breakdown} {helper_breakdown}".strip()

    if hit:
        if original_hit:
            damage_display = f"{base_damage_breakdown} {helper_breakdown}".strip()
        else:
            damage_display = damage_breakdown
    else:
        damage_display = "none"

    response = (
        f"🎲 **{character_name.title()}** attacks!\n"
        f"Attack: {attack_display}\n"
        f"Damage: {damage_display}"
    )

    if d20_roll in (20, 1):
        response += nat_text
    else:
        response += flavor_text

    return response

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
