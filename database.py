import sqlite3
from datetime import datetime, timedelta

DB_PATH = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 0,
        referrer_id INTEGER,
        is_admin BOOLEAN DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Subscriptions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bot_token TEXT,
        plan_type TEXT,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Referrals tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        referrer_id INTEGER,
        referred_id INTEGER,
        UNIQUE(referred_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)", 
                   (user_id, username, referrer_id))
    conn.commit()
    conn.close()

def update_points(user_id, points):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
    conn.commit()
    conn.close()

def get_points(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_subscription(user_id, bot_token, plan_type, days):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    cursor.execute('''
    INSERT INTO subscriptions (user_id, bot_token, plan_type, start_date, end_date)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, bot_token, plan_type, start_date, end_date))
    conn.commit()
    conn.close()

def get_active_subscription(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM subscriptions 
    WHERE user_id = ? AND status = 'active' AND end_date > ?
    ''', (user_id, datetime.now()))
    sub = cursor.fetchone()
    conn.close()
    return sub

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
