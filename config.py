"""Local application settings, with environment variables taking precedence."""

import os
from pathlib import Path

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent


def load_settings(env_file=BASE_DIR / '.env'):
    settings = {**dotenv_values(env_file, encoding='utf-8-sig'), **os.environ}
    secret_key = settings.get('SECRET_KEY', '')
    if not secret_key or not secret_key.strip():
        raise ValueError(
            'SECRET_KEY is required. Copy .env.example to .env and set a generated key, '
            'or supply it as an environment variable.'
        )

    debug = (settings.get('FLASK_DEBUG') or 'false').strip().lower()
    if debug not in {'true', 'false', '1', '0', 'yes', 'no', 'on', 'off'}:
        raise ValueError('FLASK_DEBUG must be true or false (also accepts 1/0, yes/no, on/off).')

    return {
        'SECRET_KEY': secret_key,
        'DEBUG': debug in {'true', '1', 'yes', 'on'},
    }
