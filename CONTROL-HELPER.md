# Optional passwordless GPU controls

The GTK app always runs as your user. The optional system helper allows one
configured user in an active local session to start a privileged GPU-control
worker without another password prompt. It does not store or reuse a password.
Any process running as that user in the authorized session can request the same
GPU operations. Authorization is checked when the worker starts; locking the
screen does not stop an already-running fan curve.

## Install

Use a trusted checkout and its pinned `nvidia-ml-py` dependency. After reviewing
`scripts/install-control-helper.py`, run from the repository root:

```sh
pkexec /usr/bin/python3 -I scripts/install-control-helper.py --user "$USER" \
  --nvml-module "$(~/.cache/gwe-dev/bin/python -I -c 'import pynvml; print(pynvml.__file__)')"
```

This one-time installation requires administrator authentication. Restart the
app afterward. Re-run the installer after changes to `nvml_control.py` or the
NVML dependency, since the helper uses installed copies, not the checkout.

The installer creates root-owned files without group/world write permissions:

- `/usr/local/libexec/greenwithenvi-control`: fixed entry command.
- `/usr/local/lib/greenwithenvi/`: entry script, control worker and `pynvml.py`.
- `/usr/share/polkit-1/actions/io.github.hsantos92.GreenWithEnvi.control.policy`.
- `/etc/polkit-1/rules.d/49-greenwithenvi-control.rules`.

The entry uses `/usr/bin/python3 -I -S` and a fixed root-owned module directory.
The rule matches the helper's action, executable, selected user, and active local
session. It does not authorize arbitrary Python, shell commands or development
files. The helper accepts a GPU UUID and the existing validated fan, clock and
power protocol; it cannot execute caller-supplied commands or load caller paths.
Firmware fan restoration on disconnect/error/timeout remains in place. Clock
offsets and power limits are not automatically restored on exit.

## Remove passwordless authorization

Remove `/etc/polkit-1/rules.d/49-greenwithenvi-control.rules` as administrator,
then quit and restart the app. The installed helper will require authentication.
To uninstall it entirely, also remove the policy, executable and the three files
in `/usr/local/lib/greenwithenvi/`, then the empty directory. Without the installed
helper, the app returns to its authenticated development worker.

## Verification

A successful heartbeat request verifies authorization and starts/stops the helper
without modifying fans, clocks or power. Use this for installation checks rather
than changing GPU settings just to test permissions. Real boot startup still
requires the configured checkout and Python environment to be available at login.
