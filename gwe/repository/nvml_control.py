"""NVML controls and the authenticated, pipe-scoped control worker.

The authenticated development worker uses Python -I. The optional root-owned
system helper uses -I -S and its own trusted nvidia-ml-py copy. Neither imports
the UI. See CONTROL-HELPER.md for the optional authorization policy.
"""
import ctypes
import json
import logging
import select
import sys
from typing import Any, Dict, TextIO

import pynvml as nvml

_LOG = logging.getLogger(__name__)


def checked_struct_call(name: str, handle: Any, info: Any) -> Any:
    """Check the native result (some nvidia-ml-py struct wrappers discard it)."""
    function = nvml._nvmlGetFunctionPointer(name)  # pylint: disable=protected-access
    result = function(handle, ctypes.byref(info))
    if result != nvml.NVML_SUCCESS:
        raise nvml.NVMLError(result)
    return info


def clock_offsets(handle: Any, domain: int) -> Any:
    info = nvml.c_nvmlClockOffset_t()
    info.version = nvml.nvmlClockOffset_v1
    info.type = domain
    info.pstate = nvml.NVML_PSTATE_0
    return checked_struct_call('nvmlDeviceGetClockOffsets', handle, info)


def fan_rpm(handle: Any, fan: int) -> int:
    info = nvml.c_nvmlFanSpeedInfo_t()
    info.version = nvml.nvmlFanSpeedInfo_v1
    info.fan = fan
    return int(checked_struct_call('nvmlDeviceGetFanSpeedRPM', handle, info).speed)


def integer(value: Any, name: str) -> int:
    if type(value) is not int:  # bool is not a valid setting
        raise ValueError(f'{name} must be an integer')
    return int(value)


class Controller:
    """Bind commands to one UUID; restore only fans this worker has changed."""
    def __init__(self, uuid: str) -> None:
        self.handle = nvml.nvmlDeviceGetHandleByUUID(uuid)
        self.manual_fans: set[int] = set()

    def restore(self) -> None:
        errors = []
        for fan in list(self.manual_fans):
            try:
                nvml.nvmlDeviceSetDefaultFanSpeed_v2(self.handle, fan)
                self.manual_fans.remove(fan)
            except nvml.NVMLError as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('Could not restore automatic fans: ' + '; '.join(errors))

    def execute(self, request: Dict[str, Any]) -> None:
        operation = request.get('operation')
        if operation == 'heartbeat':
            return
        if operation == 'auto':
            # Explicit Auto also restores fans left manual by another application.
            self.manual_fans.update(range(nvml.nvmlDeviceGetNumFans(self.handle)))
            self.restore()
        elif operation == 'fan':
            speed = integer(request.get('speed'), 'Fan speed')
            if not 0 <= speed <= 100:
                raise ValueError('Fan speed must be between 0 and 100')
            minimum, maximum = nvml.nvmlDeviceGetMinMaxFanSpeed(self.handle)
            speed = max(minimum, min(maximum, speed))
            count = nvml.nvmlDeviceGetNumFans(self.handle)
            if not count:
                raise ValueError('This GPU has no controllable fans')
            try:
                for fan in range(count):
                    self.manual_fans.add(fan)
                    nvml.nvmlDeviceSetFanSpeed_v2(self.handle, fan, speed)
            except nvml.NVMLError:
                self.restore()
                raise
        elif operation == 'overclock':
            gpu = integer(request.get('gpu'), 'GPU offset')
            # GWE profiles store memory clock MHz; NVML uses transfer-rate offsets.
            memory = integer(request.get('memory'), 'Memory offset') * 2
            graphics = clock_offsets(self.handle, nvml.NVML_CLOCK_GRAPHICS)
            mem = clock_offsets(self.handle, nvml.NVML_CLOCK_MEM)
            for info, value in ((graphics, gpu), (mem, memory)):
                if not info.minClockOffsetMHz <= value <= info.maxClockOffsetMHz:
                    raise ValueError('Clock offset is outside the driver limits')
            original = graphics.clockOffsetMHz
            graphics.clockOffsetMHz = gpu
            checked_struct_call('nvmlDeviceSetClockOffsets', self.handle, graphics)
            try:
                mem.clockOffsetMHz = memory
                checked_struct_call('nvmlDeviceSetClockOffsets', self.handle, mem)
            except nvml.NVMLError:
                graphics.clockOffsetMHz = original
                checked_struct_call('nvmlDeviceSetClockOffsets', self.handle, graphics)
                raise
        elif operation == 'power':
            milliwatts = integer(request.get('watts'), 'Power limit') * 1000
            minimum, maximum = nvml.nvmlDeviceGetPowerManagementLimitConstraints(self.handle)
            if not minimum <= milliwatts <= maximum:
                raise ValueError('Power limit is outside the driver limits')
            nvml.nvmlDeviceSetPowerManagementLimit(self.handle, milliwatts)
        else:
            raise ValueError('Unknown control operation')


def serve(controller: Controller, input_stream: TextIO, output_stream: TextIO, timeout: float = 15) -> None:
    """EOF or missed heartbeats restore firmware fan control, including on crash."""
    try:
        while select.select([input_stream], [], [], timeout)[0]:
            line = input_stream.readline(4097)
            if not line:
                break
            try:
                if len(line) > 4096 or not line.endswith('\n'):
                    raise ValueError('Invalid request length')
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Expected an object')
                controller.execute(request)
                response: Dict[str, Any] = {'ok': True}
            except (ValueError, RuntimeError, nvml.NVMLError) as error:
                response = {'ok': False, 'error': str(error)}
            output_stream.write(json.dumps(response) + '\n')
            output_stream.flush()
    finally:
        controller.restore()


def main() -> None:
    nvml.nvmlInit()
    try:
        controller = Controller(sys.argv[1])
        serve(controller, sys.stdin, sys.stdout)
    finally:
        nvml.nvmlShutdown()


if __name__ == '__main__':
    main()
