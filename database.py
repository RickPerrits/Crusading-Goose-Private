import sqlite3
from pathlib import Path
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from config import TIMEZONE

from classes import (
    CLASS_RULES,
    get_damage_die_for_class,
    get_helper_dice_for_level,
)

DB_NAME = Path("/data/goosequest.db")

def get_connection():
    return sqlite3.connect(DB_NAME)

def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_user_id INTEGER UNIQUE,
            character_name TEXT NOT NULL UNIQUE,
            player_name TEXT,
            class_name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,

            attack_die TEXT NOT NULL DEFAULT '1d20',
            helper_dice TEXT,
            damage_die TEXT NOT NULL DEFAULT '1d8',
            hit_threshold INTEGER NOT NULL DEFAULT 11,

            current_hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            gold INTEGER NOT NULL DEFAULT 0,
            dead INTEGER NOT NULL DEFAULT 0
        )
    """)

    existing_columns = [
        row[1] for row in cursor.execute("PRAGMA table_info(characters)")
    ]

    if "attack_die" not in existing_columns:
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN attack_die TEXT NOT NULL DEFAULT '1d20'"
        )

    if "helper_dice" not in existing_columns:
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN helper_dice TEXT"
        )

    if "damage_die" not in existing_columns:
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN damage_die TEXT NOT NULL DEFAULT '1d8'"
        )

    if "hit_threshold" not in existing_columns:
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN hit_threshold INTEGER NOT NULL DEFAULT 11"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bonus_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            day INTEGER NOT NULL,
            potion_key TEXT NOT NULL,
            target_discord_id INTEGER,
            target_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bonus_day_announcements (
            month TEXT NOT NULL,
            day INTEGER NOT NULL,
            announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (month, day)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_monsters (
            month TEXT PRIMARY KEY,
            monster_name TEXT NOT NULL,
            size TEXT,
            creature_type TEXT,
            alignment TEXT,
            armor_class INTEGER NOT NULL,
            hit_points INTEGER NOT NULL,
            threat_level INTEGER NOT NULL,
            counter_damage TEXT NOT NULL,
            source_type TEXT NOT NULL,
            party_average_level REAL NOT NULL,
            party_size INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            current_hp INTEGER,
            monsters_defeated INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workout_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            workout_date TEXT NOT NULL,
            damage_rolled INTEGER NOT NULL DEFAULT 0,
            damage_dealt INTEGER NOT NULL DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id),
            UNIQUE(character_id, workout_date)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            month TEXT,
            amount INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            description TEXT,
            reward_key TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inactivity_penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            penalty_date TEXT NOT NULL,
            hp_lost INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id),
            UNIQUE(character_id, penalty_date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revival_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            revival_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_hp_resets (
            month TEXT PRIMARY KEY,
            reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_up_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            old_level INTEGER NOT NULL,
            new_level INTEGER NOT NULL,
            old_max_hp INTEGER NOT NULL,
            new_max_hp INTEGER NOT NULL,
            hp_gain INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, month),
            FOREIGN KEY (character_id) REFERENCES characters(id)
        )
    """)

    monthly_monster_columns = [
        row[1] for row in cursor.execute(
            "PRAGMA table_info(monthly_monsters)"
        )
    ]

    if "current_hp" not in monthly_monster_columns:
        cursor.execute(
            "ALTER TABLE monthly_monsters ADD COLUMN current_hp INTEGER"
        )

        cursor.execute("""
            UPDATE monthly_monsters
            SET current_hp = hit_points
            WHERE current_hp IS NULL
        """)

    if "monsters_defeated" not in monthly_monster_columns:
        cursor.execute(
            "ALTER TABLE monthly_monsters "
            "ADD COLUMN monsters_defeated INTEGER NOT NULL DEFAULT 0"
        )

    conn.commit()
    conn.close()

