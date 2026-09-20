"""Hidden startup must initialize controls/tray without presenting the window."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Dazzle', '1.0')
gi.require_version('Notify', '0.7')
from gwe.app import Application
from gwe.view.main_view import MainView


class HiddenStartTests(unittest.TestCase):
    def make_app(self, hidden):
        window = MagicMock()
        app = SimpleNamespace(_window=None, _builder=MagicMock(),
                              _presenter=MagicMock(), _view=MagicMock(),
                              _start_hidden=hidden)
        app._builder.get_object.return_value = window
        return app, window

    def test_hidden_start_initializes_tray_and_controls_without_showing_window(self):
        app, window = self.make_app(True)
        Application.do_activate(app)
        app._view.show.assert_called_once()
        app._view.restore_window_state.assert_called_once()
        window.show_all.assert_not_called()
        window.present.assert_not_called()
        window.get_child.return_value.show_all.assert_called_once()
        window.get_titlebar.return_value.show_all.assert_called_once()
        self.assertFalse(app._start_hidden)

    def test_normal_launch_presents_window(self):
        app, window = self.make_app(False)
        Application.do_activate(app)
        window.present.assert_called_once()
        window.hide.assert_not_called()

    def test_later_activation_opens_hidden_app_without_initializing_again(self):
        app, window = self.make_app(True)
        Application.do_activate(app)
        Application.do_activate(app)
        window.present.assert_called_once()
        app._view.show.assert_called_once()

    def test_tray_still_opens_and_hides_window(self):
        window = MagicMock()
        view = SimpleNamespace(_window=window)
        window.props.visible = False
        MainView.toggle_window_visibility(view)
        window.present.assert_called_once()
        window.props.visible = True
        MainView.toggle_window_visibility(view)
        window.hide.assert_called_once()
