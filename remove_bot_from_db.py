# remove_bot_from_db.py
import sqlite3

DB = "casino.db"
BOT_ID = 8132818875  # tu bot ID (la parte antes de ':' en el token)

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT user_id, username, balance FROM users WHERE user_id=?", (BOT_ID,))
row = c.fetchone()
if row:
    print("Encontrado en users:", row)
    c.execute("DELETE FROM users WHERE user_id=?", (BOT_ID,))
    conn.commit()
    print(f"✅ Eliminado user_id={BOT_ID} de la tabla users.")
else:
    print("No se encontró el bot en la tabla users.")
conn.close()