def get_character(character_name):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM characters
        WHERE LOWER(character_name) = LOWER(?)
        LIMIT 1
    """, (character_name,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    character = dict(row)

    character["attack_die"] = "1d20"
    character["helper_dice"] = get_helper_dice_for_level(character["level"])
    character["damage_die"] = get_damage_die_for_class(character["class_name"])
    character["hit_threshold"] = 11
    character["dead"] = bool(character["dead"])

    return character

def get_character_by_discord_user_id(discord_user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM characters
        WHERE discord_user_id = ?
        LIMIT 1
    """, (discord_user_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    character = dict(row)

    character["attack_die"] = "1d20"
    character["helper_dice"] = get_helper_dice_for_level(character["level"])
    character["damage_die"] = get_damage_die_for_class(character["class_name"])
    character["hit_threshold"] = 11
    character["dead"] = bool(character["dead"])

    return character

def bind_character_to_user(character_name, discord_user_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE characters
            SET discord_user_id = ?
            WHERE LOWER(character_name) = LOWER(?)
            AND discord_user_id IS NULL
        """, (
            discord_user_id,
            character_name
        ))

        conn.commit()

        if cursor.rowcount == 0:
            return False

        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        conn.close()

def unbind_character_from_user(discord_user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE characters
        SET discord_user_id = NULL
        WHERE discord_user_id = ?
    """, (discord_user_id,))

    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()

    return changed

def create_level_1_character(character_name, player_name, class_name, discord_user_id):
    class_key = class_name.lower()

    if class_key not in CLASS_RULES:
        return False, f"Unknown class: {class_name}"

    starting_hp = CLASS_RULES[class_key]["starting_hp"]

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO characters (
                discord_user_id,
                character_name,
                player_name,
                class_name,
                level,
                current_hp,
                max_hp,
                gold,
                dead
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            discord_user_id,
            character_name.lower(),
            player_name,
            class_key,
            1,
            starting_hp,
            starting_hp,
            0,
            0
        ))

        conn.commit()
        return True, None

    except sqlite3.IntegrityError:
        return False, "That character name is already taken, or you already have a character."

    finally:
        conn.close()

def create_character(character_name, player_name, class_name, level, current_hp, max_hp, gold=0, dead=False, discord_user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO characters (
            discord_user_id,
            character_name,
            player_name,
            class_name,
            level,
            current_hp,
            max_hp,
            gold,
            dead
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        discord_user_id,
        character_name.lower(),
        player_name,
        class_name.lower(),
        level,
        current_hp,
        max_hp,
        gold,
        1 if dead else 0
    ))

    conn.commit()
    conn.close()

def seed_starting_characters():
    create_character("patrick", "Patrick", "warlock", 7, 8, 8)
    create_character("cassie", "Cassie", "druid", 7, 8, 8)
    create_character("jay", "Jay", "bard", 5, 8, 8)
    create_character("josh", "Josh", "ranger", 2, 10, 10)
    create_character("meg", "Meg", "druid", 1, 8, 8)
    create_character("caty", "Caty", "rogue", 9, 8, 8)
    create_character("ryan", "Ryan", "warlock", 1, 8, 8, dead=True)

