import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio
from gwe.util.tray import Indicator, _XML, _PROPERTIES


class TrayTests(unittest.TestCase):
    def test_primary_and_secondary_activation_use_distinct_callbacks(self):
        tray = object.__new__(Indicator)
        tray.activate = MagicMock()
        tray.secondary_activate = MagicMock()
        for method in ('Activate', 'SecondaryActivate'):
            invocation = MagicMock()
            tray._method(None, None, None, None, method, None, invocation)
            invocation.return_value.assert_called_once_with(None)
        tray.activate.assert_called_once_with()
        tray.secondary_activate.assert_called_once_with()

    def test_activation_token_is_forwarded_without_opening_window(self):
        tray = object.__new__(Indicator)
        tray.activate = MagicMock()
        tray.provide_activation_token = MagicMock()
        invocation = MagicMock()
        tray._method(None, None, None, None, 'ProvideXdgActivationToken',
                     GLib.Variant('(s)', ('test-token',)), invocation)
        tray.provide_activation_token.assert_called_once_with('test-token')
        tray.activate.assert_not_called()
        invocation.return_value.assert_called_once_with(None)

    def test_context_menu_does_not_toggle_window(self):
        tray = object.__new__(Indicator)
        tray.activate = MagicMock()
        tray.menu = MagicMock()
        tray._method(None, None, None, None, 'ContextMenu', None, MagicMock())
        tray.menu.popup_at_pointer.assert_called_once_with(None)
        tray.activate.assert_not_called()

    def test_exported_properties_and_activation_interface_are_valid(self):
        interface = Gio.DBusNodeInfo.new_for_xml(_XML).interfaces[0]
        self.assertIsNotNone(interface.lookup_method('Activate'))
        self.assertIsNotNone(interface.lookup_method('ProvideXdgActivationToken'))
        self.assertIsNotNone(interface.lookup_method('SecondaryActivate'))
        self.assertEqual(_PROPERTIES['ItemIsMenu'], ('b', False))
        for signature, value in _PROPERTIES.values():
            GLib.Variant(signature, value)

    def test_symbolic_icon_uses_theme_lookup_without_custom_path(self):
        tray = object.__new__(Indicator)
        tray.values = dict(_PROPERTIES)
        tray.bus = MagicMock()
        with tempfile.TemporaryDirectory() as folder, patch('gwe.util.tray.xdg_data_home', folder):
            tray.set_icon_full('com.leinardi.gwe-symbolic', 'GreenWithEnvi')
            self.assertTrue((Path(folder) / 'icons/hicolor/scalable/apps/com.leinardi.gwe-symbolic.svg').is_file())
            self.assertEqual(tray.values['IconName'], ('s', 'com.leinardi.gwe-symbolic'))
            self.assertEqual(tray.values['IconThemePath'], ('s', ''))
