"""OpenGL drawing. Keep game rules out of this module."""

import math
import time
import colorsys
import numpy as np
from pathlib import Path
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt, gluOrtho2D, gluPerspective
from OpenGL.GL.shaders import compileProgram, compileShader
from OpenGL.GLUT import (glutBitmapCharacter, glutSwapBuffers,
                         glutStrokeCharacter, GLUT_BITMAP_HELVETICA_18,
                         GLUT_STROKE_ROMAN, glutStrokeWidth)
from PIL import Image

from config import (BALL_HOLDER_X, BALL_HOLDER_Z, BALL_RADIUS, BALL_START_Z,
                    CLUB_BALL_SOURCE_X, CLUB_CEILING_Y, CLUB_FLOOR_SOURCE_Y,
                    CLUB_PIN_CENTER_SOURCE_Z,
                    LANE_BALL_CENTER_LIMIT, LANE_HALF_WIDTH, LANE_START_Z,
                    PIN_DECK_Z, RESET_ZONE_Z, SCOREBOARD_LEFT_ANGLE,
                    WINDOW_HEIGHT, WINDOW_WIDTH)
from physics import make_guide_curve

_lane_program = None
_shader_attempted = False
_textures = {}
_ASSET_DIR = Path(__file__).parent / "assets"
_ROOM_HALF_WIDTH = 5.5
_ROOM_FRONT_Z = LANE_START_Z - 1.5
_ROOM_BACK_Z = RESET_ZONE_Z + 3.0
_ROOM_HEIGHT = 5.8
_scoreboard_text_scale = 0.001
_scoreboard_text_x_scale = 0.001
_fps_started = time.perf_counter()
_fps_frames = 0
_fps_value = 0.0
_guide_rail_points = None
_hud_text = [None, None, None, None, None]
_hud_lists = [0, 0, 0, 0, 0]
# Six point lights model ceiling fixtures along the lanes. The final two
# compatibility-pipeline slots are reserved for the animated graffiti spots.
BULB_LIGHT_POSITIONS = tuple(
    (x, 3.35, z, 1.0)
    for z in (-8.0, 2.0, 12.0)
    for x in (-2.7, 2.7)
)
GRAFFITI_LIGHT_POSITIONS = (
    # Move each source just inside its wall so it lights the wall face too.
    (3.6857, 1.72, 9.9105, 1.0),
    (-6.1705, 1.72, 9.8850, 1.0),
)
WARM_BULB_RGB = (1.0, 0.90, 0.76)
ROOM_TAGS_EXCLUDED_FROM_SHADOWS = ("rgb_graffiti", "warm_ceiling_lights")
_SHADOW_SIZE = 768
_SHADOW_ORTHO = (-8.0, 8.0, -24.0, 24.0)
_SHADOW_LIGHT_HEIGHT = 3.35
_SHADOW_LIGHT_CENTER_Z = 8.0
_SHADOW_NEAR = 0.1
_SHADOW_FAR = 8.0
_shadow_attempted = False
_shadow_fbo = 0
_shadow_texture = 0
_static_shadow_texture = 0
_shadow_depth_program = 0
_shadow_mask_program = 0


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


def _graffiti_rgb():
    hue = (time.perf_counter() * 0.07) % 1.0
    return colorsys.hsv_to_rgb(hue, 0.95, 1.0)


def _graffiti_light_rgb():
    # Keep the emitted strokes vivid, but use a softer, less saturated tint
    # for the surrounding light spill.
    return tuple(0.35 + channel * 0.65 for channel in _graffiti_rgb())


def _draw_graffiti_lane_spill():
    """Add soft RGB spill across the imported lanes and both side walls."""
    floor_color = _graffiti_rgb()
    wall_color = _graffiti_light_rgb()
    center_x, center_z = -1.25, 9.90
    radius_x, radius_z = 5.8, 8.5
    segments = 48
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glDepthMask(GL_FALSE)
    glBegin(GL_TRIANGLE_FAN)
    glColor4f(*floor_color, 0.30)
    glVertex3f(center_x, 0.055, center_z)
    glColor4f(*floor_color, 0.0)
    for index in range(segments + 1):
        angle = 2.0 * math.pi * index / segments
        glVertex3f(center_x + math.cos(angle) * radius_x, 0.055,
                   center_z - math.sin(angle) * radius_z)
    glEnd()
    # The two wall washes sit just inside the imported wall faces, centered on
    # each neon sign. Their broad falloff makes the color reach nearby lanes.
    for wall_x, inward in ((3.76, -1.0), (-6.22, 1.0)):
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(*wall_color, 0.08)
        glVertex3f(wall_x, 1.64, center_z)
        glColor4f(*wall_color, 0.0)
        for index in range(segments + 1):
            angle = 2.0 * math.pi * index / segments
            glVertex3f(wall_x, 1.64 + math.cos(angle) * 1.0,
                       center_z + inward * math.sin(angle) * 4.5)
        glEnd()
    glDepthMask(GL_TRUE)
    glDisable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_LIGHTING)


