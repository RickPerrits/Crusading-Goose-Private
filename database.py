import sqlite3
from pathlib import Path

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

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()
    print("Database created successfully!")