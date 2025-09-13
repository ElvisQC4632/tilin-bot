import sqlite3
from pathlib import Path

DB_FILE = Path("casino.db")
DEFAULT_START_BALANCE = 1000

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 1000
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        round_id INTEGER,
        user_id INTEGER,
        bet_type TEXT,
        amount INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        status TEXT DEFAULT 'open',
        result TEXT
    )
    """)
    conn.commit()
    conn.close()

def ensure_user(user_id: int, username: str = "", start_balance: int = DEFAULT_START_BALANCE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)",
                  (user_id, username or "", start_balance))
    else:
        if username:
            c.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id: int) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return int(row["balance"]) if row else 0

def set_balance(user_id: int, value: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, ?)",
              (user_id, "", DEFAULT_START_BALANCE))
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def add_balance(user_id: int, delta: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, ?)",
              (user_id, "", DEFAULT_START_BALANCE))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
    conn.commit()
    conn.close()

def place_bet(chat_id, round_id, user_id, bet_type, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO bets (chat_id, round_id, user_id, bet_type, amount) VALUES (?, ?, ?, ?, ?)",
              (chat_id, round_id, user_id, bet_type, amount))
    conn.commit()
    conn.close()

def get_or_open_round(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM rounds WHERE chat_id=? AND status='open'", (chat_id,))
    row = c.fetchone()
    if row:
        round_id = row[0]
    else:
        c.execute("INSERT INTO rounds (chat_id, status) VALUES (?, 'open')", (chat_id,))
        round_id = c.lastrowid
    conn.commit()
    conn.close()
    return round_id

def close_round(chat_id, result):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM rounds WHERE chat_id=? AND status='open'", (chat_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    round_id = row[0]
    c.execute("UPDATE rounds SET status='closed', result=? WHERE id=?", (result, round_id))
    conn.commit()
    conn.close()
    return round_id

def get_bets(round_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, bet_type, amount FROM bets WHERE round_id=?", (round_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def top_users(limit: int = 10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_username(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["username"] if row and row["username"] else None
