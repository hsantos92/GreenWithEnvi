import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gwe.util import desktop_entry as entry
from gwe.util.desktop.desktop_parser import DesktopParser


class DesktopEntryTests(unittest.TestCase):
    def test_native_entry_repairs_old_command_and_preserves_disabled_state(self):
        with tempfile.TemporaryDirectory(prefix='gwe test ') as folder:
            root = Path(folder)
            (root / 'scripts').mkdir()
            (root / 'scripts/run-native.sh').touch()
            target = root / 'autostart/gwe.desktop'
            target.parent.mkdir()
            target.write_text('[Desktop Entry]\nType=Application\nName=GWE\nExec=gwe --hide-window\n')
            with patch.dict(os.environ, {'MESON_SOURCE_ROOT': str(root)}), \
                 patch.object(entry, 'AUTOSTART_FILE_PATH', target), \
                 patch.object(entry.sys, 'executable', '/test env/bin/python'):
                entry.set_autostart_entry(False)
            parsed = DesktopParser(str(target))
            self.assertIn('"GWE_PYTHON=/test env/bin/python"', parsed.get('Exec'))
            self.assertIn(str(root / 'scripts/run-native.sh'), parsed.get('Exec'))
            self.assertTrue(parsed.get('Exec').endswith(' --hide-window'))
            self.assertFalse(parsed.get_boolean('X-GNOME-Autostart-enabled'))
            self.assertEqual(parsed.get('Icon'), str(root / 'data/icons/com.leinardi.gwe.svg'))

    def test_installed_app_uses_installed_command_and_icon(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(entry._launch_details(), ('gwe', 'com.leinardi.gwe'))

    def test_percent_in_path_is_not_a_desktop_field_code(self):
        self.assertEqual(entry._quote_exec_arg('/tmp/100%/run'), '"/tmp/100%%/run"')