def _update_graffiti_lights():
    """Aim two softer RGB spotlights from the graffiti across the lane bank."""
    color = _graffiti_light_rgb()
    target = np.asarray((0.0, 0.2, 9.90))
    first_light = GL_LIGHT0 + len(BULB_LIGHT_POSITIONS)
    for index, position in enumerate(GRAFFITI_LIGHT_POSITIONS):
        light = first_light + index
        direction = target - np.asarray(position[:3])
        direction /= max(float(np.linalg.norm(direction)), 1e-6)
        glLightfv(light, GL_POSITION, position)
        glLightfv(light, GL_SPOT_DIRECTION, direction)
        # A broad beam spreads the graffiti glow across every lane, while the
        # floor-only additive wash supplies the visible color without bathing
        # the ceiling in RGB.
        glLightf(light, GL_SPOT_CUTOFF, 85.0)
        glLightf(light, GL_SPOT_EXPONENT, 2.0)
        glLightfv(light, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
        glLightfv(light, GL_DIFFUSE, tuple(channel * 2.0 for channel in color) + (1.0,))


def _draw_room(room_model=None, exclude_dynamic_tags=()):
    if room_model is not None:
        # Rebuild the GLB's original units, then rotate its +X-to-pin axis
        # onto game +Z. These anchors put the rack approach and pin head on
        # the same coordinates used by BowlingGame and the physics solver.
        center = room_model.source_center
        unit_scale = 1.0 / room_model.normalization_scale
        glPushMatrix()
        glTranslatef(center[2] - CLUB_PIN_CENTER_SOURCE_Z,
                     center[1] - CLUB_FLOOR_SOURCE_Y,
                     BALL_START_Z + CLUB_BALL_SOURCE_X - center[0])
        glRotatef(90.0, 0.0, 1.0, 0.0)
        glScalef(unit_scale, unit_scale, unit_scale)
        graffiti_rgb = _graffiti_rgb()
        room_model.draw((1.0, 1.0, 1.0),
                        dynamic_colors={"rgb_graffiti": graffiti_rgb,
                                        "warm_ceiling_lights": WARM_BULB_RGB},
                        exclude_dynamic_tags=exclude_dynamic_tags)
        glPopMatrix()
        return

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


def _draw_scoreboard_text(text, x, y, z, color, scale=1.0):
    glColor3f(*color)
    glPushMatrix()
    glTranslatef(x, y, z)
    # Stroke glyphs live in the display plane, so yaw and perspective distort
    # the text together with the screen instead of leaving it screen-aligned.
    glScalef(-_scoreboard_text_x_scale * scale, _scoreboard_text_scale * scale,
             _scoreboard_text_scale * scale)
    for char in text:
        glutStrokeCharacter(GLUT_STROKE_ROMAN, ord(char))
    glPopMatrix()




def _stroke_text_width(text):
    return sum(glutStrokeWidth(GLUT_STROKE_ROMAN, ord(char)) for char in text)


def _draw_scoreboard_text_fit(text, center_x, y, z, color, max_width):
    width = _stroke_text_width(text) * _scoreboard_text_x_scale
    scale = min(1.0, max_width / max(width, 1e-6))
    x = center_x + width * scale * 0.5
    _draw_scoreboard_text(text, x, y, z, color, scale)

def _draw_scoreboard(game, compact=False):
    """Draw the live pinfall board and its ceiling suspension."""
    global _scoreboard_text_scale, _scoreboard_text_x_scale
    _scoreboard_text_scale = 0.00070 if compact else 0.0012
    _scoreboard_text_x_scale = (_scoreboard_text_scale * 0.5 / 0.28
                                if compact else _scoreboard_text_scale)
    left, right = -1.9, 1.9
    bottom, top, z = 3.52, 5.13, -5.72
    glDisable(GL_LIGHTING)
    glPushMatrix()
    if compact:
        # Seat the 4:3 board on the holder and turn it toward the opposite side.
        glTranslatef(BALL_HOLDER_X, 1.45, BALL_HOLDER_Z)
        glRotatef(-SCOREBOARD_LEFT_ANGLE, 0.0, 1.0, 0.0)
        # The source panel is 3.8 x 1.61. These axes make its rendered face
        # approximately 1.06 x 0.81 units, a 4:3 ratio.
        glScalef(0.28, 0.5, 0.5)
        glTranslatef(0.0, -4.325, 5.72)
        # Suspend the panel from the model ceiling while keeping it at the
        # low holder-side position. The rear supports meet the panel's top edge.
        ceiling_local_y = 4.325 + (CLUB_CEILING_Y - 1.45) / 0.5
        glColor3f(0.12, 0.14, 0.17)
        glBegin(GL_QUADS)
        for center_x in (-1.55, 1.55):
            x0, x1 = center_x - 0.07, center_x + 0.07
            y0, y1 = top - 0.18, ceiling_local_y
            z0, z1 = -5.70, -5.56
            glVertex3f(x0, y0, z0); glVertex3f(x1, y0, z0)
            glVertex3f(x1, y1, z0); glVertex3f(x0, y1, z0)
            glVertex3f(x0, y0, z1); glVertex3f(x0, y1, z1)
            glVertex3f(x1, y1, z1); glVertex3f(x1, y0, z1)
            glVertex3f(x0, y0, z0); glVertex3f(x0, y1, z0)
            glVertex3f(x0, y1, z1); glVertex3f(x0, y0, z1)
            glVertex3f(x1, y0, z0); glVertex3f(x1, y0, z1)
            glVertex3f(x1, y1, z1); glVertex3f(x1, y1, z0)
            glVertex3f(x0, y0, z0); glVertex3f(x0, y0, z1)
            glVertex3f(x1, y0, z1); glVertex3f(x1, y0, z0)
            glVertex3f(x0, y1, z0); glVertex3f(x1, y1, z0)
            glVertex3f(x1, y1, z1); glVertex3f(x0, y1, z1)
        glEnd()

    if not compact:
        # Use the original ceiling hanger for the procedural-scene scoreboard.
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
    _draw_scoreboard_text_fit(heading, 0.0, top - 0.28, z - 0.04,
                              heading_color, 3.25)
    # Reserve one full-width column for the player labels, then use the rest
    # for ten equal-width frame columns. This consumes the old empty gutter
    # while keeping every player row aligned to the same cell dimensions.
    grid_left, grid_right = left + 0.08, right - 0.08
    cell_width = (grid_right - grid_left) / 11
    for frame in range(10):
        # The display is viewed from the negative-Z side, where screen-left
        # maps to positive world X. Reverse world X so frames read 1 through 10.
        cell_x = grid_right - (frame + 1.5) * cell_width
        _draw_scoreboard_text_fit(str(frame + 1), cell_x, top - 0.61, z - 0.04,
                                  (1.0, 0.72, 0.82), cell_width * 0.76)

    glColor3f(0.95, 0.27, 0.53)
    glLineWidth(1.2)
    glBegin(GL_LINES)
    grid_bottom, grid_top = bottom + 0.35, top - 0.62
    grid_middle = (grid_bottom + grid_top) * 0.5
    for index in range(12):
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
        label_x = grid_right - cell_width * 0.5
        _draw_scoreboard_text_fit(f"P{player + 1}", label_x, row_y,
                                  z - 0.05, color, cell_width * 0.78)
        card = game.scorecards[player]
        cumulative = card.cumulative_scores
        for frame_index in range(10):
            cell_x = grid_right - (frame_index + 1.5) * cell_width
            marks = card.frame_symbol(frame_index)
            if marks:
                _draw_scoreboard_text_fit(marks, cell_x, row_y + 0.055,
                                          z - 0.05, color, cell_width * 0.86)
            frame_score = cumulative[frame_index]
            if frame_score is not None:
                score_text = str(frame_score)
                _draw_scoreboard_text_fit(score_text, cell_x, row_y - 0.105,
                                          z - 0.05, color, cell_width * 0.86)

    if game.player_count == 1:
        total = f"P1 TOTAL  {game.player_totals[0]}"
        _draw_scoreboard_text_fit(total, 0.0, bottom + 0.15, z - 0.04,
                                  (1.0, 0.82, 0.54), 3.25)
    else:
        for player, center_x in enumerate((1.12, -1.12)):
            total = f"P{player + 1} TOTAL {game.player_totals[player]}"
            _draw_scoreboard_text_fit(total, center_x, bottom + 0.15, z - 0.04,
                                      (1.0, 0.82, 0.54), 1.65)
    glLineWidth(1.0)
    glPopMatrix()
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


def _draw_ball(ball, ball_model, draw_contact_shadow=True):
    if draw_contact_shadow:
        _draw_contact_shadow(ball.x, ball.z, BALL_RADIUS * 1.8, BALL_RADIUS * 1.15, 0.35)
    glPushMatrix()
    glTranslatef(ball.x, BALL_RADIUS, ball.z)
    ball_model.draw((0.12, 0.20, 0.8))
    glPopMatrix()


def _draw_pins(pins, pin_model, draw_contact_shadows=True):
    for pin in pins:
        if pin.cleared:
            continue
        if draw_contact_shadows:
            _draw_contact_shadow(pin.x, pin.z, 0.16, 0.12, 0.26)
        glPushMatrix()
        glTranslatef(pin.x, 0.0, pin.z)
        glRotatef(math.degrees(pin.tilt_z), 0, 0, 1)
        glRotatef(math.degrees(pin.tilt_x), 1, 0, 0)
        # Keep the pin's white body and red bands readable under the alley's
        # dark shadow maps. Pins still cast shadows in the depth pass, but
        # their visible surface color is not multiplied by scene lighting.
        restore_lighting = bool(glIsEnabled(GL_LIGHTING))
        glDisable(GL_LIGHTING)
        pin_model.draw((0.92, 0.91, 0.84))
        if restore_lighting:
            glEnable(GL_LIGHTING)
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


def _look_at_matrix(eye, target, up):
    eye = np.asarray(eye, dtype=float)
    forward = np.asarray(target, dtype=float) - eye
    forward /= np.linalg.norm(forward)
    up = np.asarray(up, dtype=float)
    side = np.cross(forward, up)
    side /= np.linalg.norm(side)
    corrected_up = np.cross(side, forward)
    return np.array([
        [side[0], side[1], side[2], -np.dot(side, eye)],
        [corrected_up[0], corrected_up[1], corrected_up[2], -np.dot(corrected_up, eye)],
        [-forward[0], -forward[1], -forward[2], np.dot(forward, eye)],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=float)


def _perspective_matrix(fov_degrees, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov_degrees) * 0.5)
    return np.array([
        [f / aspect, 0.0, 0.0, 0.0],
        [0.0, f, 0.0, 0.0],
        [0.0, 0.0, (far + near) / (near - far),
         (2.0 * far * near) / (near - far)],
        [0.0, 0.0, -1.0, 0.0],
    ], dtype=float)


def _orthographic_matrix(left, right, bottom, top, near, far):
    return np.array([
        [2.0 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
        [0.0, 2.0 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
        [0.0, 0.0, -2.0 / (far - near), -(far + near) / (far - near)],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=float)


def _ensure_shadow_resources():
    global _shadow_attempted, _shadow_fbo, _shadow_texture, _static_shadow_texture
    global _shadow_depth_program, _shadow_mask_program
    if _shadow_attempted:
        return bool(_shadow_fbo and _shadow_texture and _static_shadow_texture
                    and _shadow_depth_program and _shadow_mask_program)
    _shadow_attempted = True
    shader_dir = Path(__file__).parent / "shaders"
    try:
        depth_vertex = (shader_dir / "shadow_depth.vert").read_text(encoding="utf-8-sig")
        depth_fragment = (shader_dir / "shadow_depth.frag").read_text(encoding="utf-8-sig")
        mask_vertex = (shader_dir / "shadow_mask.vert").read_text(encoding="utf-8-sig")
        mask_fragment = (shader_dir / "shadow_mask.frag").read_text(encoding="utf-8-sig")
        _shadow_depth_program = compileProgram(
            compileShader(depth_vertex, GL_VERTEX_SHADER),
            compileShader(depth_fragment, GL_FRAGMENT_SHADER))
        _shadow_mask_program = compileProgram(
            compileShader(mask_vertex, GL_VERTEX_SHADER),
            compileShader(mask_fragment, GL_FRAGMENT_SHADER))
        _shadow_texture = glGenTextures(1)
        _static_shadow_texture = glGenTextures(1)
        for texture in (_shadow_texture, _static_shadow_texture):
            glBindTexture(GL_TEXTURE_2D, texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT, _SHADOW_SIZE,
                         _SHADOW_SIZE, 0, GL_DEPTH_COMPONENT, GL_FLOAT, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)
            glTexParameterfv(GL_TEXTURE_2D, GL_TEXTURE_BORDER_COLOR,
                             (1.0, 1.0, 1.0, 1.0))
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE)
        _shadow_fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, _shadow_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                               GL_TEXTURE_2D, _static_shadow_texture, 0)
        glDrawBuffer(GL_NONE)
        glReadBuffer(GL_NONE)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDrawBuffer(GL_BACK)
        glReadBuffer(GL_BACK)
        glBindTexture(GL_TEXTURE_2D, 0)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"shadow framebuffer incomplete: {status}")
        return True
    except Exception as exc:
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glDrawBuffer(GL_BACK)
            glReadBuffer(GL_BACK)
            glBindTexture(GL_TEXTURE_2D, 0)
        except Exception:
            pass
        _shadow_fbo = 0
        print(f"Dynamic shadows unavailable; using bulb lighting only: {exc}")
        return False

def _draw_lane_shadow_geometry():
    glBegin(GL_QUADS)
    glVertex3f(-LANE_HALF_WIDTH, 0.0, LANE_START_Z)
    glVertex3f(LANE_HALF_WIDTH, 0.0, LANE_START_Z)
    glVertex3f(LANE_HALF_WIDTH, 0.0, PIN_DECK_Z + 2.0)
    glVertex3f(-LANE_HALF_WIDTH, 0.0, PIN_DECK_Z + 2.0)
    glEnd()


def _draw_shadow_casters(game, ball_model, pin_model, room_model,
                         draw_room=True, draw_objects=True,
                         exclude_room_dynamic_tags=(), draw_pins=True):
    if draw_room:
        _draw_room(room_model, exclude_dynamic_tags=exclude_room_dynamic_tags)
        if room_model is None:
            _draw_lane_shadow_geometry()
    if draw_objects:
        if draw_pins:
            _draw_pins(game.pins, pin_model, draw_contact_shadows=False)
        _draw_ball(game.ball, ball_model, draw_contact_shadow=False)


def _render_bulb_shadow(game, camera, ball_model, pin_model, room_model):
    if not _ensure_shadow_resources():
        return None
    # Use a top-down orthographic shadow volume covering the entire alley.
    # A perspective map from one ceiling bulb clipped the far third of the lane.
    light_eye = (0.0, _SHADOW_LIGHT_HEIGHT, _SHADOW_LIGHT_CENTER_Z)
    light_target = (0.0, 0.0, _SHADOW_LIGHT_CENTER_Z)
    light_view = _look_at_matrix(light_eye, light_target, (0.0, 0.0, -1.0))
    camera_view = _look_at_matrix(camera.position, camera.target, (0.0, 1.0, 0.0))
    light_projection = _orthographic_matrix(*_SHADOW_ORTHO,
                                            _SHADOW_NEAR, _SHADOW_FAR)
    camera_to_light = light_projection @ light_view @ np.linalg.inv(camera_view)
    viewport = np.asarray(glGetIntegerv(GL_VIEWPORT), dtype=int)

    glBindFramebuffer(GL_FRAMEBUFFER, _shadow_fbo)
    glViewport(0, 0, _SHADOW_SIZE, _SHADOW_SIZE)
    glDrawBuffer(GL_NONE)
    glReadBuffer(GL_NONE)
    glClearDepth(1.0)
    glClear(GL_DEPTH_BUFFER_BIT)
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LESS)
    glDepthMask(GL_TRUE)
    glDisable(GL_BLEND)
    glActiveTexture(GL_TEXTURE0)
    glUseProgram(_shadow_depth_program)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(*_SHADOW_ORTHO, _SHADOW_NEAR, _SHADOW_FAR)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    gluLookAt(light_eye[0], light_eye[1], light_eye[2],
              light_target[0], light_target[1], light_target[2],
              0.0, 0.0, -1.0)
    # Save room geometry separately so it can shadow the pins and ball without
    # letting the room mesh darken itself across its floors, walls, and ceiling.
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                           GL_TEXTURE_2D, _static_shadow_texture, 0)
    glClear(GL_DEPTH_BUFFER_BIT)
    _draw_shadow_casters(game, ball_model, pin_model, room_model,
                         draw_room=True, draw_objects=False,
                         exclude_room_dynamic_tags=ROOM_TAGS_EXCLUDED_FROM_SHADOWS)

    # Moving objects cast a second map that can safely shade the room and lane.
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                           GL_TEXTURE_2D, _shadow_texture, 0)
    glClear(GL_DEPTH_BUFFER_BIT)
    _draw_shadow_casters(game, ball_model, pin_model, room_model,
                         draw_room=False, draw_objects=True)
    glUseProgram(0)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glDrawBuffer(GL_BACK)
    glReadBuffer(GL_BACK)
    glViewport(int(viewport[0]), int(viewport[1]),
               int(viewport[2]), int(viewport[3]))
    glActiveTexture(GL_TEXTURE0)
    return camera_to_light

