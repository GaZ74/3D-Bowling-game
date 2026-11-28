"""Bowling turns, pinfall, and per-player ten-frame scoring state."""

from dataclasses import dataclass, field
import math
import random

from config import (BALL_RADIUS, BALL_START_Z, BALL_SPEED_DEFAULT,
                    BALL_SPEED_MAX, BALL_SPEED_MIN, BALL_SPEED_STEP,
                    MAX_AIM_ANGLE, MAX_START_X, START_X_STEP, PIN_DECK_Z,
                    PIN_SPACING, PIN_ROW_DEPTH, PIN_ROWS, PHYSICS_HZ, MAX_PHYSICS_STEPS)
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
    pin_id: int = 0
    home_x: float | None = None
    home_z: float | None = None
    cleared: bool = False
    pin_contacts: set = field(default_factory=set)
    roll_angular_scale: float = 1.0
    roll_contact_bias: float = 0.0


class BowlingGame:
    def __init__(self):
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.ball = Ball()
        self.pins = self._make_pins()
        self.phase = "menu"  # menu, aiming, rolling, result
        self.rolls_this_frame = 0
        self.message = "Aim with arrows, set power, then press Space"
        self.player_count = 1
        self.menu_selection = 1
        self.current_player = 0
        self.turn_number = 1
        self.scorecards = [Scorecard(), Scorecard()]
        self.scorecard = self.scorecards[0]
        self.player_totals = [0, 0]
        self.player_frames = [card.frames for card in self.scorecards]
        self.score_notification = "SCORE METER"
        self.match_over = False
        self._frame_complete_pending = False
        self._pins_before_roll = 10
        self._physics_accumulator = 0.0
        self._physics_step = 1.0 / PHYSICS_HZ

    @staticmethod
    def _make_pins():
        pins = []
        pin_id = 1
        for row in range(PIN_ROWS):
            count = row + 1
            z = PIN_DECK_Z + row * PIN_ROW_DEPTH
            for col in range(count):
                x = (col - (count - 1) / 2) * PIN_SPACING
                pins.append(Pin(x, z, pin_id=pin_id, home_x=x, home_z=z))
                pin_id += 1
        return pins

    def _reset_standing_pins(self):
        """Sweep fallen pins and restore each standing pin to its home spot."""
        for pin in self.pins:
            if pin.down:
                pin.cleared = True
                continue
            pin.x = pin.home_x if pin.home_x is not None else pin.x
            pin.z = pin.home_z if pin.home_z is not None else pin.z
            pin.vx = pin.vz = 0.0
            pin.tilt_x = pin.tilt_z = 0.0
            pin.omega_x = pin.omega_z = 0.0
            pin.ball_contacted = False
            pin.pin_contacts.clear()

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
            self.aim = max(-MAX_AIM_ANGLE, min(
                MAX_AIM_ANGLE, self.aim + direction * math.radians(0.1)))

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
        if self.phase != "aiming" or self.match_over:
            return
        for pin in self.pins:
            pin.ball_contacted = False
            pin.pin_contacts.clear()
            # Tiny per-roll differences in balance and contact alignment make
            # each rack react slightly differently without changing the aim.
            pin.roll_angular_scale = random.uniform(0.93, 1.07)
            pin.roll_contact_bias = math.radians(random.uniform(-1.5, 1.5))
        self._pins_before_roll = self.standing_pins
        self.ball = Ball(x=self.start_x, vx=math.sin(self.aim) * self.power,
                         vz=math.cos(self.aim) * self.power)
        self.phase = "rolling"
        self.message = "Ball in motion"

    def move_menu_selection(self, direction: int):
        if self.phase == "menu":
            self.menu_selection = 2 if direction > 0 else 1

    def start_game(self, player_count: int):
        if player_count not in (1, 2):
            return
        self.player_count = player_count
        self.menu_selection = player_count
        self.reset_frame()
        self.phase = "aiming"
        self.message = ("Single-player game - frame 1" if player_count == 1
                        else "Local game - Player 1, turn 1/20")

    def return_to_menu(self):
        self.menu_selection = self.player_count
        self.reset_frame()
        self.phase = "menu"
        self.message = "Select a game mode"

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
                # Keep simulating pin-to-pin contacts after the ball stops.
                # Record the roll only after every pin has finished settling.
                if self.pins_moving:
                    self.message = "Ball reached reset zone; pins are settling"
                else:
                    self.rolls_this_frame += 1
                    pinfall = max(0, self._pins_before_roll - self.standing_pins)
                    card = self.scorecards[self.current_player]
                    event = card.record_roll(pinfall)
                    self.player_totals[self.current_player] = card.total_score
                    self._frame_complete_pending = card.last_frame_complete
                    self.phase = "result"
                    player_label = f"P{self.current_player + 1}"
                    if event == "TURKEY":
                        self.score_notification = f"{player_label} TURKEY!"
                        self.message = "TURKEY! Gobble Gobble achievement unlocked!"
                    elif event == "PERFECT_GAME":
                        self.score_notification = f"{player_label} PERFECT 300!"
                        self.message = "PERFECT GAME! 300!"
                    elif card.game_over and self.ball.on_guide:
                        self.message = (f"{player_label} finished with {card.total_score} - "
                                        "ball followed the guide to reset")
                    elif self.ball.on_guide:
                        self.message = (f"Ball followed the side guide to the reset zone - "
                                       f"{10 - self.standing_pins} pin(s) down")
                    else:
                        self.message = f"Ball reached the reset zone - {10 - self.standing_pins} pin(s) down"
                    self.match_over = all(self.scorecards[index].game_over
                                           for index in range(self.player_count))
                    if self.match_over and event != "PERFECT_GAME":
                        if event == "TURKEY":
                            self.score_notification = f"{player_label} TURKEY!"
                            self.message = (f"Game complete - {player_label}: {card.total_score}; "
                                            "Turkey achievement unlocked!")
                        else:
                            self.score_notification = f"{player_label} FINAL {card.total_score}"
                            self.message = f"Game complete - {player_label}: {card.total_score}"
        if (self.phase == "result" and not self.pins_moving
                and "press Space" not in self.message):
            self.message += " - press Space for next roll"

    def next_roll(self):
        if self.phase != "result":
            return
        if self.pins_moving:
            self.message = "Pins are still settling"
            return
        if self.match_over:
            self.message = "Game complete - press R to start a new game"
            return

        card = self.scorecards[self.current_player]
        if self._frame_complete_pending:
            other = 1 - self.current_player
            if self.player_count == 2 and not self.scorecards[other].game_over:
                self.current_player = other
            elif card.game_over:
                self.message = "Game complete - press R to start a new game"
                self.match_over = True
                return
            self.turn_number += 1
            self.pins = self._make_pins()
            self.rolls_this_frame = 0
            self._frame_complete_pending = False
            active_card = self.scorecards[self.current_player]
            if self.player_count == 2:
                self.message = (f"Player {self.current_player + 1}, frame "
                                f"{min(active_card.current_frame + 1, 10)}")
            else:
                self.message = f"Frame {min(active_card.current_frame + 1, 10)} - pins reset"
        elif card.reset_rack_after_roll:
            # Tenth-frame bonus balls receive a fresh rack when earned.
            self.pins = self._make_pins()
            self.rolls_this_frame = len(card.frames[card.current_frame])
        else:
            # The second ball gets only the pins that remained standing.
            self._reset_standing_pins()
            self.message = "Standing pins reset for the second throw"
        self.ball = Ball()
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.phase = "aiming"
        self._physics_accumulator = 0.0

    def reset_frame(self):
        self.scorecards = [Scorecard(), Scorecard()]
        self.scorecard = self.scorecards[0]
        self.player_frames = [card.frames for card in self.scorecards]
        self.player_totals = [0, 0]
        self.current_player = 0
        self.turn_number = 1
        self.score_notification = "SCORE METER"
        self.match_over = False
        self._frame_complete_pending = False
        self.pins = self._make_pins()
        self.rolls_this_frame = 0
        self.ball = Ball()
        self.aim = 0.0
        self.start_x = 0.0
        self.power = BALL_SPEED_DEFAULT
        self.phase = "aiming"
        self.message = "Game reset"
        self._physics_accumulator = 0.0


