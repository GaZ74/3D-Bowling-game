"""OpenGL drawing. Keep game rules out of this module."""

import math
import time
from pathlib import Path
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt, gluOrtho2D
from OpenGL.GL.shaders import compileProgram, compileShader
from OpenGL.GLUT import (glutBitmapCharacter, glutSwapBuffers,
                         GLUT_BITMAP_HELVETICA_18)
from PIL import Image

from config import (BALL_RADIUS, LANE_BALL_CENTER_LIMIT, LANE_HALF_WIDTH,
                    LANE_START_Z, PIN_DECK_Z, RESET_ZONE_Z,
                    WINDOW_HEIGHT, WINDOW_WIDTH)
from physics import make_guide_curve

_lane_program = None
_shader_attempted = False
_textures = {}
_ASSET_DIR = Path(__file__).parent / "assets"
_ROOM_HALF_WIDTH = 5.5
_ROOM_FRONT_Z = -10.0
_ROOM_BACK_Z = 11.0
_ROOM_HEIGHT = 5.8
_fps_started = time.perf_counter()
_fps_frames = 0
_fps_value = 0.0
_guide_rail_points = None
_hud_text = [None, None, None, None, None]
_hud_lists = [0, 0, 0, 0, 0]
_ROOM_LIGHT_POSITIONS = [(-2.5, 5.35, -4.0, 1.0),
                         (2.5, 5.35, -0.5, 1.0),
                         (-2.5, 5.35, 4.0, 1.0),
                         (2.5, 5.35, 7.0, 1.0)]


def _get_texture(filename):
    if filename in _textures:
        return _textures[filename]
    try:
        image = Image.open(_ASSET_DIR / filename).convert("RGB").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, image.tobytes())
        _textures[filename] = texture
    except Exception as exc:
        print(f"Texture {filename} unavailable; using fallback material: {exc}")
        _textures[filename] = 0
    return _textures[filename]


def _draw_textured_quad(texture, color, normal, vertices):
    if texture:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture)
    else:
        glDisable(GL_TEXTURE_2D)
    glColor3f(*color)
    glBegin(GL_QUADS)
    glNormal3f(*normal)
    for x, y, z, u, v in vertices:
        glTexCoord2f(u, v)
        glVertex3f(x, y, z)
    glEnd()
    glDisable(GL_TEXTURE_2D)


def _draw_room():
    wall = _get_texture("wall.jpg")
    floor = _get_texture("floor.jpg")
    half = _ROOM_HALF_WIDTH
    front, back, height = _ROOM_FRONT_Z, _ROOM_BACK_Z, _ROOM_HEIGHT
    _draw_textured_quad(floor, (0.72, 0.72, 0.72), (0, 1, 0), [
        (-half, -0.035, front, 0, 0), (half, -0.035, front, 5, 0),
        (half, -0.035, back, 5, 10), (-half, -0.035, back, 0, 10)])
    _draw_textured_quad(wall, (0.75, 0.75, 0.75), (1, 0, 0), [
        (-half, 0, front, 0, 0), (-half, height, front, 0, 4),
        (-half, height, back, 8, 4), (-half, 0, back, 8, 0)])
    _draw_textured_quad(wall, (0.75, 0.75, 0.75), (-1, 0, 0), [
        (half, 0, back, 0, 0), (half, height, back, 0, 4),
        (half, height, front, 8, 4), (half, 0, front, 8, 0)])
    _draw_textured_quad(wall, (0.75, 0.75, 0.75), (0, 0, -1), [
        (-half, 0, back, 0, 0), (-half, height, back, 0, 4),
        (half, height, back, 4, 4), (half, 0, back, 4, 0)])
    _draw_textured_quad(0, (0.18, 0.20, 0.23), (0, -1, 0), [
        (-half, height, back, 0, 0), (-half, height, front, 0, 1),
        (half, height, front, 1, 1), (half, height, back, 1, 0)])

    # Light ceiling panels provide a readable indoor alley silhouette.
    glDisable(GL_LIGHTING)
    for z in (-7.0, -2.5, 2.0, 6.5):
        glColor3f(0.78, 0.73, 0.59)
        glBegin(GL_QUADS)
        glVertex3f(-1.05, height - 0.03, z - 0.34)
        glVertex3f(1.05, height - 0.03, z - 0.34)
        glVertex3f(1.05, height - 0.03, z + 0.34)
        glVertex3f(-1.05, height - 0.03, z + 0.34)
        glEnd()
        glColor3f(1.0, 0.91, 0.68)
        glBegin(GL_QUADS)
        glVertex3f(-0.88, height - 0.015, z - 0.23)
        glVertex3f(0.88, height - 0.015, z - 0.23)
        glVertex3f(0.88, height - 0.015, z + 0.23)
        glVertex3f(-0.88, height - 0.015, z + 0.23)
        glEnd()
    glEnable(GL_LIGHTING)