def _apply_one_shadow_map(game, texture, ball_model, pin_model, room_model,
                          draw_room, draw_objects,
                          exclude_room_dynamic_tags=(), receive_pins=True):
    glActiveTexture(GL_TEXTURE1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glActiveTexture(GL_TEXTURE0)
    glDepthFunc(GL_LEQUAL)
    glDepthMask(GL_FALSE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_ZERO, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_LIGHTING)
    _draw_shadow_casters(game, ball_model, pin_model, room_model,
                         draw_room=draw_room, draw_objects=draw_objects,
                         exclude_room_dynamic_tags=exclude_room_dynamic_tags,
                         draw_pins=receive_pins)
    glEnable(GL_LIGHTING)
    glDisable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDepthMask(GL_TRUE)
    glDepthFunc(GL_LESS)
    glUseProgram(0)
    glActiveTexture(GL_TEXTURE1)
    glBindTexture(GL_TEXTURE_2D, 0)
    glActiveTexture(GL_TEXTURE0)


def _apply_bulb_shadows(game, camera_to_light, ball_model, pin_model, room_model):
    if camera_to_light is None:
        return
    glUseProgram(_shadow_mask_program)
    matrix_location = glGetUniformLocation(_shadow_mask_program, "uCameraToLight")
    if matrix_location >= 0:
        glUniformMatrix4fv(matrix_location, 1, GL_TRUE,
                           np.asarray(camera_to_light, dtype=np.float32))
    sampler_location = glGetUniformLocation(_shadow_mask_program, "uShadowMap")
    if sampler_location >= 0:
        glUniform1i(sampler_location, 1)
    texel_location = glGetUniformLocation(_shadow_mask_program, "uShadowTexel")
    if texel_location >= 0:
        glUniform2f(texel_location, 1.0 / _SHADOW_SIZE, 1.0 / _SHADOW_SIZE)

    # Let the room's tables, chairs, holders, and other static geometry shadow
    # gameplay objects, then let gameplay objects shadow the static room too.
    _apply_one_shadow_map(game, _static_shadow_texture, ball_model, pin_model,
                          room_model, draw_room=False, draw_objects=True,
                          receive_pins=False)
    if room_model is not None:
        # The imported room is a combined mesh. A depth-biased receiver pass
        # suppresses each surface's own shadow while preserving shadows from
        # higher objects such as tables, chairs, and ball holders.
        glUseProgram(_shadow_mask_program)
        matrix_location = glGetUniformLocation(_shadow_mask_program, "uCameraToLight")
        if matrix_location >= 0:
            glUniformMatrix4fv(matrix_location, 1, GL_TRUE,
                               np.asarray(camera_to_light, dtype=np.float32))
        sampler_location = glGetUniformLocation(_shadow_mask_program, "uShadowMap")
        if sampler_location >= 0:
            glUniform1i(sampler_location, 1)
        texel_location = glGetUniformLocation(_shadow_mask_program, "uShadowTexel")
        if texel_location >= 0:
            glUniform2f(texel_location, 1.0 / _SHADOW_SIZE, 1.0 / _SHADOW_SIZE)
        _apply_one_shadow_map(game, _static_shadow_texture, ball_model, pin_model,
                              room_model, draw_room=True, draw_objects=False,
                              exclude_room_dynamic_tags=ROOM_TAGS_EXCLUDED_FROM_SHADOWS)
    glUseProgram(_shadow_mask_program)
    matrix_location = glGetUniformLocation(_shadow_mask_program, "uCameraToLight")
    if matrix_location >= 0:
        glUniformMatrix4fv(matrix_location, 1, GL_TRUE,
                           np.asarray(camera_to_light, dtype=np.float32))
    sampler_location = glGetUniformLocation(_shadow_mask_program, "uShadowMap")
    if sampler_location >= 0:
        glUniform1i(sampler_location, 1)
    texel_location = glGetUniformLocation(_shadow_mask_program, "uShadowTexel")
    if texel_location >= 0:
        glUniform2f(texel_location, 1.0 / _SHADOW_SIZE, 1.0 / _SHADOW_SIZE)
    _apply_one_shadow_map(game, _shadow_texture, ball_model, pin_model,
                          room_model, draw_room=True, draw_objects=True,
                          receive_pins=False,
                          exclude_room_dynamic_tags=ROOM_TAGS_EXCLUDED_FROM_SHADOWS)

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
    if game.player_count == 2:
        score_text = (f"P1 {game.player_totals[0]}  |  P2 {game.player_totals[1]}  |  "
                      f"PINS {game.standing_pins}/10  |  AIM {math.degrees(game.aim):+.1f} deg  |  "
                      f"POWER {game.power:.1f}  |  FPS {fps:.0f}")
    else:
        score_text = (f"SCORE {card.total_score}  |  PINS {game.standing_pins}/10  |  "
                      f"AIM {math.degrees(game.aim):+.1f} deg  |  POWER {game.power:.1f}  |  "
                      f"FPS {fps:.0f}")
    lines = [f"{game.player_count}P  |  TURN {game.turn_number}/{total_turns}  |  PLAYER {game.current_player + 1}  |  FRAME {frame}  |  {state.upper()}  |  CAMERA {camera.mode.upper()}",
             score_text,
             game.message,
             "ARROWS aim 0.1 deg / power    A,D position    LEFT DRAG aim & power, release to throw",
             "RIGHT DRAG look    SPACE throw / next roll    C cycle    1 follow 2 fixed 3 result 4 board    R reset    ESC title"]
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


def draw_scene(game, camera, ball_model, pin_model, room_model=None):
    fps = _measure_fps()
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(*camera.position, *camera.target, 0, 1, 0)
    # Fixed-function light positions are transformed by the active view matrix.
    for index, position in enumerate(BULB_LIGHT_POSITIONS):
        glLightfv(GL_LIGHT0 + index, GL_POSITION, position)
    if room_model is not None:
        _update_graffiti_lights()
    shadow_matrix = _render_bulb_shadow(game, camera, ball_model, pin_model, room_model)
    _draw_room(room_model)
    if room_model is None:
        _draw_alley_decorations(ball_model)
    if game.phase == "menu":
        if room_model is None:
            _draw_lane()
            _draw_guide_rails()
        _draw_pins(game.pins, pin_model)
        _draw_ball(game.ball, ball_model)
        _apply_bulb_shadows(game, shadow_matrix, ball_model, pin_model, room_model)
        if room_model is not None:
            _draw_graffiti_lane_spill()
        _draw_title_menu(game)
        glutSwapBuffers()
        return
    if room_model is None:
        _draw_scoreboard(game)
        _draw_lane()
        _draw_guide_rails()
    else:
        _draw_scoreboard(game, compact=True)
    _draw_pins(game.pins, pin_model)
    _draw_ball(game.ball, ball_model)
    _apply_bulb_shadows(game, shadow_matrix, ball_model, pin_model, room_model)
    if room_model is not None:
        _draw_graffiti_lane_spill()
    if game.phase == "aiming":
        _draw_trajectory(game.trajectory())
    _draw_hud(game, camera, fps)
    glutSwapBuffers()















