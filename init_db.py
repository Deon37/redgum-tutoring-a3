import sqlite3
import os
import argparse


def init_db(upgrade=False):
    if not upgrade and os.path.exists('redgum.db'):
        os.remove('redgum.db')
    conn = sqlite3.connect('redgum.db')
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    if not upgrade:
        with open('seed.sql', 'r') as f:
            conn.executescript(f.read())
    conn.close()
    print('Database schema upgraded; existing records preserved.' if upgrade else 'Database initialised.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Set up or upgrade the Redgum database.')
    parser.add_argument('--upgrade', action='store_true', help='Apply schema additions without resetting records.')
    init_db(upgrade=parser.parse_args().upgrade)
