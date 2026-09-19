"""StatusNotifierItem with window activation and a separate context menu.

Hosts choose the gesture: GNOME AppIndicator uses double/middle click; other
hosts commonly send Activate for a single primary click.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path
from xdg.BaseDirectory import xdg_data_home
import gi
gi.require_version('Dbusmenu', '0.4')
gi.require_version('DbusmenuGtk3', '0.4')
from gi.repository import Gio, GLib, Dbusmenu, DbusmenuGtk3

_LOG = logging.getLogger(__name__)
_INTERFACE = 'org.kde.StatusNotifierItem'
_PATH = '/StatusNotifierItem'
_MENU = '/GreenWithEnviMenu'
_PROPERTIES = {
    'Category': ('s', 'Hardware'), 'Id': ('s', 'GreenWithEnvi'),
    'Title': ('s', 'GreenWithEnvi'), 'Status': ('s', 'Active'),
    'WindowId': ('i', 0), 'ItemIsMenu': ('b', False), 'Menu': ('o', _MENU),
    'IconName': ('s', ''), 'IconThemePath': ('s', ''),
    'IconPixmap': ('a(iiay)', []), 'OverlayIconName': ('s', ''),
    'OverlayIconPixmap': ('a(iiay)', []), 'AttentionIconName': ('s', ''),
    'AttentionIconPixmap': ('a(iiay)', []), 'AttentionMovieName': ('s', ''),
    'XAyatanaLabel': ('s', ''), 'XAyatanaLabelGuide': ('s', ''),
}
_XML = '<node><interface name="' + _INTERFACE + '">' + ''.join(
    f'<property name="{name}" type="{value[0]}" access="read"/>'
    for name, value in _PROPERTIES.items()) + '''
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<signal name="NewIcon"/><signal name="NewStatus"><arg type="s"/></signal>
<signal name="XAyatanaNewLabel"><arg type="s"/><arg type="s"/></signal>
</interface></node>'''


class IndicatorStatus:
    ACTIVE = 'Active'
    PASSIVE = 'Passive'


class IndicatorCategory:
    HARDWARE = 'Hardware'


class Indicator:
    @classmethod
    def new(cls, app_id, _icon, _category):
        return cls(app_id)

    def __init__(self, app_id):
        self.activate = lambda: None
        self.menu = None
        self.values = dict(_PROPERTIES)
        self.values['Id'] = ('s', app_id)
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.registration = self.bus.register_object(
            _PATH, Gio.DBusNodeInfo.new_for_xml(_XML).interfaces[0],
            self._method, self._property, None)
        self.server = Dbusmenu.Server.new(_MENU)
        self.watch = Gio.bus_watch_name_on_connection(
            self.bus, 'org.kde.StatusNotifierWatcher', Gio.BusNameWatcherFlags.NONE,
            self._watcher_appeared, lambda *_: None)

    def _watcher_appeared(self, connection, name, _owner):
        connection.call(name, '/StatusNotifierWatcher', 'org.kde.StatusNotifierWatcher',
                        'RegisterStatusNotifierItem', GLib.Variant('(s)', (_PATH,)),
                        None, Gio.DBusCallFlags.NONE, -1, None, self._registered)

    @staticmethod
    def _registered(connection, result):
        try:
            connection.call_finish(result)
        except GLib.Error as error:
            _LOG.warning('Tray registration failed: %s', error)

    def _property(self, _connection, _sender, _path, _interface, name):
        return GLib.Variant(*self.values[name])

    def _method(self, _connection, _sender, _path, _interface, method, _args, invocation):
        if method in ('Activate', 'SecondaryActivate'):
            self.activate()
        elif method == 'ContextMenu' and self.menu is not None:
            self.menu.popup_at_pointer(None)
        invocation.return_value(None)

    def _change(self, name, value):
        signature, previous = self.values[name]
        if previous == value:
            return
        self.values[name] = (signature, value)
        self.bus.emit_signal(None, _PATH, 'org.freedesktop.DBus.Properties',
                             'PropertiesChanged', GLib.Variant('(sa{sv}as)',
                             (_INTERFACE, {name: GLib.Variant(signature, value)}, [])))

    def set_menu(self, menu):
        self.menu = menu
        self.server.set_root(DbusmenuGtk3.gtk_parse_menu_structure(menu))

    def set_icon_full(self, icon, _description):
        source_icon = Path(__file__).resolve().parents[2] / 'data/icons' / (icon + '.svg')
        if source_icon.is_file():
            # A custom IconThemePath makes GNOME load a FileIcon, losing symbolic
            # recoloring. Make native-checkout artwork available by theme name.
            target = Path(xdg_data_home) / 'icons/hicolor/scalable/apps' / source_icon.name
            try:
                content = source_icon.read_bytes()
                if not target.is_file() or target.read_bytes() != content:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                theme_root = target.parents[2]
                cache = theme_root / 'icon-theme.cache'
                updater = shutil.which('gtk-update-icon-cache')
                if updater and (not cache.exists() or cache.stat().st_mtime < target.stat().st_mtime):
                    subprocess.run([updater, '-f', '-t', str(theme_root)], check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
                    os.utime(theme_root, None)
            except (OSError, subprocess.SubprocessError):
                _LOG.warning('Could not install native tray icon', exc_info=True)
        self._change('IconThemePath', '')
        self._change('IconName', icon)
        self.bus.emit_signal(None, _PATH, _INTERFACE, 'NewIcon', None)

    def set_status(self, status):
        if self.values['Status'][1] != status:
            self._change('Status', status)
            self.bus.emit_signal(None, _PATH, _INTERFACE, 'NewStatus', GLib.Variant('(s)', (status,)))

    def set_label(self, label, guide):
        if self.values['XAyatanaLabel'][1] != label:
            self._change('XAyatanaLabel', label)
            self._change('XAyatanaLabelGuide', guide)
            self.bus.emit_signal(None, _PATH, _INTERFACE, 'XAyatanaNewLabel',
                                 GLib.Variant('(ss)', (label, guide)))

    def close(self):
        Gio.bus_unwatch_name(self.watch)
        self.bus.unregister_object(self.registration)
