# This file is part of gwe.
#
# Copyright (c) 2018 Roberto Leinardi
#
# gwe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gwe is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gwe.  If not, see <http://www.gnu.org/licenses/>.
import os
import sys
from pathlib import Path

from xdg.BaseDirectory import xdg_config_home, xdg_data_home

from gwe.conf import DESKTOP_ENTRY, APP_ICON_NAME, APP_DESKTOP_ENTRY_NAME, APP_PACKAGE_NAME
from gwe.util.desktop.desktop_parser import DesktopParser

DESKTOP_ENTRY_EXEC = 'Exec'
DESKTOP_ENTRY_ICON = 'Icon'
AUTOSTART_FLAG = 'X-GNOME-Autostart-enabled'
AUTOSTART_FILE_PATH = Path(xdg_config_home).joinpath('autostart').joinpath(APP_DESKTOP_ENTRY_NAME)
APPLICATION_ENTRY_FILE_PATH = Path(xdg_data_home).joinpath('applications').joinpath(APP_DESKTOP_ENTRY_NAME)


def _quote_exec_arg(value: str) -> str:
    # Desktop Entry escaping is different from shell quoting. Literal percent
    # signs must also be escaped to avoid interpreting them as field codes.
    value = value.replace('%', '%%').replace('\\', '\\\\\\\\')
    for char in ('"', '`', '$'):
        value = value.replace(char, '\\\\' + char)
    return '"' + value + '"'


def _launch_details() -> tuple[str, str]:
    source = os.environ.get('MESON_SOURCE_ROOT')
    if source:
        root = Path(source)
        launcher = root / 'scripts/run-native.sh'
        if launcher.is_file():
            args = ['/usr/bin/env', f'GWE_PYTHON={sys.executable}',
                    '/bin/bash', str(launcher)]
            return (' '.join(_quote_exec_arg(arg) for arg in args),
                    str(root / 'data/icons/com.leinardi.gwe.svg'))
    return APP_PACKAGE_NAME, APP_ICON_NAME


def set_autostart_entry(is_enabled: bool) -> None:
    desktop_parser = DesktopParser(str(AUTOSTART_FILE_PATH))

    if not AUTOSTART_FILE_PATH.is_file():
        for key, value in DESKTOP_ENTRY.items():
            desktop_parser.set(key, value)

    command, icon = _launch_details()
    desktop_parser.set(DESKTOP_ENTRY_ICON, icon)
    desktop_parser.set(DESKTOP_ENTRY_EXEC, f'{command} --hide-window')

    desktop_parser.set(AUTOSTART_FLAG, str(is_enabled).lower())
    desktop_parser.write()


def add_application_entry() -> None:
    desktop_parser = DesktopParser(str(APPLICATION_ENTRY_FILE_PATH))

    for k, v in DESKTOP_ENTRY.items():
        desktop_parser.set(k, v)
    command, icon = _launch_details()
    desktop_parser.set(DESKTOP_ENTRY_ICON, icon)
    desktop_parser.set(DESKTOP_ENTRY_EXEC, command)
    desktop_parser.write()