def _draw_scoreboard_rounded_panel(left, bottom, right, top, z, radius, color):
    glColor3f(*color)
    glBegin(GL_POLYGON)
    for center_x, center_y, start_angle in (
            (right - radius, bottom + radius, -90),
            (right - radius, top - radius, 0),
            (left + radius, top - radius, 90),
            (left + radius, bottom + radius, 180)):
        for segment in range(9):
            angle = math.radians(start_angle + segment * 11.25)
            glVertex3f(center_x + math.cos(angle) * radius,
                       center_y + math.sin(angle) * radius, z)
    glEnd()


def _draw_scoreboard_quad(left, bottom, right, top, z, color):
    glColor3f(*color)
    glBegin(GL_QUADS)
    glVertex3f(left, bottom, z)
    glVertex3f(right, bottom, z)
    glVertex3f(right, top, z)
    glVertex3f(left, top, z)
    glEnd()


def _draw_scoreboard_text(text, x, y, z, color):
    glColor3f(*color)
    glRasterPos3f(x, y, z)
    for char in text:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))


def _draw_scoreboard(game):
    """Draw the pinfall board hanging above the centered lane approach."""
    left, right = -1.9, 1.9
    bottom, top, z = 3.52, 5.13, -5.72
    glDisable(GL_LIGHTING)

    # Suspended rods and a crossbar attach the panel to the lowered ceiling.
    glColor3f(0.10, 0.10, 0.12)
    glBegin(GL_QUADS)
    for x in (-0.78, 0.78):
        glVertex3f(x - 0.045, top, z + 0.10)
        glVertex3f(x + 0.045, top, z + 0.10)
        glVertex3f(x + 0.045, _ROOM_HEIGHT - 0.06, z + 0.10)
        glVertex3f(x - 0.045, _ROOM_HEIGHT - 0.06, z + 0.10)
    glVertex3f(-0.95, _ROOM_HEIGHT - 0.08, z + 0.16)
    glVertex3f(0.95, _ROOM_HEIGHT - 0.08, z + 0.16)
    glVertex3f(0.95, _ROOM_HEIGHT - 0.20, z + 0.16)
    glVertex3f(-0.95, _ROOM_HEIGHT - 0.20, z + 0.16)
    glEnd()

    _draw_scoreboard_rounded_panel(left - 0.04, bottom - 0.02,
                                   right + 0.04, top + 0.02, z + 0.04, 0.38,
                                   (0.16, 0.025, 0.075))
    _draw_scoreboard_rounded_panel(left, bottom, right, top, z, 0.32,
                                   (0.59, 0.055, 0.25))
    _draw_scoreboard_quad(left + 0.08, bottom + 0.35, right - 0.08, top - 0.43,
                          z - 0.02, (0.40, 0.035, 0.16))
    _draw_scoreboard_quad(left + 0.08, bottom + 0.08, right - 0.08, bottom + 0.31,
                          z - 0.02, (0.31, 0.025, 0.12))
    _draw_scoreboard_quad(left + 0.08, top - 0.38, right - 0.08, top - 0.08,
                          z - 0.02, (0.34, 0.035, 0.14))

    heading = game.score_notification or "SCORE METER"
    heading_color = ((1.0, 0.91, 0.45) if "TURKEY" in heading or "PERFECT" in heading
                     else (1.0, 0.78, 0.84))
    _draw_scoreboard_text(heading, left + 0.20, top - 0.28, z - 0.04,
                          heading_color)
    grid_left, grid_right = left + 0.53, right - 0.12
    cell_width = (grid_right - grid_left) / 10
    for frame in range(10):
        # The display is viewed from the negative-Z side, where screen-left
        # maps to positive world X. Reverse world X so frames read 1 through 10.
        cell_x = grid_right - (frame + 0.5) * cell_width
        _draw_scoreboard_text(str(frame + 1), cell_x + 0.045,
                              top - 0.61, z - 0.04, (1.0, 0.72, 0.82))

    glColor3f(0.95, 0.27, 0.53)
    glLineWidth(1.2)
    glBegin(GL_LINES)
    grid_bottom, grid_middle, grid_top = bottom + 0.35, bottom + 0.72, top - 0.62
    for index in range(11):
        x = grid_left + index * cell_width
        glVertex3f(x, grid_bottom, z - 0.04)
        glVertex3f(x, grid_top, z - 0.04)
    horizontal_lines = ((grid_bottom, grid_middle, grid_top)
                        if game.player_count == 2 else (grid_bottom, grid_top))
    for y in horizontal_lines:
        glVertex3f(left + 0.08, y, z - 0.04)
        glVertex3f(right - 0.08, y, z - 0.04)
    glEnd()

    for player in range(game.player_count):
        if game.player_count == 1:
            row_y = (grid_bottom + grid_top) * 0.5
        else:
            row_y = ((grid_middle + grid_top) * 0.5 if player == 0
                     else (grid_bottom + grid_middle) * 0.5)
        active = player == game.current_player
        color = (1.0, 0.85, 0.48) if active else (0.92, 0.68, 0.77)
        _draw_scoreboard_text(f"P{player + 1}", left + 0.16, row_y,
                              z - 0.05, color)
        card = game.scorecards[player]
        cumulative = card.cumulative_scores
        for frame_index in range(10):
            cell_x = grid_right - (frame_index + 0.5) * cell_width
            marks = card.frame_symbol(frame_index)
            if marks:
                _draw_scoreboard_text(marks,
                                      cell_x + 0.035 * len(marks), row_y + 0.055,
                                      z - 0.05, color)
            frame_score = cumulative[frame_index]
            if frame_score is not None:
                score_text = str(frame_score)
                _draw_scoreboard_text(score_text,
                                      cell_x + 0.035 * len(score_text), row_y - 0.105,
                                      z - 0.05, color)

    _draw_scoreboard_text(f"P1 TOTAL  {game.player_totals[0]}",
                          left + 0.18, bottom + 0.15, z - 0.04, (1.0, 0.82, 0.54))
    if game.player_count == 2:
        _draw_scoreboard_text(f"P2 TOTAL  {game.player_totals[1]}",
                              left + 2.25, bottom + 0.15, z - 0.04,
                              (1.0, 0.82, 0.54))
    glLineWidth(1.0)
    glEnable(GL_LIGHTING)


