import sqlite3

conn = sqlite3.connect('taxi.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT CHECK(role IN ('client', 'driver', 'admin')),
    phone TEXT,
    name TEXT,
    balance INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    driver_id INTEGER DEFAULT NULL,
    from_address TEXT,
    to_address TEXT,
    price INTEGER,
    status TEXT DEFAULT 'searching',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES users(user_id),
    FOREIGN KEY(driver_id) REFERENCES users(user_id)
)
''')
conn.commit()

def add_user(user_id, role, phone, name):
    cursor.execute('INSERT OR IGNORE INTO users (user_id, role, phone, name) VALUES (?, ?, ?, ?)',
                   (user_id, role, phone, name))
    conn.commit()

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    return cursor.fetchone()

def set_driver_active(user_id, active):
    cursor.execute('UPDATE users SET is_active=? WHERE user_id=?', (active, user_id))
    conn.commit()

def create_order(client_id, from_addr, to_addr, price):
    cursor.execute('''
        INSERT INTO orders (client_id, from_address, to_address, price)
        VALUES (?, ?, ?, ?)
    ''', (client_id, from_addr, to_addr, price))
    conn.commit()
    return cursor.lastrowid

def get_active_drivers():
    cursor.execute('SELECT user_id FROM users WHERE role="driver" AND is_active=1')
    return [row[0] for row in cursor.fetchall()]

def assign_driver(order_id, driver_id):
    cursor.execute('UPDATE orders SET driver_id=?, status="accepted" WHERE order_id=?', (driver_id, order_id))
    conn.commit()