def has_leveled_up_this_month(discord_user_id, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM level_up_history
        WHERE character_id = (
            SELECT id
            FROM characters
            WHERE discord_user_id = ?
        )
        AND month = ?
        LIMIT 1
    """, (
        discord_user_id,
        month
    ))

    result = cursor.fetchone()
    conn.close()

    return result is not None

def level_up_character_by_discord_user_id(discord_user_id, hp_gain, month):
    character = get_character_by_discord_user_id(discord_user_id)

    if character is None:
        return None

    old_level = character["level"]
    old_max_hp = character["max_hp"]

    new_level = old_level + 1
    new_max_hp = old_max_hp + hp_gain

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE characters
            SET level = ?,
                max_hp = ?,
                current_hp = ?
            WHERE discord_user_id = ?
        """, (
            new_level,
            new_max_hp,
            new_max_hp,
            discord_user_id
        ))

        cursor.execute("""
            INSERT INTO level_up_history (
                character_id,
                month,
                old_level,
                new_level,
                old_max_hp,
                new_max_hp,
                hp_gain
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            character["id"],
            month,
            old_level,
            new_level,
            old_max_hp,
            new_max_hp,
            hp_gain
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        return None

    finally:
        conn.close()

    updated_character = get_character_by_discord_user_id(discord_user_id)

    return {
        "character": updated_character,
        "old_level": old_level,
        "new_level": new_level,
        "old_max_hp": old_max_hp,
        "new_max_hp": new_max_hp,
        "hp_gain": hp_gain,
    }

def undo_level_up_character(character_name, month):
    character = get_character(character_name)

    if character is None:
        return None

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM level_up_history
        WHERE character_id = ?
        AND month = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (
        character["id"],
        month
    ))

    history = cursor.fetchone()

    if history is None:
        conn.close()
        return None

    try:
        cursor.execute("""
            UPDATE characters
            SET level = ?,
                max_hp = ?,
                current_hp = ?
            WHERE id = ?
        """, (
            history["old_level"],
            history["old_max_hp"],
            history["old_max_hp"],
            character["id"]
        ))

        cursor.execute("""
            DELETE FROM level_up_history
            WHERE id = ?
        """, (history["id"],))

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        return None

    finally:
        conn.close()

    return {
        "character_name": character["character_name"],
        "old_level": history["old_level"],
        "new_level": history["new_level"],
        "old_max_hp": history["old_max_hp"],
        "new_max_hp": history["new_max_hp"],
        "hp_gain": history["hp_gain"],
    }

def damage_character_by_discord_user_id(discord_user_id, damage_amount):
    character = get_character_by_discord_user_id(discord_user_id)

    if character is None:
        return None

    old_hp = character["current_hp"]
    new_hp = max(old_hp - damage_amount, 0)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE characters
        SET current_hp = ?
        WHERE discord_user_id = ?
    """, (
        new_hp,
        discord_user_id
    ))

    conn.commit()
    conn.close()

    character["current_hp"] = new_hp

    return {
        "character": character,
        "old_hp": old_hp,
        "new_hp": new_hp,
        "damage_taken": damage_amount,
    }