def _draw_contact_shadow(x, z, radius_x, radius_z, opacity=0.24):
    """Soft fake contact shadow on the floor for the legacy fixed pipeline."""
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDepthMask(GL_FALSE)
    glColor4f(0.015, 0.018, 0.025, opacity)
    glBegin(GL_TRIANGLE_FAN)
    glVertex3f(x, 0.012, z)
    for index in range(33):
        angle = 2.0 * math.pi * index / 32
        glVertex3f(x + math.cos(angle) * radius_x, 0.012,
                   z + math.sin(angle) * radius_z)
    glEnd()
    glDepthMask(GL_TRUE)
    glDisable(GL_BLEND)
    glEnable(GL_LIGHTING)


def _get_lane_program():
    global _lane_program, _shader_attempted
    if _shader_attempted:
        return _lane_program
    _shader_attempted = True
    shader_dir = Path(__file__).parent / "shaders"
    try:
        vertex = (shader_dir / "lane.vert").read_text(encoding="utf-8")
        fragment = (shader_dir / "lane.frag").read_text(encoding="utf-8")
        _lane_program = compileProgram(
            compileShader(vertex, GL_VERTEX_SHADER),
            compileShader(fragment, GL_FRAGMENT_SHADER))
    except Exception as exc:
        print(f"Lane shader unavailable; using fallback material: {exc}")
    return _lane_program


