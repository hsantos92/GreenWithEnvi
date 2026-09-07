"""Hardware-free regression tests; never write to a real GPU."""
import ctypes
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import gi
gi.require_version('Gtk', '3.0')
import pynvml as nvml
from gwe.repository import nvml_control as control
from gwe.repository.nvidia_repository import NvidiaRepository, nvml_session, query
from gwe.interactor.has_nvidia_driver_interactor import HasNvidiaDriverInteractor, HasNvidiaDriverResult


class NvmlTests(unittest.TestCase):
    def test_memory_v2_reports_used_and_reserved_separately(self):
        mib = 1048576
        memory = SimpleNamespace(total=24564 * mib, used=3548 * mib + 123,
                                 reserved=488 * mib)
        def sensor(function, *args):
            if function is nvml.nvmlDeviceGetMemoryInfo:
                self.assertEqual(args, ('handle', nvml.nvmlMemory_v2))
                return memory
            return None
        with patch('gwe.repository.nvidia_repository.query', side_effect=sensor):
            info = NvidiaRepository()._get_gpu_status(0, 'handle', 'GPU-test').info
        self.assertEqual(info.memory_used, 3548)
        self.assertEqual(info.memory_reserved, 488)
        self.assertEqual(info.memory_total, 24564)

    def test_unavailable_memory_v2_does_not_break_status(self):
        with patch('gwe.repository.nvidia_repository.query', return_value=None):
            info = NvidiaRepository()._get_gpu_status(0, 'handle', 'GPU-test').info
        self.assertIsNone(info.memory_used)
        self.assertIsNone(info.memory_reserved)
        self.assertIsNone(info.memory_total)

    def test_wayland_startup_needs_only_nvml(self):
        repo = MagicMock(spec=['has_nvml_shared_library'])
        repo.has_nvml_shared_library.return_value = True
        self.assertEqual(HasNvidiaDriverInteractor(repo)._has_nvidia_driver(), HasNvidiaDriverResult.POSITIVE)

    def test_optional_sensor_errors(self):
        for code in (nvml.NVML_ERROR_NOT_SUPPORTED, nvml.NVML_ERROR_FUNCTION_NOT_FOUND,
                     nvml.NVML_ERROR_NO_PERMISSION, nvml.NVML_ERROR_UNKNOWN):
            def sensor():
                raise nvml.NVMLError(code)
            self.assertIsNone(query(sensor))

    def test_lost_gpu_not_silenced(self):
        def sensor():
            raise nvml.NVMLError(nvml.NVML_ERROR_GPU_IS_LOST)
        with self.assertRaises(nvml.NVMLError):
            query(sensor)

    def test_failed_init_does_not_shutdown(self):
        with patch.object(nvml, 'nvmlInit', side_effect=nvml.NVMLError(9)), \
             patch.object(nvml, 'nvmlShutdown') as shutdown:
            with self.assertRaises(nvml.NVMLError):
                with nvml_session():
                    pass
            shutdown.assert_not_called()

    def test_shutdown_after_query_failure(self):
        with patch.object(nvml, 'nvmlInit'), patch.object(nvml, 'nvmlShutdown') as shutdown:
            with self.assertRaises(ValueError):
                with nvml_session():
                    raise ValueError()
            shutdown.assert_called_once()

    def test_native_clock_error_is_not_discarded(self):
        with patch.object(nvml, '_nvmlGetFunctionPointer', return_value=lambda *_: nvml.NVML_ERROR_NO_PERMISSION):
            with self.assertRaises(nvml.NVMLError):
                control.clock_offsets(None, nvml.NVML_CLOCK_GRAPHICS)

    def test_fan_rpm_uses_each_fan_index(self):
        def native(_handle, pointer):
            info = ctypes.cast(pointer, ctypes.POINTER(nvml.c_nvmlFanSpeedInfo_t)).contents
            info.speed = 1000 + info.fan
            return 0
        with patch.object(nvml, '_nvmlGetFunctionPointer', return_value=native):
            self.assertEqual(control.fan_rpm(None, 1), 1001)

    def controller(self):
        with patch.object(nvml, 'nvmlDeviceGetHandleByUUID', return_value='handle'):
            return control.Controller('GPU-test')

    def test_invalid_controls_do_not_write(self):
        controller = self.controller()
        for speed in (-1, 101, True, '50'):
            with self.assertRaises(ValueError):
                controller.execute({'operation': 'fan', 'speed': speed})
        with self.assertRaises(ValueError):
            controller.execute({'operation': 'arbitrary'})

    def test_fan_clamps_to_driver_limits_and_restores(self):
        controller = self.controller()
        with patch.object(nvml, 'nvmlDeviceGetNumFans', return_value=2), \
             patch.object(nvml, 'nvmlDeviceGetMinMaxFanSpeed', return_value=[30, 100]), \
             patch.object(nvml, 'nvmlDeviceSetFanSpeed_v2') as speed, \
             patch.object(nvml, 'nvmlDeviceSetDefaultFanSpeed_v2') as restore:
            controller.execute({'operation': 'fan', 'speed': 0})
            self.assertEqual([call.args for call in speed.call_args_list], [('handle', 0, 30), ('handle', 1, 30)])
            controller.restore()
            self.assertEqual(restore.call_count, 2)
            self.assertFalse(controller.manual_fans)

    def test_partial_fan_failure_restores_all_attempted_fans(self):
        controller = self.controller()
        with patch.object(nvml, 'nvmlDeviceGetNumFans', return_value=2), \
             patch.object(nvml, 'nvmlDeviceGetMinMaxFanSpeed', return_value=[30, 100]), \
             patch.object(nvml, 'nvmlDeviceSetFanSpeed_v2', side_effect=[None, nvml.NVMLError(3)]), \
             patch.object(nvml, 'nvmlDeviceSetDefaultFanSpeed_v2') as restore:
            with self.assertRaises(nvml.NVMLError):
                controller.execute({'operation': 'fan', 'speed': 50})
            self.assertEqual(restore.call_count, 2)

    def test_clock_memory_units_and_rollback(self):
        controller = self.controller()
        def offset(_handle, domain):
            return SimpleNamespace(type=domain, minClockOffsetMHz=-2000, maxClockOffsetMHz=6000, clockOffsetMHz=10)
        writes = []
        def setter(_name, _handle, info):
            writes.append((info.type, info.clockOffsetMHz))
            if info.type == nvml.NVML_CLOCK_MEM:
                raise nvml.NVMLError(4)
        with patch.object(control, 'clock_offsets', side_effect=offset), \
             patch.object(control, 'checked_struct_call', side_effect=setter):
            with self.assertRaises(nvml.NVMLError):
                controller.execute({'operation': 'overclock', 'gpu': 100, 'memory': 400})
        self.assertEqual(writes, [(nvml.NVML_CLOCK_GRAPHICS, 100), (nvml.NVML_CLOCK_MEM, 800),
                                  (nvml.NVML_CLOCK_GRAPHICS, 10)])

    def test_out_of_range_clock_does_not_partially_apply(self):
        controller = self.controller()
        offset = SimpleNamespace(minClockOffsetMHz=-1000, maxClockOffsetMHz=1000, clockOffsetMHz=0)
        with patch.object(control, 'clock_offsets', return_value=offset), \
             patch.object(control, 'checked_struct_call') as setter:
            with self.assertRaises(ValueError):
                controller.execute({'operation': 'overclock', 'gpu': 10, 'memory': 1000})
            setter.assert_not_called()

    def test_worker_restores_on_eof_and_timeout(self):
        for ready in ([io.StringIO()], []):
            controller = MagicMock()
            with patch.object(control.select, 'select', return_value=(ready, [], [])):
                control.serve(controller, io.StringIO(''), io.StringIO())
            controller.restore.assert_called_once()

    def test_worker_restores_on_broken_pipe(self):
        controller = MagicMock()
        output = MagicMock()
        output.write.side_effect = BrokenPipeError()
        with patch.object(control.select, 'select', return_value=([True], [], [])):
            with self.assertRaises(BrokenPipeError):
                control.serve(controller, io.StringIO('{"operation":"heartbeat"}\n'), output)
        controller.restore.assert_called_once()

    def test_power_bounds_and_units(self):
        controller = self.controller()
        with patch.object(nvml, 'nvmlDeviceGetPowerManagementLimitConstraints', return_value=(100000, 450000)), \
             patch.object(nvml, 'nvmlDeviceSetPowerManagementLimit') as setter:
            controller.execute({'operation': 'power', 'watts': 250})
            setter.assert_called_once_with('handle', 250000)
            with self.assertRaises(ValueError):
                controller.execute({'operation': 'power', 'watts': 451})

    def test_empty_gpu_list_does_not_create_index_error(self):
        with patch.object(nvml, 'nvmlInit'), patch.object(nvml, 'nvmlShutdown'), \
             patch.object(nvml, 'nvmlDeviceGetCount', return_value=0):
            self.assertIsNone(NvidiaRepository().get_status())


if __name__ == '__main__':
    unittest.main()