def heal_character_full_by_discord_user_id(discord_user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        # Find the character's current HP.
        cursor.execute("""
            SELECT id, current_hp, max_hp
            FROM characters
            WHERE discord_user_id = ?
        """, (discord_user_id,))

        character = cursor.fetchone()

        if character is None:
            conn.rollback()
            return None

        was_unconscious = character["current_hp"] <= 0

        # Restore the character to full HP.
        cursor.execute("""
            UPDATE characters
            SET current_hp = max_hp
            WHERE id = ?
        """, (character["id"],))

        # Record a revival only when HP changes from 0 to positive.
        if was_unconscious and character["max_hp"] > 0:
            revival_date = datetime.now(
                ZoneInfo(TIMEZONE)
            ).strftime("%Y-%m-%d")

            record_revival(
                cursor,
                character["id"],
                revival_date
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_character_by_discord_user_id(discord_user_id)

def save_bonus_day(month, day, potion_key, target_discord_id=None, target_name=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bonus_days (
            month,
            day,
            potion_key,
            target_discord_id,
            target_name
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        month,
        day,
        potion_key,
        target_discord_id,
        target_name
    ))

    conn.commit()
    conn.close()

def clear_bonus_days_not_for_month(month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM bonus_days
        WHERE month != ?
    """, (month,))

    conn.commit()
    conn.close()

def get_bonus_day(month, day, target_discord_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if target_discord_id is not None:
        cursor.execute("""
            SELECT potion_key
            FROM bonus_days
            WHERE month = ?
            AND day = ?
            AND target_discord_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (month, day, target_discord_id))

        personal_bonus = cursor.fetchone()

        if personal_bonus:
            conn.close()
            return personal_bonus[0]

    cursor.execute("""
        SELECT potion_key
        FROM bonus_days
        WHERE month = ?
        AND day = ?
        AND target_discord_id IS NULL
        ORDER BY created_at DESC
        LIMIT 1
    """, (month, day))

    everyone_bonus = cursor.fetchone()
    conn.close()

    if everyone_bonus:
        return everyone_bonus[0]

    return None

def bonus_days_exist_for_month(month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM bonus_days
        WHERE month = ?
    """, (month,))

    count = cursor.fetchone()[0]
    conn.close()

    return count > 0

def generate_monthly_bonus_days(month, potion_keys, current_day=1):
    if bonus_days_exist_for_month(month):
        return False

    bonus_ranges = [
        (2, 7),
        (8, 14),
        (15, 21),
        (22, 28),
    ]

    available_ranges = []

    for start_day, end_day in bonus_ranges:
        earliest_available_day = max(start_day, current_day)

        if earliest_available_day <= end_day:
            available_ranges.append(
                (earliest_available_day, end_day)
            )

    if not available_ranges:
        return False

    chosen_days = [
        random.randint(start_day, end_day)
        for start_day, end_day in available_ranges
    ]

    chosen_potions = random.sample(
        potion_keys,
        len(chosen_days)
    )

    clear_bonus_days_not_for_month(month)

    for day, potion_key in zip(chosen_days, chosen_potions):
        save_bonus_day(month, day, potion_key)

    return True

def get_all_bonus_days_for_month(month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT day, potion_key
        FROM bonus_days
        WHERE month = ?
        ORDER BY day ASC
    """, (month,))

    results = cursor.fetchall()
    conn.close()

    return results


def get_active_party_characters():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM characters
        WHERE dead = 0
        ORDER BY character_name
    """)

    rows = cursor.fetchall()
    conn.close()

    characters = []

    for row in rows:
        character = dict(row)
        character["attack_die"] = "1d20"
        character["helper_dice"] = get_helper_dice_for_level(character["level"])
        character["damage_die"] = get_damage_die_for_class(character["class_name"])
        character["hit_threshold"] = 11
        character["dead"] = bool(character["dead"])
        characters.append(character)

    return characters


def save_monthly_monster(month, monster, party_average_level, party_size, quantity):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO monthly_monsters (
                month,
                monster_name,
                size,
                creature_type,
                alignment,
                armor_class,
                hit_points,
                threat_level,
                counter_damage,
                source_type,
                party_average_level,
                party_size,
                quantity,
                current_hp,
                monsters_defeated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month,
            monster["name"],
            monster.get("size"),
            monster.get("creature_type"),
            monster.get("alignment"),
            monster["armor_class"],
            monster["hit_points"],
            monster["threat_level"],
            monster["counter_damage"],
            monster.get("source_type", "open"),
            party_average_level,
            party_size,
            quantity,
            monster["hit_points"],
            0,
        ))
        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        conn.close()


def get_monthly_monster(month):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM monthly_monsters
        WHERE month = ?
        LIMIT 1
    """, (month,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None

if __name__ == "__main__":
    setup_database()
    seed_starting_characters()
    print("Database created successfully!")

def apply_damage_to_monthly_monster(month, damage_amount):
    if damage_amount <= 0:
        return None

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM monthly_monsters
        WHERE month = ?
        LIMIT 1
    """, (month,))

    row = cursor.fetchone()

    if row is None:
        conn.close()
        return None

    monster = dict(row)

    hit_points = monster["hit_points"]
    quantity = monster["quantity"]
    current_hp = monster["current_hp"]
    monsters_defeated = monster["monsters_defeated"]

    if current_hp is None:
        current_hp = hit_points

    starting_defeated = monsters_defeated
    remaining_damage = damage_amount

    while remaining_damage > 0 and monsters_defeated < quantity:

        if remaining_damage >= current_hp:
            remaining_damage -= current_hp
            monsters_defeated += 1

            if monsters_defeated >= quantity:
                current_hp = 0
                break

            current_hp = hit_points

        else:
            current_hp -= remaining_damage
            remaining_damage = 0

    cursor.execute("""
        UPDATE monthly_monsters
        SET current_hp = ?,
            monsters_defeated = ?
        WHERE month = ?
    """, (
        current_hp,
        monsters_defeated,
        month,
    ))

    conn.commit()
    conn.close()

    monsters_defeated_this_attack = (
        monsters_defeated - starting_defeated
    )

    if monsters_defeated >= quantity:
        total_remaining_hp = 0
    else:
        monsters_after_current = (
            quantity - monsters_defeated - 1
        )

        total_remaining_hp = (
            current_hp
            + (monsters_after_current * hit_points)
        )

    return {
        "monster_name": monster["monster_name"],
        "damage_dealt": damage_amount - remaining_damage,
        "current_hp": current_hp,
        "hit_points": hit_points,
        "monsters_defeated": monsters_defeated,
        "monsters_defeated_this_attack": monsters_defeated_this_attack,
        "quantity": quantity,
        "total_remaining_hp": total_remaining_hp,
        "hunt_complete": monsters_defeated >= quantity,
    }

def has_bonus_day_been_announced(month, day):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM bonus_day_announcements
        WHERE month = ?
        AND day = ?
        LIMIT 1
    """, (month, day))

    announced = cursor.fetchone() is not None
    conn.close()
    return announced

def mark_bonus_day_announced(month, day):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO bonus_day_announcements (month, day)
        VALUES (?, ?)
    """, (month, day))

    conn.commit()
    conn.close()

def get_workout_stats(character_id, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(CASE WHEN month = ? THEN 1 END),
            MAX(workout_date)
        FROM workout_history
        WHERE character_id = ?
    """, (month, character_id))

    workout_count, last_workout_date = cursor.fetchone()

    conn.close()

    return {
        "workout_count": workout_count,
        "last_workout_date": last_workout_date
    }


def calculate_potential_gold(character_id, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM workout_history
        WHERE character_id = ?
        AND month = ?
    """, (character_id, month))

    workout_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT level
        FROM characters
        WHERE id = ?
    """, (character_id,))

    character = cursor.fetchone()

    conn.close()

    if character is None:
        return 0

    level = character[0]

    return max(0, workout_count - 12) * level

def get_awarded_gold(character_id, month):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM gold_transactions
        WHERE character_id = ?
        AND month = ?
        AND transaction_type = 'workout_reward'
    """, (character_id, month))

    awarded_gold = cursor.fetchone()[0]

    conn.close()

    return awarded_gold

def award_owed_gold(cursor, character_id, month):
    # Find the character and check eligibility.
    cursor.execute("""
        SELECT level, current_hp, dead
        FROM characters
        WHERE id = ?
    """, (character_id,))

    character = cursor.fetchone()

    if character is None:
        return 0

    level, current_hp, dead = character

    if dead or current_hp <= 0:
        return 0

    # Count monthly workouts.
    cursor.execute("""
        SELECT COUNT(*)
        FROM workout_history
        WHERE character_id = ?
        AND month = ?
    """, (character_id, month))

    workout_count = cursor.fetchone()[0]

    # Calculate total qualifying gold.
    total_gold = max(0, workout_count - 12) * level

    # Find how much has already been awarded.
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM gold_transactions
        WHERE character_id = ?
        AND month = ?
        AND transaction_type = 'workout_reward'
    """, (character_id, month))

    awarded_gold = cursor.fetchone()[0]

    gold_owed = max(0, total_gold - awarded_gold)

    if gold_owed == 0:
        return 0

    # Record the reward.
    reward_key = f"workout:{month}:{character_id}:{workout_count}"

    cursor.execute("""
        INSERT INTO gold_transactions (
            character_id,
            month,
            amount,
            transaction_type,
            description,
            reward_key
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        character_id,
        month,
        gold_owed,
        "workout_reward",
        "Monthly workout gold",
        reward_key
    ))

    # Add earned gold to the spendable balance.
    cursor.execute("""
        UPDATE characters
        SET gold = gold + ?
        WHERE id = ?
    """, (gold_owed, character_id))

    return gold_owed

def award_party_victory_gold(cursor, month):
    # Find all characters participating in the campaign.
    cursor.execute("""
        SELECT id
        FROM characters
        WHERE dead = 0
        AND discord_user_id IS NOT NULL
    """)

    characters = cursor.fetchall()

    total_gold_awarded = 0
    players_rewarded = 0

    # Award outstanding gold to each eligible character.
    for character in characters:
        character_id = character[0]

        gold_awarded = award_owed_gold(
            cursor,
            character_id,
            month
        )

        if gold_awarded > 0:
            total_gold_awarded += gold_awarded
            players_rewarded += 1

    return {
        "total_gold_awarded": total_gold_awarded,
        "players_rewarded": players_rewarded
    }

def has_workout_for_date(character_id, workout_date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM workout_history
        WHERE character_id = ?
        AND workout_date = ?
        LIMIT 1
    """, (character_id, workout_date))

    workout_exists = cursor.fetchone() is not None

    conn.close()

    return workout_exists