def _draw_lane():
    floor = _get_texture("floor.jpg")
    program = _get_lane_program()
    if program:
        glUseProgram(program)
        sampler = glGetUniformLocation(program, "uFloorTexture")
        if sampler >= 0:
            glUniform1i(sampler, 0)
    if floor:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, floor)
    else:
        glDisable(GL_TEXTURE_2D)
    glColor3f(1.0, 1.0, 1.0)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0)
    glVertex3f(-LANE_HALF_WIDTH, 0, LANE_START_Z)
    glTexCoord2f(2.2, 0)
    glVertex3f(LANE_HALF_WIDTH, 0, LANE_START_Z)
    glTexCoord2f(2.2, 5.2)
    glVertex3f(LANE_HALF_WIDTH, 0, PIN_DECK_Z + 2.0)
    glTexCoord2f(0, 5.2)
    glVertex3f(-LANE_HALF_WIDTH, 0, PIN_DECK_Z + 2.0)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    if program:
        glUseProgram(0)

    # Dark gutters and low rails give the lane a clearer alley silhouette.
    glColor3f(0.07, 0.09, 0.13)
    glBegin(GL_QUADS)
    for side in (-1, 1):
        inner = side * LANE_HALF_WIDTH
        outer = side * (LANE_HALF_WIDTH + 0.32)
        glVertex3f(inner, -0.015, LANE_START_Z)
        glVertex3f(outer, -0.015, LANE_START_Z)
        glVertex3f(outer, -0.015, PIN_DECK_Z + 2.0)
        glVertex3f(inner, -0.015, PIN_DECK_Z + 2.0)
    glEnd()
    glColor3f(0.78, 0.58, 0.32)
    glBegin(GL_LINES)
    for side in (-1, 1):
        x = side * LANE_HALF_WIDTH
        glVertex3f(x, 0.025, LANE_START_Z)
        glVertex3f(x, 0.025, PIN_DECK_Z + 2.0)
    glEnd()
    # Approach foul line and the classic target-arrow inlays.
    glLineWidth(2.0)
    glColor3f(0.91, 0.78, 0.52)
    glBegin(GL_LINES)
    glVertex3f(-LANE_HALF_WIDTH, 0.018, LANE_START_Z + 0.32)
    glVertex3f(LANE_HALF_WIDTH, 0.018, LANE_START_Z + 0.32)
    glEnd()
    glLineWidth(1.0)
    glColor3f(0.76, 0.86, 0.82)
    glBegin(GL_TRIANGLES)
    for x in (-0.84, -0.56, -0.28, 0.0, 0.28, 0.56, 0.84):
        glVertex3f(x - 0.075, 0.018, -1.20)
        glVertex3f(x + 0.075, 0.018, -1.20)
        glVertex3f(x, 0.018, -0.94)
    glEnd()
    glPointSize(4.0)
    glColor3f(0.95, 0.77, 0.43)
    glBegin(GL_POINTS)
    for x in (-0.70, -0.35, 0.0, 0.35, 0.70):
        glVertex3f(x, 0.018, LANE_START_Z + 0.78)
    glEnd()
    glPointSize(1.0)


