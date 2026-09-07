# This file is part of gwe.
#
# Copyright (c) 2020 Roberto Leinardi
#
# gst is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gst is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gst.  If not, see <http://www.gnu.org/licenses/>.
"""NVIDIA monitoring through NVML, independent of X11 and NV-CONTROL."""
import atexit
import logging
import threading
from contextlib import contextmanager
from typing import Optional, Any, Callable, Iterator, Dict

import pynvml as nvml
from injector import singleton, inject

from gwe.model.clocks import Clocks
from gwe.model.fan import Fan
from gwe.model.gpu_status import GpuStatus
from gwe.model.info import Info
from gwe.model.overclock import Overclock
from gwe.model.power import Power
from gwe.model.status import Status
from gwe.model.temp import Temp
from gwe.repository.nvml_control import clock_offsets, fan_rpm
from gwe.repository.nvml_worker import NvmlWorker
from gwe.util.concurrency import synchronized_with_attr
from gwe.util.deployment import is_flatpak

_LOG = logging.getLogger(__name__)
_OPTIONAL_ERRORS = (nvml.NVML_ERROR_NOT_SUPPORTED, nvml.NVML_ERROR_FUNCTION_NOT_FOUND,
                    nvml.NVML_ERROR_NO_PERMISSION, nvml.NVML_ERROR_UNKNOWN)


@contextmanager
def nvml_session() -> Iterator[None]:
    nvml.nvmlInit()
    try:
        yield
    finally:
        nvml.nvmlShutdown()


def query(function: Callable[..., Any], *args: Any) -> Any:
    """A missing optional sensor must not take down the entire status refresh."""
    try:
        return function(*args)
    except nvml.NVMLError as error:
        if error.value not in _OPTIONAL_ERRORS:
            raise
        _LOG.debug('%s unavailable: %s', function.__name__, error)
        return None


def text(value: Any) -> Any:
    return value.decode('utf-8') if isinstance(value, bytes) else value


def watts(value: Optional[int]) -> Optional[float]:
    return None if value is None else value / 1000


