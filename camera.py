"""Camera modes and right-drag look offsets for the follow camera."""

import math

from config import (BALL_HOLDER_X, BALL_HOLDER_Z, BALL_START_Z,
                    CAMERA_MODES, FOLLOW_STOP_Z, PIN_DECK_Z,
                    SCOREBOARD_LEFT_ANGLE)


class Camera:
    def __init__(self):
        self.mode_index = 0
        self.position = [0.0, 2.1, -7.0]
        self.target = [0.0, 0.5, -1.3]
        self.look_yaw = 0.0
        self.look_pitch = 0.0
        self.look_dragging = False

    @property
    def mode(self):
        return CAMERA_MODES[self.mode_index]

    def cycle_mode(self):
        self.mode_index = (self.mode_index + 1) % len(CAMERA_MODES)
        if self.mode == "follow":
            self.look_yaw = 0.0
            self.look_pitch = 0.0

    def begin_look(self):
        if self.mode == "follow":
            self.look_dragging = True

    def end_look(self):
        self.look_dragging = False

    def look(self, dx: int, dy: int):
        if self.mode != "follow" or not self.look_dragging:
            return
        self.look_yaw = max(-1.35, min(1.35, self.look_yaw + dx * 0.003))
        self.look_pitch = max(-0.55, min(0.55, self.look_pitch - dy * 0.003))

    def update(self, ball, dt: float):
        if self.mode == "fixed":
            # Lower overview covers the lane without rising above the room.
            desired = ([0.0, 2.2, BALL_START_Z - 7.0],
                       [0.0, 0.8, PIN_DECK_Z * 0.55])
        elif self.mode == "result":
            # Keep the result view inside the room and frame the pin deck.
            desired = ([ball.x * 0.35, 1.9, PIN_DECK_Z - 4.0],
                       [0.0, 0.35, PIN_DECK_Z + 0.35])
        elif self.mode == "scoreboard":
            # Track the board from the front-right, matching its reversed yaw.
            angle = math.radians(SCOREBOARD_LEFT_ANGLE)
            distance = 2.8
            desired = ([BALL_HOLDER_X + math.sin(angle) * distance, 1.10,
                        BALL_HOLDER_Z - math.cos(angle) * distance],
                       [BALL_HOLDER_X, 1.45, BALL_HOLDER_Z])
        else:  # orbit around a focus point just ahead of the ball
            if not self.look_dragging:
                recenter = min(1.0, dt * 2.5)
                self.look_yaw += (0.0 - self.look_yaw) * recenter
                self.look_pitch += (0.0 - self.look_pitch) * recenter
            # Stop tracking at two thirds of the lane so the camera stays
            # inside the room while the ball finishes its run to the pins.
            focus_z = min(ball.z, FOLLOW_STOP_Z)
            focus = (ball.x * 0.68, 0.48, focus_z + 1.0)
            yaw = self.look_yaw
            pitch = max(-0.2, min(0.75, 0.18 + self.look_pitch))
            distance = 3.0
            horizontal = distance * math.cos(pitch)
            desired = ([focus[0] - math.sin(yaw) * horizontal,
                        focus[1] + math.sin(pitch) * distance,
                        focus[2] - math.cos(yaw) * horizontal],
                       [focus[0], focus[1], focus[2]])
        blend = min(1.0, dt * 3.5)
        for current, goal in zip((self.position, self.target), desired):
            for i in range(3):
                current[i] += (goal[i] - current[i]) * blend