def _draw_alley_decorations(ball_model):
    """Add lightweight neon trim, lane plaques, and a ball-return rack."""
    glDisable(GL_LIGHTING)
    # Low neon strips and colored wall pilasters brighten the brick room.
    glLineWidth(4.0)
    glColor3f(0.22, 0.95, 0.78)
    glBegin(GL_LINES)
    for side in (-1, 1):
        x = side * (_ROOM_HALF_WIDTH - 0.025)
        glVertex3f(x, 2.25, -8.0)
        glVertex3f(x, 2.25, 7.8)
    glEnd()
    glLineWidth(2.0)
    glColor3f(0.95, 0.25, 0.58)
    glBegin(GL_LINES)
    for side in (-1, 1):
        x = side * (_ROOM_HALF_WIDTH - 0.025)
        glVertex3f(x, 2.42, -8.0)
        glVertex3f(x, 2.42, 7.8)
    glEnd()
    glLineWidth(1.0)

    # Small illuminated plaques on the back wall add an alley identity.
    for center_x, color, label in ((-3.3, (0.08, 0.23, 0.25), "OPEN"),
                                   (3.3, (0.29, 0.08, 0.18), "BOWL")):
        glColor3f(*color)
        glBegin(GL_QUADS)
        glVertex3f(center_x - 0.95, 2.1, _ROOM_BACK_Z - 0.04)
        glVertex3f(center_x + 0.95, 2.1, _ROOM_BACK_Z - 0.04)
        glVertex3f(center_x + 0.95, 3.25, _ROOM_BACK_Z - 0.04)
        glVertex3f(center_x - 0.95, 3.25, _ROOM_BACK_Z - 0.04)
        glEnd()
        _draw_scoreboard_text(label, center_x - 0.42, 2.62,
                              _ROOM_BACK_Z - 0.07, (0.76, 0.94, 0.87))

    # A compact ball-return console stays outside the right gutter.
    x0, x1 = 1.72, 2.92
    z0, z1 = -4.65, -2.95
    y0, y1 = 0.10, 0.55
    glColor3f(0.07, 0.10, 0.13)
    glBegin(GL_QUADS)
    # top, front, back, and side faces
    glVertex3f(x0, y1, z0); glVertex3f(x1, y1, z0); glVertex3f(x1, y1, z1); glVertex3f(x0, y1, z1)
    glVertex3f(x0, y0, z0); glVertex3f(x1, y0, z0); glVertex3f(x1, y1, z0); glVertex3f(x0, y1, z0)
    glVertex3f(x0, y0, z1); glVertex3f(x0, y1, z1); glVertex3f(x1, y1, z1); glVertex3f(x1, y0, z1)
    glVertex3f(x0, y0, z0); glVertex3f(x0, y1, z0); glVertex3f(x0, y1, z1); glVertex3f(x0, y0, z1)
    glVertex3f(x1, y0, z0); glVertex3f(x1, y0, z1); glVertex3f(x1, y1, z1); glVertex3f(x1, y1, z0)
    glEnd()
    glColor3f(0.20, 0.78, 0.70)
    glBegin(GL_LINES)
    glVertex3f(x0 + 0.08, y1 + 0.02, z0 + 0.12)
    glVertex3f(x1 - 0.08, y1 + 0.02, z0 + 0.12)
    glVertex3f(x0 + 0.08, y1 + 0.02, z1 - 0.12)
    glVertex3f(x1 - 0.08, y1 + 0.02, z1 - 0.12)
    glEnd()
    glEnable(GL_LIGHTING)
    for x, color in ((2.02, (0.13, 0.30, 0.86)), (2.45, (0.71, 0.12, 0.39))):
        glPushMatrix()
        glTranslatef(x, y1 + BALL_RADIUS * 0.92, (z0 + z1) * 0.5)
        ball_model.draw(color)
        glPopMatrix()


def _draw_guide_rails():
    """Draw the dark return guides that route a wide shot around the pins."""
    global _guide_rail_points
    if _guide_rail_points is None:
        _guide_rail_points = {}
        for side in (-1, 1):
            _guide_rail_points[side] = make_guide_curve(
                side,
                start_x=side * LANE_BALL_CENTER_LIMIT,
                start_z=LANE_START_Z,
            )[0]
    glDisable(GL_LIGHTING)
    glColor3f(0.035, 0.045, 0.06)
    glLineWidth(5.0)
    for side in (-1, 1):
        glBegin(GL_LINE_STRIP)
        for x, z in _guide_rail_points[side]:
            glVertex3f(x, 0.035, z)
        glEnd()
    # A dark reset pocket marks where the guided ball comes to rest.
    glBegin(GL_LINE_LOOP)
    for index in range(48):
        angle = 2.0 * math.pi * index / 48
        glVertex3f(math.cos(angle) * 1.7, 0.035,
                   RESET_ZONE_Z + math.sin(angle) * 0.34)
    glEnd()
    glLineWidth(1.0)
    glEnable(GL_LIGHTING)


