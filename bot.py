import discord
from discord.ext import commands, tasks
import random
import re
from combat import roll_dice_expression, run_character_attack
from items import POTIONS
from monsters import (
    calculate_monster_quantity,
    choose_monster,
    get_party_average_level,
)
from config import (
    ALLOWED_GUILD_ID,
    ALLOWED_CHANNEL_IDS,
    BONUS_DAY_CHANNEL_ID,
    TIMEZONE,
)

from database import (
    setup_database,
    save_bonus_day,
    get_bonus_day,
    generate_monthly_bonus_days,
    get_character,
    get_character_by_discord_user_id,
    create_level_1_character,
    bind_character_to_user,
    unbind_character_from_user,
    level_up_character_by_discord_user_id,
    has_leveled_up_this_month,
    undo_level_up_character,
    damage_character_by_discord_user_id,
    heal_character_full_by_discord_user_id,
    get_all_bonus_days_for_month,
    has_bonus_day_been_announced,
    mark_bonus_day_announced,
    get_active_party_characters,
    get_monthly_monster,
    save_monthly_monster,
)

from datetime import datetime, time
from zoneinfo import ZoneInfo

def game_is_open():
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    return 1 <= eastern_now.day <= 28

intents = discord.Intents.default()
intents.message_content = True



bot = commands.Bot(command_prefix="!", intents=intents)

def get_current_month_key():
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    return eastern_now.strftime("%Y-%m")


@tasks.loop(hours=1)
async def monthly_bonus_picker():
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    month = eastern_now.strftime("%Y-%m")

    created = generate_monthly_bonus_days(
        month,
        list(POTIONS.keys()),
        current_day=eastern_now.day
    )

    if created:
        print(
            f"Monthly bonus days generated for {month} "
            f"starting from day {eastern_now.day}."
        )


@tasks.loop(time=time(hour=12, minute=0, tzinfo=ZoneInfo(TIMEZONE)))
async def bonus_day_announcer():
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    month = eastern_now.strftime("%Y-%m")
    day = eastern_now.day

    potion_key = get_bonus_day(month, day)

    if potion_key is None or has_bonus_day_been_announced(month, day):
        return

    potion = POTIONS[potion_key]
    announcement = (
        "🧪 **BONUS DAY!**\n\n"
        f"{potion['emoji']} **{potion['name']}**\n"
        f"{potion['description']}"
    )

    sent_to_any_channel = False

    channel = bot.get_channel(BONUS_DAY_CHANNEL_ID)

    if channel is not None:
        await channel.send(announcement)
        sent_to_any_channel = True

    if sent_to_any_channel:
        mark_bonus_day_announced(month, day)

@bonus_day_announcer.before_loop
async def before_bonus_day_announcer():
    await bot.wait_until_ready()

@bot.command()
async def pickbonus(ctx):
    eastern_now = datetime.now(ZoneInfo(TIMEZONE))
    month = eastern_now.strftime("%Y-%m")

    created = generate_monthly_bonus_days(
        month,
        list(POTIONS.keys()),
        current_day=eastern_now.day
    )
    
@bot.command()
@commands.has_permissions(manage_guild=True)
async def peek(ctx):
    month = get_current_month_key()

    bonus_days = get_all_bonus_days_for_month(month)

    if not bonus_days:
        await ctx.send(
            "No bonus days have been generated for this month yet."
        )
        return

    response = "🪿 **The Crusading Goose whispers his secrets...**\n\n"

    for day, potion_key in bonus_days:
        potion = POTIONS[potion_key]
        response += (
            f"{month}-{day:02d} - "
            f"{potion['emoji']} {potion['name']}\n"
        )

    response += "\nPlease pretend to be surprised when they happen."

    await ctx.send(response)


def format_monthly_monster(monster):
    return (
        f"👹 **Monster of the Month: {monster['monster_name']}**\n"
        f"Threat Level: **{monster['threat_level']}**\n"
        f"Quantity: **{monster['quantity']}**\n"
        f"HP each: **{monster['hit_points']}**\n"
        f"AC: **{monster['armor_class']}**\n"
        f"Counter Damage: **{monster['counter_damage']}**\n"
        f"Party: **{monster['party_size']} characters** "
        f"(average level **{monster['party_average_level']:.2f}**)"
    )


@bot.command()
@commands.has_permissions(manage_guild=True)
async def pickmonster(ctx, month: str = None):
    month = month or get_current_month_key()

    if not re.fullmatch(r"\d{4}-\d{2}", month):
        await ctx.send("❌ Use a month like `2026-08`.")
        return
    existing_monster = get_monthly_monster(month)

    if existing_monster:
        await ctx.send(
            "🔒 This month's monster is already locked.\n\n"
            + format_monthly_monster(existing_monster)
        )
        return

    characters = get_active_party_characters()

    if not characters:
        await ctx.send("❌ There are no living characters available for monster selection.")
        return

    average_level = get_party_average_level(characters)
    monster = choose_monster(average_level, allow_restricted=False)

    if monster is None:
        await ctx.send("❌ No eligible monsters were found for this party.")
        return

    quantity = calculate_monster_quantity(monster, characters)
    saved = save_monthly_monster(
        month,
        monster,
        average_level,
        len(characters),
        quantity,
    )

    if not saved:
        await ctx.send("❌ I couldn't lock the monthly monster.")
        return

    monthly_monster = get_monthly_monster(month)
    await ctx.send(
        "🪿 **The Crusading Goose has chosen the hunt!**\n\n"
        + format_monthly_monster(monthly_monster)
    )


