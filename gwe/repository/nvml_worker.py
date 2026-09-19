"""Client for a single authenticated NVML control session."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
from typing import Any, Dict

from gwe.util.deployment import is_flatpak


class NvmlWorker:
    def __init__(self, uuid: str) -> None:
        if is_flatpak():
            raise RuntimeError('GPU controls require a native GWE installation; monitoring works in Flatpak.')
        helper = Path('/usr/local/libexec/greenwithenvi-control')
        if helper.is_file():
            command = [str(helper), uuid]
        else:
            script = str(Path(__file__).with_name('nvml_control.py'))
            command = [sys.executable, '-I', script, uuid]
        if os.geteuid() != 0:
            command.insert(0, 'pkexec')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)
        self.request({'operation': 'heartbeat'}, timeout=120)

    def request(self, request: Dict[str, Any], timeout: float = 5) -> None:
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.write(json.dumps(request) + '\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], timeout)[0]:
                raise RuntimeError('GPU control session timed out')
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError('GPU authorization was cancelled or the control worker exited')
            response = json.loads(line)
            if not response.get('ok'):
                raise RuntimeError(response.get('error', 'GPU control failed'))
        except (OSError, ValueError, RuntimeError):
            self.close()
            raise

    def close(self) -> None:
        # Closing stdin lets the worker restore fans before exiting. Do not kill it.
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.stdout and not self.process.stdout.closed:
            self.process.stdout.close()
        threading.Thread(target=self.process.wait, daemon=True).start()