def _draw_ball(ball, ball_model):
    _draw_contact_shadow(ball.x, ball.z, BALL_RADIUS * 1.8, BALL_RADIUS * 1.15, 0.35)
    glPushMatrix()
    glTranslatef(ball.x, BALL_RADIUS, ball.z)
    ball_model.draw((0.12, 0.20, 0.8))
    glPopMatrix()


def _draw_pins(pins, pin_model):
    for pin in pins:
        _draw_contact_shadow(pin.x, pin.z, 0.16, 0.12, 0.26)
        glPushMatrix()
        glTranslatef(pin.x, 0.0, pin.z)
        glRotatef(math.degrees(pin.tilt_z), 0, 0, 1)
        glRotatef(math.degrees(pin.tilt_x), 1, 0, 0)
        pin_model.draw((0.92, 0.91, 0.84))
        glPopMatrix()


def _draw_trajectory(points):
    glDisable(GL_LIGHTING)
    glColor3f(0.25, 0.95, 0.82)
    glLineStipple(1, 0x00FF)
    glEnable(GL_LINE_STIPPLE)
    glBegin(GL_LINE_STRIP)
    for x, y, z in points:
        glVertex3f(x, y, z)
    glEnd()
    glDisable(GL_LINE_STIPPLE)
    glEnable(GL_LIGHTING)


def _measure_fps():
    global _fps_started, _fps_frames, _fps_value
    _fps_frames += 1
    now = time.perf_counter()
    elapsed = now - _fps_started
    if elapsed >= 0.5:
        _fps_value = _fps_frames / elapsed
        _fps_frames = 0
        _fps_started = now
    return _fps_value


