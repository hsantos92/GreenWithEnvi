"""Regression coverage for gradual cooling, profile resets and curve interpolation."""
import unittest

from gwe.util.fan_curve import FanHysteresis, curve_points, interpolate


class FanCurveTests(unittest.TestCase):
    def test_gradual_cooling_accumulates_to_threshold(self):
        control = FanHysteresis()
        temperatures = [70, 69, 68, 67, 66, 65, 64]
        self.assertEqual([control.choose(t, t, 2) for t in temperatures], [70, 70, 68, 68, 66, 66, 64])

    def test_repeated_polls_do_not_move_reference(self):
        control = FanHysteresis()
        control.choose(70, 70, 2)
        for _ in range(100):
            self.assertEqual(control.choose(69, 69, 2), 70)
        self.assertEqual(control.choose(68, 68, 2), 68)

    def test_heating_raises_duty_immediately(self):
        control = FanHysteresis()
        self.assertEqual(control.choose(60, 50, 3), 50)
        self.assertEqual(control.choose(61, 51, 3), 51)
        self.assertEqual(control.choose(60, 50, 3), 51)
        self.assertEqual(control.choose(62, 52, 3), 52)

    def test_profile_reset_applies_lower_curve_at_constant_temperature(self):
        control = FanHysteresis()
        control.choose(60, 80, 2)
        control.reset()
        self.assertEqual(control.choose(60, 40, 2), 40)
        self.assertEqual(control.choose(59, 39, 2), 40)
        self.assertEqual(control.choose(58, 38, 2), 38)

    def test_zero_hysteresis_tracks_every_reading(self):
        control = FanHysteresis()
        self.assertEqual([control.choose(t, t, 0) for t in [70, 69, 68, 69]], [70, 69, 68, 69])

    def test_flat_curve_does_not_reset_last_changed_command(self):
        control = FanHysteresis()
        control.choose(70, 70, 2)
        control.choose(75, 70, 2)
        control.choose(69, 70, 2)
        self.assertEqual(control.choose(68, 68, 2), 68)

    def test_edited_database_row_order_does_not_change_interpolation(self):
        steps = [(80, 100), (20, 30), (60, 60)]
        self.assertEqual(interpolate(steps, 40), 45)
        self.assertEqual(interpolate(steps, 70), 80)

    def test_graph_and_controller_preserve_quiet_endpoint(self):
        for steps in ([(60, 30), (90, 50)], [(60, 30), (90, 50), (100, 50)]):
            self.assertEqual(curve_points(steps)[100], 50)
            self.assertEqual(interpolate(steps, 100), 50)
            self.assertEqual(interpolate(steps, 0), 30)

    def test_single_point_is_constant(self):
        self.assertEqual([interpolate([(50, 40)], t) for t in [0, 50, 100]], [40, 40, 40])

    def test_empty_curve_is_not_treated_as_zero_speed(self):
        with self.assertRaises(ValueError):
            interpolate([], 50)


if __name__ == '__main__':
    unittest.main()