@bot.command()
async def currentmonster(ctx, month: str = None):
    month = month or get_current_month_key()

    if not re.fullmatch(r"\d{4}-\d{2}", month):
        await ctx.send("❌ Use a month like `2026-08`.")
        return
    monster = get_monthly_monster(month)

    if monster is None:
        await ctx.send("No monster has been selected for this month yet.")
        return

    await ctx.send(format_monthly_monster(monster))

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
async def createnew(ctx, character_name: str, class_name: str):
    existing_character = get_character_by_discord_user_id(ctx.author.id)

    if existing_character:
        await ctx.send(
            f"❌ You already have a character: **{existing_character['character_name'].title()}**."
        )
        return

    success, error = create_level_1_character(
        character_name=character_name,
        player_name=ctx.author.display_name,
        class_name=class_name,
        discord_user_id=ctx.author.id
    )

    if not success:
        await ctx.send(f"❌ {error}")
        return

    new_character = get_character(character_name)

    await ctx.send(
        f"✅ **{ctx.author.display_name}** created **{new_character['character_name'].title()}**!\n"
        f"Class: **{new_character['class_name'].title()}**\n"
        f"Level: **{new_character['level']}**\n"
        f"HP: **{new_character['current_hp']}/{new_character['max_hp']}**\n"
        f"Damage Die: **{new_character['damage_die']}**"
    )

@bot.command()
async def bindme(ctx, character_name: str):
    character = get_character(character_name)

    if not character:
        await ctx.send(f"There is no saved character named **{character_name}**.")
        return

    existing_character = get_character_by_discord_user_id(ctx.author.id)

    if existing_character:
        await ctx.send(
            f"❌ You are already bound to **{existing_character['character_name'].title()}**."
        )
        return

    if character["discord_user_id"] is not None:
        await ctx.send(
            f"❌ **{character['character_name'].title()}** is already bound to another Discord user."
        )
        return

    success = bind_character_to_user(character_name, ctx.author.id)

    if not success:
        await ctx.send("❌ I couldn't bind that character.")
        return

    await ctx.send(
        f"✅ **{ctx.author.display_name}** is now bound to **{character['character_name'].title()}**."
    )

@bot.command()
async def attack(ctx, *, personal_message: str = None):
    if not game_is_open():
        await ctx.send("The hunt is over for this month. Rest up — we begin again on the 1st.")
        return

    character = get_character_by_discord_user_id(ctx.author.id)

    if not character:
        await ctx.send(
            "You do not have a character yet. Use `!createnew name class` first."
        )
        return

    character_name = character["character_name"]

    response = run_character_attack(character_name)

    if personal_message:
        old_attack_line = f"🎲 **{character_name.title()}** attacks!"
        new_attack_line = (
            f'🎲 **{character_name.title()}** attacks by "{personal_message}"!'
        )
        response = response.replace(old_attack_line, new_attack_line, 1)

    await ctx.send(response)

@bot.command()
async def levelup(ctx):
    character = get_character_by_discord_user_id(ctx.author.id)

    if not character:
        await ctx.send(
            "You do not have a character yet. Use `!createnew name class` first."
        )
        return

    month = get_current_month_key()

    if has_leveled_up_this_month(ctx.author.id, month):
        await ctx.send(
            f"❌ **{character['character_name'].title()}** has already leveled up this month."
        )
        return

    hp_gain = random.randint(1, 4)

    result = level_up_character_by_discord_user_id(
        ctx.author.id,
        hp_gain,
        month
    )

    if result is None:
        await ctx.send("❌ I couldn't level up your character.")
        return

    updated_character = result["character"]

    await ctx.send(
        f"🎉 **{updated_character['character_name'].title()}** leveled up!\n"
        f"Level: **{result['old_level']} → {result['new_level']}**\n"
        f"HP gained: **1d4[{result['hp_gain']}]**\n"
        f"HP: **{result['old_max_hp']} → {result['new_max_hp']}**\n"
        f"Helper Dice: **{updated_character['helper_dice']}**"
    )

@bot.command()
@commands.has_permissions(manage_guild=True)
async def undolevelup(ctx, character_name: str):
    month = get_current_month_key()

    result = undo_level_up_character(character_name, month)

    if result is None:
        await ctx.send(
            f"❌ I couldn't find a level-up this month for **{character_name.title()}**."
        )
        return

    await ctx.send(
        f"↩️ **{result['character_name'].title()}**'s level-up has been undone.\n"
        f"Level: **{result['new_level']} → {result['old_level']}**\n"
        f"HP removed: **1d4[{result['hp_gain']}]**\n"
        f"HP: **{result['new_max_hp']} → {result['old_max_hp']}**"
    )

@bot.command()
async def unbindme(ctx):
    character = get_character_by_discord_user_id(ctx.author.id)

    if not character:
        await ctx.send("You do not have a bound character right now.")
        return

    success = unbind_character_from_user(ctx.author.id)

    if not success:
        await ctx.send("❌ I couldn't unbind your character.")
        return

    await ctx.send(
        f"❌ **{ctx.author.display_name}** is no longer bound to **{character['character_name'].title()}**."
    )

@bot.command()
async def mybind(ctx):
    character = get_character_by_discord_user_id(ctx.author.id)

    if character:
        await ctx.send(
            f"**{ctx.author.display_name}** is currently bound to **{character['character_name'].title()}**."
        )
    else:
        await ctx.send("You are not currently bound to any character.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    setup_database()

    if not monthly_bonus_picker.is_running():
        monthly_bonus_picker.start()

    if not bonus_day_announcer.is_running():
        bonus_day_announcer.start()

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

        character = get_character(command_name)

        if character:
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