@singleton
class NvidiaRepository:
    @inject
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workers: Dict[str, NvmlWorker] = {}
        self._uuids: Dict[int, str] = {}
        atexit.register(self.set_all_gpus_fan_to_auto)

    @staticmethod
    def set_ctrl_display(_ctrl_display: str) -> None:
        _LOG.info('--ctrl-display is obsolete: NVML does not use an X display')

    @staticmethod
    def has_nvml_shared_library() -> bool:
        try:
            with nvml_session():
                return bool(nvml.nvmlDeviceGetCount() > 0)
        except nvml.NVMLError:
            _LOG.exception('Unable to initialize NVIDIA driver through NVML')
            return False

    @synchronized_with_attr('_lock')
    def get_status(self) -> Optional[Status]:
        try:
            with nvml_session():
                statuses = []
                for index in range(nvml.nvmlDeviceGetCount()):
                    handle = nvml.nvmlDeviceGetHandleByIndex(index)
                    uuid = text(nvml.nvmlDeviceGetUUID(handle))
                    statuses.append(self._get_gpu_status(index, handle, uuid))
                self._uuids = {gpu.index: gpu.info.uuid for gpu in statuses}
                for uuid in set(self._workers) - set(self._uuids.values()):
                    self._close_worker(uuid)
                return Status(statuses) if statuses else None
        except nvml.NVMLError:
            _LOG.exception('Error while getting NVIDIA status')
            self.set_all_gpus_fan_to_auto()
            return None

    def _get_gpu_status(self, index: int, handle: Any, uuid: str) -> GpuStatus:
        memory = query(nvml.nvmlDeviceGetMemoryInfo, handle, nvml.nvmlMemory_v2)
        util = query(nvml.nvmlDeviceGetUtilizationRates, handle)
        encoder = query(nvml.nvmlDeviceGetEncoderUtilization, handle)
        decoder = query(nvml.nvmlDeviceGetDecoderUtilization, handle)
        info = Info(
            name=text(query(nvml.nvmlDeviceGetName, handle)),
            vbios=text(query(nvml.nvmlDeviceGetVbiosVersion, handle)),
            driver=text(query(nvml.nvmlSystemGetDriverVersion)), uuid=uuid,
            pcie_current_generation=query(nvml.nvmlDeviceGetCurrPcieLinkGeneration, handle),
            pcie_max_generation=query(nvml.nvmlDeviceGetMaxPcieLinkGeneration, handle),
            pcie_current_link=query(nvml.nvmlDeviceGetCurrPcieLinkWidth, handle),
            pcie_max_link=query(nvml.nvmlDeviceGetMaxPcieLinkWidth, handle),
            cuda_cores=query(nvml.nvmlDeviceGetNumGpuCores, handle),
            memory_interface=query(nvml.nvmlDeviceGetMemoryBusWidth, handle),
            memory_total=memory.total // 1048576 if memory else None,
            memory_used=memory.used // 1048576 if memory else None,
            memory_reserved=memory.reserved // 1048576 if memory else None,
            memory_usage=util.memory if util else None, gpu_usage=util.gpu if util else None,
            encoder_usage=encoder[0] if encoder else None, decoder_usage=decoder[0] if decoder else None)
        limits = query(nvml.nvmlDeviceGetPowerManagementLimitConstraints, handle)
        power = Power(
            draw=watts(query(nvml.nvmlDeviceGetPowerUsage, handle)),
            limit=watts(query(nvml.nvmlDeviceGetPowerManagementLimit, handle)),
            default=watts(query(nvml.nvmlDeviceGetPowerManagementDefaultLimit, handle)),
            enforced=watts(query(nvml.nvmlDeviceGetEnforcedPowerLimit, handle)),
            minimum=watts(limits[0]) if limits else None,
            maximum=watts(limits[1]) if limits else None)
        temp = Temp(gpu=query(nvml.nvmlDeviceGetTemperature, handle, nvml.NVML_TEMPERATURE_GPU),
                    maximum=query(nvml.nvmlDeviceGetTemperatureThreshold, handle,
                                  nvml.NVML_TEMPERATURE_THRESHOLD_GPU_MAX),
                    slowdown=query(nvml.nvmlDeviceGetTemperatureThreshold, handle,
                                   nvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN),
                    shutdown=query(nvml.nvmlDeviceGetTemperatureThreshold, handle,
                                   nvml.NVML_TEMPERATURE_THRESHOLD_SHUTDOWN))
        values = {}
        for name, domain in (('graphic', nvml.NVML_CLOCK_GRAPHICS), ('sm', nvml.NVML_CLOCK_SM),
                             ('memory', nvml.NVML_CLOCK_MEM), ('video', nvml.NVML_CLOCK_VIDEO)):
            values[name + '_current'] = query(nvml.nvmlDeviceGetClockInfo, handle, domain)
            values[name + '_max'] = query(nvml.nvmlDeviceGetMaxClockInfo, handle, domain)
        graphics = query(clock_offsets, handle, nvml.NVML_CLOCK_GRAPHICS)
        mem = query(clock_offsets, handle, nvml.NVML_CLOCK_MEM)
        overclock = Overclock()
        if graphics is not None and mem is not None:
            overclock = Overclock(
                available=not is_flatpak(), perf_level_max=0,
                gpu_range=(graphics.minClockOffsetMHz, graphics.maxClockOffsetMHz),
                gpu_offset=graphics.clockOffsetMHz,
                memory_range=(-(-mem.minClockOffsetMHz // 2), mem.maxClockOffsetMHz // 2),
                memory_offset=mem.clockOffsetMHz // 2)
        count = query(nvml.nvmlDeviceGetNumFans, handle) or 0
        fans = [(query(nvml.nvmlDeviceGetFanSpeed_v2, handle, fan), query(fan_rpm, handle, fan))
                for fan in range(count)]
        policies = [query(nvml.nvmlDeviceGetFanControlPolicy_v2, handle, fan) for fan in range(count)]
        fan = Fan(fan_list=fans or None,
                  control_allowed=bool(count and all(p is not None for p in policies) and not is_flatpak()),
                  manual_control=any(p == nvml.NVML_FAN_POLICY_MANUAL for p in policies))
        if temp.gpu is None:
            self._close_worker(uuid)
        return GpuStatus(index=index, info=info, power=power, temp=temp, fan=fan,
                         clocks=Clocks(**values), overclock=overclock)

    def _close_worker(self, uuid: str) -> None:
        worker = self._workers.pop(uuid, None)
        if worker:
            worker.close()

    def _control(self, gpu_index: int, request: Dict[str, Any]) -> bool:
        uuid = self._uuids.get(gpu_index)
        if uuid is None:
            raise RuntimeError('Refresh GPU information before applying controls')
        worker = self._workers.get(uuid)
        if worker and worker.process.poll() is not None:
            self._close_worker(uuid)
            worker = None
        try:
            if worker is None:
                worker = NvmlWorker(uuid)
                self._workers[uuid] = worker
            worker.request(request)
            return True
        except (OSError, ValueError, RuntimeError):
            self._close_worker(uuid)
            raise

    @synchronized_with_attr('_lock')
    def set_overclock(self, gpu_index: int, perf: int, gpu_offset: int, memory_offset: int) -> bool:
        return self._control(gpu_index, {'operation': 'overclock', 'gpu': gpu_offset, 'memory': memory_offset})

    @synchronized_with_attr('_lock')
    def set_power_limit(self, gpu_index: int, limit: int) -> bool:
        return self._control(gpu_index, {'operation': 'power', 'watts': limit})

    @synchronized_with_attr('_lock')
    def set_all_gpus_fan_to_auto(self) -> None:
        for uuid in list(self._workers):
            self._close_worker(uuid)

    @synchronized_with_attr('_lock')
    def set_fan_speed(self, gpu_index: int, speed: int = 100, manual_control: bool = False) -> bool:
        return self._control(gpu_index, {'operation': 'fan', 'speed': speed} if manual_control
                             else {'operation': 'auto'})
