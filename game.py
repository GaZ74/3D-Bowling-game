"""Game state and two-roll frame flow."""

from dataclasses import dataclass, field
import math

from config import (BALL_RADIUS, BALL_START_Z, BALL_SPEED_DEFAULT,
                    BALL_SPEED_MAX, BALL_SPEED_MIN, BALL_SPEED_STEP,
                    MAX_AIM_ANGLE, MAX_START_X, START_X_STEP, PIN_DECK_Z,
                    PIN_SPACING, PIN_ROWS, PHYSICS_HZ, MAX_PHYSICS_STEPS)
from physics import predict_trajectory, step_physics
from scoring import Scorecard


@dataclass
class Ball:
    x: float = 0.0
    z: float = BALL_START_Z
    vx: float = 0.0
    vz: float = 0.0
    on_guide: bool = False
    guide_side: int = 0
    guide_points: list = field(default_factory=list)
    guide_lengths: list = field(default_factory=list)
    guide_distance: float = 0.0
    reached_reset: bool = False


@dataclass
class Pin:
    x: float
    z: float
    down: bool = False
    vx: float = 0.0
    vz: float = 0.0
    tilt_x: float = 0.0
    tilt_z: float = 0.0
    omega_x: float = 0.0
    omega_z: float = 0.0
    ball_contacted: bool = False


class BowlingGame:
    def __init__(self):
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.ball = Ball()
        self.pins = self._make_pins()
        self.phase = "aiming"  # aiming, rolling, result
        self.rolls_this_frame = 0
        self.message = "Aim with arrows, set power, then press Space"
        self.scorecard = Scorecard()
        self._physics_accumulator = 0.0
        self._physics_step = 1.0 / PHYSICS_HZ

    @staticmethod
    def _make_pins():
        pins = []
        for row in range(PIN_ROWS):
            count = row + 1
            z = PIN_DECK_Z + (PIN_ROWS - 1 - row) * PIN_SPACING
            for col in range(count):
                x = (col - (count - 1) / 2) * PIN_SPACING
                pins.append(Pin(x, z))
        return pins

    @property
    def standing_pins(self):
        return sum(not pin.down for pin in self.pins)

    @property
    def pins_moving(self):
        return any(math.hypot(pin.vx, pin.vz) > 0.04
                   or math.hypot(pin.omega_x, pin.omega_z) > 0.04
                   for pin in self.pins)

    def trajectory(self):
        return predict_trajectory(self.aim, self.power, self.start_x)

    def change_aim(self, direction: int):
        if self.phase == "aiming":
            self.aim = max(-MAX_AIM_ANGLE, min(MAX_AIM_ANGLE, self.aim + direction * 0.04))

    def change_power(self, direction: int):
        if self.phase == "aiming":
            self.power = max(BALL_SPEED_MIN, min(BALL_SPEED_MAX,
                               self.power + direction * BALL_SPEED_STEP))

    def change_start_position(self, direction: int):
        if self.phase == "aiming":
            self.start_x = max(-MAX_START_X, min(MAX_START_X,
                               self.start_x + direction * START_X_STEP))
            self.ball.x = self.start_x

    def throw(self):
        if self.phase != "aiming":
            return
        for pin in self.pins:
            pin.ball_contacted = False
        self.ball = Ball(x=self.start_x, vx=math.sin(self.aim) * self.power,
                         vz=math.cos(self.aim) * self.power)
        self.phase = "rolling"
        self.message = "Ball in motion"

    def update(self, dt: float):
        if self.phase not in ("rolling", "result"):
            return
        self._physics_accumulator += min(max(dt, 0.0), 0.1)
        steps = 0
        while self._physics_accumulator >= self._physics_step and steps < MAX_PHYSICS_STEPS:
            finished = step_physics(self.ball, self.pins, self._physics_step)
            self._physics_accumulator -= self._physics_step
            steps += 1
            if self.phase == "rolling" and finished:
                self.rolls_this_frame += 1
                self.phase = "result"
                if self.ball.on_guide:
                    self.message = (f"Ball followed the side guide to the reset zone - "
                                   f"{10 - self.standing_pins} pin(s) down")
                else:
                    self.message = f"Ball reached the reset zone - {10 - self.standing_pins} pin(s) down"
        if (self.phase == "result" and not self.pins_moving
                and "press Space" not in self.message):
            self.message += " - press Space for next roll"

    def next_roll(self):
        if self.phase != "result":
            return
        if self.pins_moving:
            self.message = "Pins are still settling"
            return
        # A strike finishes the frame immediately. Otherwise allow roll two.
        if self.rolls_this_frame >= 2 or self.standing_pins == 0:
            self.pins = self._make_pins()  # reset all ten pins for the next frame
            self.rolls_this_frame = 0
            self.message = "New frame - pins reset"
        self.ball = Ball()
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.phase = "aiming"
        self._physics_accumulator = 0.0

    def reset_frame(self):
        self.pins = self._make_pins()
        self.rolls_this_frame = 0
        self.ball = Ball()
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.phase = "aiming"
        self.message = "Frame reset"
        self._physics_accumulator = 0.0
