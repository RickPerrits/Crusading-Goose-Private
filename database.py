import sqlite3
from pathlib import Path
import random

DB_NAME = Path("/data/goosequest.db")

def get_connection():
    return sqlite3.connect(DB_NAME)

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
    character = get_character_by_discord_user_id(discord_user_id)

    if character is None:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE characters
        SET current_hp = max_hp
        WHERE discord_user_id = ?
    """, (discord_user_id,))

    conn.commit()
    conn.close()

    character["current_hp"] = character["max_hp"]

    return character

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

def generate_monthly_bonus_days(month, potion_keys):
    if bonus_days_exist_for_month(month):
        return False

    chosen_days = [
        random.randint(2, 7),
        random.randint(8, 14),
        random.randint(15, 21),
        random.randint(22, 28),
    ]

    chosen_potions = random.sample(potion_keys, 4)

    clear_bonus_days_not_for_month(month)

    for day, potion_key in zip(chosen_days, chosen_potions):
        save_bonus_day(month, day, potion_key)

    return True

if __name__ == "__main__":
    setup_database()
    seed_starting_characters()
    print("Database created successfully!")
