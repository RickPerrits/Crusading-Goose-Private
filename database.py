import sqlite3
from pathlib import Path
import random

DB_NAME = Path(__file__).parent / "goosequest.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_user_id INTEGER UNIQUE,
            character_name TEXT NOT NULL,
            player_name TEXT,
            class_name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            current_hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            gold INTEGER NOT NULL DEFAULT 0,
            dead INTEGER NOT NULL DEFAULT 0
        )
    """)

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

    conn.commit()
    conn.close()

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
    print("Database created successfully!")

