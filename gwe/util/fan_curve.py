"""Shared curve interpolation and stateful fan hysteresis (no hardware access)."""
from typing import Dict, Iterable, Optional, Tuple


def curve_points(steps: Iterable[Tuple[int, int]]) -> Dict[int, int]:
    """Sort database rows and extend endpoints without changing the saved duties."""
    points = dict(steps)
    if points:
        points.setdefault(0, points[min(points)])
        points.setdefault(100, points[max(points)])
    return dict(sorted(points.items()))


def interpolate(steps: Iterable[Tuple[int, int]], temperature: float) -> float:
    points = list(curve_points(steps).items())
    if not points:
        raise ValueError('A fan curve must have at least one point')
    if temperature <= points[0][0]:
        return float(points[0][1])
    for (left_temp, left_duty), (right_temp, right_duty) in zip(points, points[1:]):
        if temperature <= right_temp:
            fraction = (temperature - left_temp) / (right_temp - left_temp)
            return left_duty + fraction * (right_duty - left_duty)
    return float(points[-1][1])


class FanHysteresis:
    """Raise duty immediately; lower it after cumulative cooling reaches the band.

    The reference is the temperature at the last changed command, not the last
    poll. Repeating a command to keep the worker alive does not move it. Track
    the requested duty, not measured fan speed, which can lag or be clamped.
    """
    def __init__(self) -> None:
        self.temperature: Optional[float] = None
        self.duty: Optional[int] = None

    def reset(self) -> None:
        self.temperature = None
        self.duty = None

    def choose(self, temperature: float, requested: int, hysteresis: int) -> int:
        if (self.duty is None or self.temperature is None or requested > self.duty
                or hysteresis <= 0
                or (requested < self.duty and temperature <= self.temperature - hysteresis)):
            if requested != self.duty or hysteresis <= 0:
                self.temperature = temperature
                self.duty = requested
        assert self.duty is not None
        return self.duty
