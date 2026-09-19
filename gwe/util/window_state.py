"""Persist normal window size and maximized state without saving hidden geometry."""
from gi.repository import Gdk, GLib


class WindowState:
    def __init__(self, window, settings):
        self.window = window
        self.settings = settings
        self.pending = 0
        self.width = settings.get_int('window_width', 1024)
        self.height = settings.get_int('window_height', 900)
        self.maximized = settings.get_bool('window_maximized', False)
        self.width = max(540, min(self.width, 16384))
        self.height = max(540, min(self.height, 16384))
        window.set_default_size(self.width, self.height)
        if self.maximized:
            window.maximize()
        window.connect('configure-event', self.on_configure)
        window.connect('window-state-event', self.on_state)
        window.connect('hide', self.flush)
        window.connect('delete-event', self.flush)

    def on_configure(self, window, event):
        state = window.get_window().get_state() if window.get_window() else 0
        if window.get_visible() and not state & (Gdk.WindowState.MAXIMIZED | Gdk.WindowState.FULLSCREEN | Gdk.WindowState.ICONIFIED):
            self.width, self.height = event.width, event.height
            self.schedule()
        return False

    def on_state(self, _window, event):
        if event.changed_mask & Gdk.WindowState.MAXIMIZED:
            self.maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
            self.schedule()
        return False

    def schedule(self):
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(400, self.flush)

    def flush(self, *_args):
        if self.pending:
            GLib.source_remove(self.pending)
            self.pending = 0
        for key, value in (('window_width', self.width), ('window_height', self.height)):
            if self.settings.get_int(key, 0) != value:
                self.settings.set_int(key, value)
        if self.settings.get_bool('window_maximized', False) != self.maximized:
            self.settings.set_bool('window_maximized', self.maximized)
        return False
