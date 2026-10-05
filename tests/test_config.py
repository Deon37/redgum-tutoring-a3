"""Configuration must be explicit without publishing private settings."""

import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from config import BASE_DIR, load_settings


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.env_file = Path(directory.name) / '.env'
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_environment_can_configure_app_without_env_file(self):
        with patch.dict(os.environ, {'SECRET_KEY': 'environment-test-key'}):
            settings = load_settings(self.env_file)
        self.assertEqual(settings['SECRET_KEY'], 'environment-test-key')
        self.assertFalse(settings['DEBUG'])

    def test_missing_or_blank_secret_is_rejected(self):
        for contents in ('', 'SECRET_KEY=', 'SECRET_KEY', 'SECRET_KEY="   "'):
            with self.subTest(contents=contents):
                self.env_file.write_text(contents, encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'SECRET_KEY is required'):
                    load_settings(self.env_file)

    def test_file_settings_support_windows_utf8_bom(self):
        self.env_file.write_text('SECRET_KEY=file-test-key\nFLASK_DEBUG=true\n', encoding='utf-8-sig')
        settings = load_settings(self.env_file)
        self.assertEqual(settings['SECRET_KEY'], 'file-test-key')
        self.assertTrue(settings['DEBUG'])
        self.assertNotIn('SECRET_KEY', os.environ)

    def test_environment_overrides_file_including_debug_false(self):
        self.env_file.write_text('SECRET_KEY=file-test-key\nFLASK_DEBUG=true\n', encoding='utf-8')
        with patch.dict(os.environ, {'SECRET_KEY': 'environment-test-key', 'FLASK_DEBUG': 'false'}):
            settings = load_settings(self.env_file)
        self.assertEqual(settings['SECRET_KEY'], 'environment-test-key')
        self.assertFalse(settings['DEBUG'])

    def test_blank_environment_secret_cannot_fall_back_to_file(self):
        self.env_file.write_text('SECRET_KEY=file-test-key\n', encoding='utf-8')
        with patch.dict(os.environ, {'SECRET_KEY': ''}):
            with self.assertRaisesRegex(ValueError, 'SECRET_KEY is required'):
                load_settings(self.env_file)

    def test_debug_boolean_values(self):
        for value, expected in (
            ('true', True), ('1', True), ('YES', True), (' On ', True),
            ('false', False), ('0', False), ('NO', False), (' Off ', False), ('', False),
        ):
            with self.subTest(value=value):
                with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': value}):
                    self.assertIs(load_settings(self.env_file)['DEBUG'], expected)

    def test_invalid_debug_flag_is_rejected(self):
        with patch.dict(os.environ, {'SECRET_KEY': 'test-only-key', 'FLASK_DEBUG': 'enabled'}):
            with self.assertRaisesRegex(ValueError, 'FLASK_DEBUG must be'):
                load_settings(self.env_file)

    def test_startup_uses_environment_settings(self):
        for debug in ('true', 'false'):
            with self.subTest(debug=debug):
                with patch.dict(os.environ, {'SECRET_KEY': 'startup-test-key', 'FLASK_DEBUG': debug}):
                    with patch('flask.Flask.run') as run_server:
                        namespace = runpy.run_path(str(BASE_DIR / 'app.py'), run_name='__main__')
                self.assertEqual(namespace['app'].secret_key, 'startup-test-key')
                self.assertIs(namespace['app'].debug, debug == 'true')
                run_server.assert_called_once_with(debug=debug == 'true', load_dotenv=False)


if __name__ == '__main__':
    unittest.main()
