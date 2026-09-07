"""Exercise the real presenter loop with telemetry and hardware writes replaced."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Dazzle', '1.0')
gi.require_version('Notify', '0.7')
from gwe.presenter.main_presenter import MainPresenter
from gwe.util.fan_curve import FanHysteresis


class FanPresenterTests(unittest.TestCase):
    def setUp(self):
        self.presenter = object.__new__(MainPresenter)
        self.profile = SimpleNamespace(id=2, type='fan_curve', steps=[
            SimpleNamespace(temperature=0, duty=0), SimpleNamespace(temperature=100, duty=100)])
        self.gpu = SimpleNamespace(index=0, temp=SimpleNamespace(gpu=70),
                                   fan=SimpleNamespace(control_allowed=True, manual_control=True,
                                                       fan_list=[(95, 2000)]))
        p = self.presenter
        p._gpu_index = 0
        p._latest_status = SimpleNamespace(gpu_status_list=[self.gpu])
        p._fan_profile_selected = self.profile
        p._fan_profile_applied = self.profile
        p._fan_hysteresis = FanHysteresis()
        p._pending_fan_request = None
        p._settings_interactor = MagicMock()
        p._settings_interactor.get_int.return_value = 2
        p._set_fan_speed = MagicMock()
        p._refresh_fan_profile_ui = MagicMock()
        p._update_current_fan_profile = MagicMock()
        p.main_view = MagicMock()

    def test_poll_loop_holds_requested_duty_not_lagging_sensor(self):
        for temperature in [70, 69, 68, 67, 66]:
            self.gpu.temp.gpu = temperature
            self.presenter._update_fan()
        self.assertEqual([call.args[1] for call in self.presenter._set_fan_speed.call_args_list],
                         [70, 70, 68, 68, 66])

    def test_apply_new_curve_takes_effect_without_waiting_for_next_poll(self):
        self.presenter._update_fan()
        self.presenter._fan_profile_selected = SimpleNamespace(id=3, type='fan_curve', steps=[
            SimpleNamespace(temperature=0, duty=30), SimpleNamespace(temperature=100, duty=30)])
        self.presenter.on_fan_apply_button_clicked()
        self.presenter._set_fan_speed.assert_called_with(0, 30)
        self.assertEqual(self.presenter._fan_profile_applied.id, 3)

    def test_auto_profile_restores_firmware_control(self):
        self.presenter._update_fan()
        self.presenter._fan_profile_selected = SimpleNamespace(id=1, type='auto')
        self.presenter.on_fan_apply_button_clicked()
        self.presenter._set_fan_speed.assert_called_with(0, manual_control=False)
        self.assertIsNone(self.presenter._fan_hysteresis.duty)

    def test_missing_temperature_does_not_send_a_fan_command(self):
        self.gpu.temp.gpu = None
        self.presenter._update_fan()
        self.presenter._set_fan_speed.assert_not_called()

    def test_control_failure_clears_reference_and_queued_commands(self):
        self.presenter._update_fan()
        self.presenter._pending_fan_request = (0, 50, True)
        self.presenter._on_fan_control_error(RuntimeError('Cancelled'))
        self.assertIsNone(self.presenter._fan_hysteresis.duty)
        self.assertIsNone(self.presenter._pending_fan_request)
        self.assertIsNone(self.presenter._fan_profile_applied)

    def test_editing_applied_curve_resets_hysteresis(self):
        self.presenter._update_fan()
        self.presenter._on_speed_step_list_changed(SimpleNamespace(entry=SimpleNamespace(profile=self.profile)))
        self.assertIsNone(self.presenter._fan_hysteresis.duty)


if __name__ == '__main__':
    unittest.main()
