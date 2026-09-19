#!/usr/bin/env python3
"""Install the optional, narrowly authorized system GPU helper. Run via pkexec/sudo.

Only run from a trusted checkout with a trusted nvidia-ml-py module. Re-run after
updating helper code. The GUI and the development environment remain unprivileged.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import stat

LIB = Path('/usr/local/lib/greenwithenvi')
HELPER = Path('/usr/local/libexec/greenwithenvi-control')
POLICY = Path('/usr/share/polkit-1/actions/io.github.hsantos92.GreenWithEnvi.control.policy')
RULE = Path('/etc/polkit-1/rules.d/49-greenwithenvi-control.rules')


def secure_directory(path):
    if path == path.parent:
        return
    secure_directory(path.parent)
    if not path.exists():
        path.mkdir(mode=0o755)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError(f'Unsafe system directory: {path}')


def write_file(path, content, mode=0o644):
    secure_directory(path.parent)
    if path.is_symlink():
        raise RuntimeError(f'Refusing symlink: {path}')
    # A fresh inode prevents following hard links or retaining unexpected modes.
    temporary = path.with_name(path.name + '.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as output:
        output.write(content)
    os.chown(temporary, 0, 0)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True, help='Local user allowed GPU control without another prompt')
    parser.add_argument('--nvml-module', type=Path, required=True, help='Trusted pinned pynvml.py to install')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run this installer via pkexec or sudo')
    account = pwd.getpwnam(args.user)
    if account.pw_uid == 0:
        parser.error('Select the desktop user, not root')
    source = Path(__file__).resolve().parents[1] / 'gwe/repository/nvml_control.py'
    for path in (source, args.nvml_module):
        if not path.is_file():
            parser.error(f'Missing source: {path}')
    write_file(LIB / 'nvml_control.py', source.read_bytes())
    write_file(LIB / 'pynvml.py', args.nvml_module.read_bytes())
    write_file(LIB / 'entry.py', b'''import re
import sys
if len(sys.argv) != 2 or not re.fullmatch(r"GPU-[0-9a-fA-F-]{36}", sys.argv[1]):
    raise SystemExit("Expected one GPU UUID")
sys.path.insert(0, "/usr/local/lib/greenwithenvi")
from nvml_control import main
main()
''')
    write_file(HELPER, b'''#!/bin/sh
exec /usr/bin/python3 -I -S /usr/local/lib/greenwithenvi/entry.py "$@"
''', 0o755)
    write_file(POLICY, b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN" "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="io.github.hsantos92.GreenWithEnvi.control">
    <description>Control NVIDIA GPU fans, clocks and power</description>
    <message>Authentication is required to control NVIDIA GPU settings</message>
    <defaults><allow_any>auth_admin</allow_any><allow_inactive>auth_admin</allow_inactive><allow_active>auth_admin</allow_active></defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/libexec/greenwithenvi-control</annotate>
  </action>
</policyconfig>
''')
    rule = '''// Only this installed helper, for the selected active local user.
polkit.addRule(function(action, subject) {
    if (action.id === "io.github.hsantos92.GreenWithEnvi.control" &&
        action.lookup("program") === "/usr/local/libexec/greenwithenvi-control" &&
        subject.user === USER && subject.local && subject.active) {
        return polkit.Result.YES;
    }
});
'''.replace('USER', json.dumps(account.pw_name))
    write_file(RULE, rule.encode())
    print(f'Installed GPU control helper for active local sessions of {account.pw_name}.')


if __name__ == '__main__':
    main()