def save_workout(character_id, workout_date, damage_rolled, damage_dealt):
    month = workout_date[:7]

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO workout_history (
                character_id,
                month,
                workout_date,
                damage_rolled,
                damage_dealt
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            character_id,
            month,
            workout_date,
            damage_rolled,
            damage_dealt
        ))

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        conn.rollback()
        return False

    finally:
        conn.close()


def record_workout_and_apply_damage(
    character_id,
    workout_date,
    damage_rolled,
    counter_damage=0,
    heal_full=False
):
    month = workout_date[:7]

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Lock the database for this workout transaction.
        cursor.execute("BEGIN IMMEDIATE")

        # Check for an existing workout.
        cursor.execute("""
            SELECT 1 FROM workout_history
            WHERE character_id = ? AND workout_date = ?
        """, (character_id, workout_date))

        if cursor.fetchone():
            conn.rollback()
            return None

        # Find the monthly monster.
        cursor.execute("""
            SELECT * FROM monthly_monsters
            WHERE month = ?
        """, (month,))

        
        row = cursor.fetchone()
        monster = dict(row) if row else None

        # Was the hunt already complete before this workout?
        was_hunt_complete = (
            monster is not None
            and monster["monsters_defeated"] >= monster["quantity"]
        )

        damage_dealt = 0
        monsters_defeated_this_attack = 0
        hunt_complete = False

        if monster:
            hp = monster["hit_points"]
            quantity = monster["quantity"]
            defeated = monster["monsters_defeated"]
            current_hp = monster["current_hp"]

            if current_hp is None:
                current_hp = hp

            remaining_damage = max(0, damage_rolled)

            while remaining_damage > 0 and defeated < quantity:
                applied = min(remaining_damage, current_hp)
                damage_dealt += applied
                remaining_damage -= applied
                current_hp -= applied

                if current_hp == 0:
                    defeated += 1
                    monsters_defeated_this_attack += 1

                    if defeated < quantity:
                        current_hp = hp

            hunt_complete = defeated >= quantity

            cursor.execute("""
                UPDATE monthly_monsters
                SET current_hp = ?,
                    monsters_defeated = ?
                WHERE month = ?
            """, (current_hp, defeated, month))

        # Record one workout, regardless of hit or miss.
        cursor.execute("""
            INSERT INTO workout_history (
                character_id,
                month,
                workout_date,
                damage_rolled,
                damage_dealt
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            character_id,
            month,
            workout_date,
            damage_rolled,
            damage_dealt
        ))

        # Calculate the character's HP after combat.
        cursor.execute("""
            SELECT current_hp, max_hp
            FROM characters
            WHERE id = ?
        """, (character_id,))

        character_row = cursor.fetchone()

        if character_row is None:
            raise ValueError("Character not found.")

        new_hp = character_row["current_hp"]

        if heal_full:
            new_hp = character_row["max_hp"]

        new_hp = max(0, new_hp - counter_damage)

        # Check whether the character was revived.
        was_unconscious = character_row["current_hp"] <= 0
        is_now_conscious = new_hp > 0

        if was_unconscious and is_now_conscious:
            record_revival(
                cursor,
                character_id,
                workout_date
            )

        cursor.execute("""
            UPDATE characters
            SET current_hp = ?
            WHERE id = ?
        """, (new_hp, character_id))

        # Handle gold rewards after combat and HP updates.
        gold_awarded = 0
        party_gold_awarded = 0
        players_rewarded = 0

        if monster and hunt_complete:

            if not was_hunt_complete:
                # The final monster was just defeated.
                # Award accumulated gold to the whole party.
                party_rewards = award_party_victory_gold(
                    cursor,
                    month
                )

                party_gold_awarded = party_rewards["total_gold_awarded"]
                players_rewarded = party_rewards["players_rewarded"]

            else:
                # The hunt was already complete.
                # Award this character's additional gold.
                gold_awarded = award_owed_gold(
                    cursor,
                    character_id,
                    month
                )

        # Save both changes together.
        conn.commit()

        return {
            "damage_rolled": damage_rolled,
            "damage_dealt": damage_dealt,
            "new_hp": new_hp,
            "monster_name": monster["monster_name"] if monster else None,
            "monsters_defeated_this_attack": monsters_defeated_this_attack,
            "hunt_complete": hunt_complete,
            "gold_awarded": gold_awarded,
            "party_gold_awarded": party_gold_awarded,
            "players_rewarded": players_rewarded,
        }

    except sqlite3.IntegrityError:
        conn.rollback()
        return None

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def record_revival(cursor, character_id, revival_date):
    cursor.execute("""
        INSERT INTO revival_history (
            character_id,
            revival_date
        )
        VALUES (?, ?)
    """, (character_id, revival_date))

def get_last_revival_date(character_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MAX(revival_date)
        FROM revival_history
        WHERE character_id = ?
    """, (character_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

def count_inactive_game_days(last_reset_date, check_date):
    # Convert saved date strings into Python dates.
    start_date = date.fromisoformat(last_reset_date)
    end_date = date.fromisoformat(check_date)

    inactive_days = 0
    current_date = start_date + timedelta(days=1)

    while current_date <= end_date:
        # Only days 1 through 28 count.
        if 1 <= current_date.day <= 28:
            inactive_days += 1

        current_date += timedelta(days=1)

    return inactive_days

def get_inactivity_penalty_dates(character_id, check_date):
    conn = get_connection()
    cursor = conn.cursor()

    # Retrieve all workouts and revivals.
    cursor.execute("""
        SELECT workout_date
        FROM workout_history
        WHERE character_id = ?

        UNION

        SELECT revival_date
        FROM revival_history
        WHERE character_id = ?
    """, (character_id, character_id))

    reset_dates = {
        date.fromisoformat(row[0])
        for row in cursor.fetchall()
    }

    conn.close()

    # No workout or revival means the clock
    # has not started yet.
    if not reset_dates:
        return []

    end_date = date.fromisoformat(check_date)
    current_date = min(reset_dates)
    inactive_days = 0
    penalty_dates = []

    while current_date <= end_date:

        # Reset the inactivity clock at the start of each month.
        if current_date.day == 1:
            inactive_days = 0

        if current_date in reset_dates:
            # A workout or revival resets the clock.
            inactive_days = 0

        elif 1 <= current_date.day <= 28:
            inactive_days += 1

            if inactive_days >= 6:
                penalty_dates.append(
                    current_date.isoformat()
                )

        current_date += timedelta(days=1)

    # Only return penalties after the most recent reset.
    last_reset = max(
        (
            reset_day for reset_day in reset_dates
            if reset_day <= end_date
        ),
        default=None
    )

    if last_reset is None:
        return []

    # Never carry penalties into a new month.
    month_start = end_date.replace(day=1)
    last_reset = max(last_reset, month_start)


    return [
        penalty_day for penalty_day in penalty_dates
        if penalty_day > last_reset.isoformat()
    ]

def apply_inactivity_penalties(character_id, check_date):
    # Find dates that qualify for inactivity penalties.
    penalty_dates = get_inactivity_penalty_dates(
        character_id,
        check_date
    )

    # Only process penalties from the month being checked.
    month = check_date[:7]
    penalty_dates = [
        day for day in penalty_dates
        if day.startswith(month)
    ]

    conn = get_connection()
    cursor = conn.cursor()

    hp_lost = 0

    try:
        cursor.execute("BEGIN IMMEDIATE")

        for penalty_date in penalty_dates:
            # Check the character's current HP.
            cursor.execute("""
                SELECT current_hp
                FROM characters
                WHERE id = ?
            """, (character_id,))

            character = cursor.fetchone()

            if character is None or character[0] <= 0:
                break

            # Record the penalty only if it hasn't
            # already been processed.
            cursor.execute("""
                INSERT OR IGNORE INTO inactivity_penalties (
                    character_id,
                    penalty_date,
                    hp_lost
                )
                VALUES (?, ?, 1)
            """, (character_id, penalty_date))

            if cursor.rowcount == 0:
                continue

            # Deduct one HP without going below zero.
            cursor.execute("""
                UPDATE characters
                SET current_hp = MAX(0, current_hp - 1)
                WHERE id = ?
            """, (character_id,))

            hp_lost += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return hp_lost

def restore_monthly_hp(month):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        # Claim this month's reset.
        cursor.execute("""
            INSERT OR IGNORE INTO monthly_hp_resets (month)
            VALUES (?)
        """, (month,))

        # If the record already exists, do nothing.
        if cursor.rowcount == 0:
            conn.rollback()
            return False

        # Restore HP for living characters.
        cursor.execute("""
            UPDATE characters
            SET current_hp = max_hp
            WHERE dead = 0
        """)

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
