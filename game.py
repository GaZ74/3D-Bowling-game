"""Game state and two-roll frame flow."""

from dataclasses import dataclass
import math

from config import (BALL_RADIUS, BALL_START_Z, BALL_SPEED_DEFAULT,
                    BALL_SPEED_MAX, BALL_SPEED_MIN, BALL_SPEED_STEP,
                    MAX_AIM_ANGLE, MAX_START_X, START_X_STEP, PIN_DECK_Z,
                    PIN_SPACING, PIN_ROWS)
from physics import advance_ball, apply_starter_pin_hits, predict_trajectory
from scoring import Scorecard


@dataclass
class Ball:
    x: float = 0.0
    z: float = BALL_START_Z
    vx: float = 0.0
    vz: float = 0.0


@dataclass
class Pin:
    x: float
    z: float
    down: bool = False


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
        self.ball = Ball(x=self.start_x, vx=math.sin(self.aim) * self.power,
                         vz=math.cos(self.aim) * self.power)
        self.phase = "rolling"
        self.message = "Ball in motion"

    def update(self, dt: float):
        if self.phase != "rolling":
            return
        apply_starter_pin_hits(self.ball, self.pins)
        if advance_ball(self.ball, dt) or self.ball.z > PIN_DECK_Z + 1.2:
            apply_starter_pin_hits(self.ball, self.pins)
            self.rolls_this_frame += 1
            self.phase = "result"
            self.message = f"{10 - self.standing_pins} pin(s) down - press Space for next roll"

    def next_roll(self):
        if self.phase != "result":
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

    def reset_frame(self):
        self.pins = self._make_pins()
        self.rolls_this_frame = 0
        self.ball = Ball()
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.phase = "aiming"
        self.message = "Frame reset"
