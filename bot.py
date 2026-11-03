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
@commands.has_permissions(manage_guild=True)
async def peek(ctx, month: str = None):
    month = month or get_current_month_key()

    if not re.fullmatch(r"(?!0000)\d{4}-(0[1-9]|1[0-2])", month):
        await ctx.send("Use a month like 2026-11.")
        return

    response = format_dm_report(month)

    try:
        await ctx.author.send(response)
        await ctx.send("Campaign status sent to your DMs.", delete_after=10)
    except discord.Forbidden:
        await ctx.send("I couldn't send you a DM. Check your privacy settings.")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def pick(ctx, month: str = None):
    month = month or get_current_month_key()

    if not re.fullmatch(r"(?!0000)\d{4}-(0[1-9]|1[0-2])", month):
        await ctx.send("Use a month like 2026-11.")
        return

    current_month = get_current_month_key()

    if month < current_month:
        await ctx.send("Past campaigns cannot be generated. Use !peek instead.")
        return

    # Step 1: Check whether a monster already exists.
    existing_monster = get_monthly_monster(month)

    if not existing_monster:
        characters = get_active_party_characters()

        if not characters:
            await ctx.send("No living characters available for monster selection.")
            return

        average_level = get_party_average_level(characters)
        monster = choose_monster(average_level, allow_restricted=False)

        if monster is None:
            await ctx.send("No eligible monsters were found.")
            return

        quantity = calculate_monster_quantity(monster, characters)

        save_monthly_monster(
            month,
            monster,
            average_level,
            len(characters),
            quantity,
        )

    # Step 2: Generate bonus days if they don't exist.
    current_day = datetime.now(ZoneInfo(TIMEZONE)).day

    if month > current_month:
        current_day = 1

    generate_monthly_bonus_days(
        month,
        list(POTIONS.keys()),
        current_day=current_day
    )

    # Step 3: Display the saved campaign information.
    response = format_dm_report(month)

    try:
        await ctx.author.send(response)
        await ctx.send("Campaign selections sent to your DMs.", delete_after=10)
    except discord.Forbidden:
        await ctx.send("I couldn't send you a DM. Check your privacy settings.")

def format_dm_report(month):
    monster = get_monthly_monster(month)
    bonus_days = get_all_bonus_days_for_month(month)

    month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")

    current_month = get_current_month_key()
    today = datetime.now(ZoneInfo(TIMEZONE)).day

    if month > current_month:
        game_status = "Upcoming"
    elif month < current_month:
        game_status = "Completed"
    elif today <= 28:
        game_status = "Open"
    else:
        game_status = "Closed"

    response = (
        "**Goose Quest — DM Status**\n"
        f"{month_name}\n\n"
        "Bot: Online\n"
        f"Game: {game_status}\n"
    )

    if monster:
        response += (
            f"Monster: {monster['monster_name']}\n"
            f"Quantity: {monster['quantity']}\n"
        )
    else:
        response += "Monster: Not selected\n"

    response += "\n**Bonus Schedule:**\n"

    if bonus_days:
        for day, potion_key in bonus_days:
            potion = POTIONS.get(potion_key)
            potion_name = potion["name"] if potion else potion_key

            date = datetime.strptime(
                f"{month}-{day:02d}", "%Y-%m-%d"
            ).strftime("%m/%d/%y")

            response += f"{date} — {potion_name}\n"
    else:
        response += "No bonus days generated.\n"

    return response

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
        
@bot.command()
async def status(ctx):
    character = get_character_by_discord_user_id(ctx.author.id)

    if not character:
        await ctx.send(
            "You do not have a character yet. Use `!createnew name class` first.",
            delete_after=10
        )
        return

    helper_dice = character["helper_dice"] or "None"

    response = (
        f"🪿 **{character['character_name'].title()}'s Status**\n\n"

        f"⚔️ Class: **{character['class_name'].title()}**\n"
        f"⭐ Level: **{character['level']}**\n"
        f"❤️ HP: **{character['current_hp']}/{character['max_hp']}**\n"
        f"🎲 Damage Die: **{character['damage_die']}**\n"
        f"✨ Helper Dice: **{helper_dice}**\n"
        f"🪙 Gold: **{character['gold']}**\n\n"

        f"🏋️ Workouts This Month: **Coming Soon**\n"
        f"📅 Days Since Last Workout: **Coming Soon**\n"
        f"🌟 Ability Charges: **Coming Soon**\n"
        f"🎒 Equipment / Potions: **Coming Soon**"
    )

    try:
        await ctx.author.send(response)

        if ctx.guild is not None:
            await ctx.message.add_reaction("📬")

    except discord.Forbidden:
        await ctx.send(
            "❌ I couldn't DM you. Make sure you allow direct messages from members of this server.",
            delete_after=10
        )


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