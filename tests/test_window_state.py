import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk
from gwe.util.window_state import WindowState


class WindowStateTests(unittest.TestCase):
    def make_state(self, values=None):
        values = values or {}
        settings = MagicMock()
        settings.get_int.side_effect = lambda key, default: values.get(key, default)
        settings.get_bool.side_effect = lambda key, default: values.get(key, default)
        window = MagicMock()
        state = WindowState(window, settings)
        return state, window, settings

    def test_restore_normal_size_and_maximized(self):
        _, window, _ = self.make_state({'window_width': 1400, 'window_height': 1000, 'window_maximized': True})
        window.set_default_size.assert_called_once_with(1400, 1000)
        window.maximize.assert_called_once()

    def test_hidden_or_maximized_geometry_does_not_replace_normal_size(self):
        state, window, _ = self.make_state()
        for visible, flags in [(False, 0), (True, Gdk.WindowState.MAXIMIZED),
                               (True, Gdk.WindowState.ICONIFIED), (True, Gdk.WindowState.FULLSCREEN)]:
            window.get_visible.return_value = visible
            window.get_window.return_value.get_state.return_value = flags
            state.on_configure(window, SimpleNamespace(width=2000, height=1500))
            self.assertEqual((state.width, state.height), (1024, 900))

    def test_resize_is_saved_on_hide_or_shutdown(self):
        state, window, settings = self.make_state()
        window.get_visible.return_value = True
        window.get_window.return_value.get_state.return_value = 0
        with patch('gwe.util.window_state.GLib.timeout_add', return_value=5), \
             patch('gwe.util.window_state.GLib.source_remove'):
            state.on_configure(window, SimpleNamespace(width=1500, height=1100))
            state.flush()
        settings.set_int.assert_any_call('window_width', 1500)
        settings.set_int.assert_any_call('window_height', 1100)

    def test_maximize_preserves_normal_dimensions(self):
        state, _, settings = self.make_state()
        with patch('gwe.util.window_state.GLib.timeout_add', return_value=5), \
             patch('gwe.util.window_state.GLib.source_remove'):
            state.on_state(None, SimpleNamespace(changed_mask=Gdk.WindowState.MAXIMIZED,
                                                new_window_state=Gdk.WindowState.MAXIMIZED))
            state.flush()
        settings.set_bool.assert_called_once_with('window_maximized', True)
        self.assertEqual((state.width, state.height), (1024, 900))