def _draw_hud(game, camera, fps):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.015, 0.025, 0.04, 0.86)
    glBegin(GL_QUADS)
    glVertex2i(14, WINDOW_HEIGHT - 164)
    glVertex2i(1045, WINDOW_HEIGHT - 164)
    glVertex2i(1045, WINDOW_HEIGHT - 14)
    glVertex2i(14, WINDOW_HEIGHT - 14)
    glEnd()
    glColor4f(0.16, 0.78, 0.70, 0.95)
    glBegin(GL_QUADS)
    glVertex2i(14, WINDOW_HEIGHT - 18)
    glVertex2i(1045, WINDOW_HEIGHT - 18)
    glVertex2i(1045, WINDOW_HEIGHT - 14)
    glVertex2i(14, WINDOW_HEIGHT - 14)
    glEnd()
    glDisable(GL_BLEND)
    state = "Guide to reset" if game.ball.on_guide else game.phase.title()
    total_turns = game.player_count * 10
    card = game.scorecards[game.current_player]
    frame = min(card.current_frame + (1 if game._frame_complete_pending else 0), 10)
    if frame == 0:
        frame = 1
    lines = [f"{game.player_count}P  |  TURN {game.turn_number}/{total_turns}  |  PLAYER {game.current_player + 1}  |  FRAME {frame}  |  {state.upper()}",
             f"SCORE {card.total_score}  |  PINS {game.standing_pins}/10  |  AIM {math.degrees(game.aim):+.0f} deg  |  POWER {game.power:.1f}  |  FPS {fps:.0f}",
             game.message,
             "ARROWS aim / power    A,D position    LEFT DRAG aim & power, release to throw",
             f"RIGHT DRAG look    SPACE throw / next roll    C camera    R reset    ESC title"]
    colors = ((0.46, 0.98, 0.86), (1.0, 0.90, 0.62), (0.98, 0.98, 1.0),
              (0.78, 0.86, 0.91), (0.78, 0.86, 0.91))
    for row, line in enumerate(lines):
        if line != _hud_text[row]:
            if _hud_lists[row]:
                glDeleteLists(_hud_lists[row], 1)
                _hud_lists[row] = 0
            _hud_text[row] = line
            new_list = glGenLists(1)
            if new_list:
                glNewList(new_list, GL_COMPILE)
                for char in line:
                    glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
                glEndList()
                _hud_lists[row] = new_list
        glColor3f(*colors[row])
        glRasterPos2i(28, WINDOW_HEIGHT - 39 - row * 26)
        if _hud_lists[row]:
            glCallList(_hud_lists[row])
        else:
            for char in line:
                glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def _draw_title_menu(game):
    """Draw a styled mode-selection screen over the alley scene."""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.012, 0.02, 0.035, 0.82)
    glBegin(GL_QUADS)
    glVertex2i(0, 0)
    glVertex2i(WINDOW_WIDTH, 0)
    glVertex2i(WINDOW_WIDTH, WINDOW_HEIGHT)
    glVertex2i(0, WINDOW_HEIGHT)
    glEnd()
    glDisable(GL_BLEND)

    def text_at(text, x, y, color):
        glColor3f(*color)
        glRasterPos2i(x, y)
        for char in text:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    center = WINDOW_WIDTH // 2
    # Framed title card and small graphic accents.
    glColor4f(0.035, 0.065, 0.09, 0.94)
    glBegin(GL_QUADS)
    glVertex2i(center - 285, 145)
    glVertex2i(center + 285, 145)
    glVertex2i(center + 285, 565)
    glVertex2i(center - 285, 565)
    glEnd()
    glColor3f(0.18, 0.82, 0.72)
    glBegin(GL_QUADS)
    glVertex2i(center - 285, 561)
    glVertex2i(center + 285, 561)
    glVertex2i(center + 285, 565)
    glVertex2i(center - 285, 565)
    glEnd()
    text_at("NIGHT LANES", center - 91, 505, (0.45, 0.98, 0.86))
    text_at("3D BOWLING", center - 75, 470, (1.0, 0.91, 0.63))
    text_at("CHOOSE YOUR GAME", center - 91, 414, (0.89, 0.94, 0.97))
    choices = ((1, "1   SINGLE PLAYER", "One scorecard  |  10 frames"),
               (2, "2   LOCAL PLAYERS", "Two scorecards  |  20 alternating turns"))
    for index, (players, label, description) in enumerate(choices):
        y = 333 - index * 78
        selected = game.menu_selection == players
        if selected:
            glColor4f(0.10, 0.27, 0.32, 0.98)
            glBegin(GL_QUADS)
            glVertex2i(center - 230, y - 22)
            glVertex2i(center + 230, y - 22)
            glVertex2i(center + 230, y + 39)
            glVertex2i(center - 230, y + 39)
            glEnd()
        color = (1.0, 0.87, 0.43) if selected else (0.86, 0.90, 0.94)
        desc_color = (0.68, 0.88, 0.86) if selected else (0.62, 0.70, 0.76)
        text_at((">  " if selected else "   ") + label, center - 145, y + 12, color)
        text_at(description, center - 135, y - 9, desc_color)
    text_at("UP / DOWN   SELECT     ENTER   START", center - 151, 184,
            (0.84, 0.90, 0.94))
    text_at("ESC   RETURN TO THIS SCREEN", center - 118, 158,
            (0.62, 0.72, 0.79))
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_scene(game, camera, ball_model, pin_model):
    fps = _measure_fps()
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(*camera.position, *camera.target, 0, 1, 0)
    # Fixed-function light positions are transformed by the active view matrix.
    for index, position in enumerate(_ROOM_LIGHT_POSITIONS):
        glLightfv(GL_LIGHT0 + index, GL_POSITION, position)
    _draw_room()
    _draw_alley_decorations(ball_model)
    if game.phase == "menu":
        _draw_lane()
        _draw_guide_rails()
        _draw_pins(game.pins, pin_model)
        _draw_ball(game.ball, ball_model)
        _draw_title_menu(game)
        glutSwapBuffers()
        return
    _draw_scoreboard(game)
    _draw_lane()
    _draw_guide_rails()
    _draw_pins(game.pins, pin_model)
    _draw_ball(game.ball, ball_model)
    if game.phase == "aiming":
        _draw_trajectory(game.trajectory())
    _draw_hud(game, camera, fps)
    glutSwapBuffers()
