import sqlite3


def init_db():
    conn = sqlite3.connect('redgum.db')
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    with open('seed.sql', 'r') as f:
        conn.executescript(f.read())
    conn.close()
    print('Database initialised.')


if __name__ == '__main__':
    init_db()
