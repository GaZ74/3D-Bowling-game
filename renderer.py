"""OpenGL drawing. Keep game rules out of this module."""

import math
from pathlib import Path
from OpenGL.GL import *
from OpenGL.GLU import gluLookAt, gluOrtho2D
from OpenGL.GL.shaders import compileProgram, compileShader
from OpenGL.GLUT import (glutSolidSphere, glutSolidCone, glutBitmapCharacter,
                         glutSwapBuffers, GLUT_BITMAP_HELVETICA_18)
from PIL import Image

from config import (BALL_RADIUS, LANE_HALF_WIDTH, LANE_START_Z, PIN_DECK_Z,
                    WINDOW_HEIGHT, WINDOW_WIDTH)

_lane_program = None
_shader_attempted = False
_textures = {}
_ASSET_DIR = Path(__file__).parent / "assets"
_ROOM_HALF_WIDTH = 5.5
_ROOM_FRONT_Z = -10.0
_ROOM_BACK_Z = 11.0
_ROOM_HEIGHT = 8.0


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
    program = _get_lane_program()
    if program:
        glUseProgram(program)
    glColor3f(1.0, 1.0, 1.0) if program else glColor3f(0.58, 0.34, 0.16)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0)
    glVertex3f(-LANE_HALF_WIDTH, 0, LANE_START_Z)
    glTexCoord2f(1, 0)
    glVertex3f(LANE_HALF_WIDTH, 0, LANE_START_Z)
    glTexCoord2f(1, 1)
    glVertex3f(LANE_HALF_WIDTH, 0, PIN_DECK_Z + 2.0)
    glTexCoord2f(0, 1)
    glVertex3f(-LANE_HALF_WIDTH, 0, PIN_DECK_Z + 2.0)
    glEnd()
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
    glColor3f(0.88, 0.77, 0.58)
    glBegin(GL_LINES)
    for x in (-0.85, -0.42, 0.0, 0.42, 0.85):
        glVertex3f(x, 0.01, LANE_START_Z)
        glVertex3f(x, 0.01, PIN_DECK_Z + 2.0)
    glEnd()


def _draw_ball(ball, ball_model):
    glPushMatrix()
    glTranslatef(ball.x, BALL_RADIUS, ball.z)
    ball_model.draw((0.12, 0.20, 0.8))
    glPopMatrix()


def _draw_pins(pins, pin_model):
    for pin in pins:
        glPushMatrix()
        glTranslatef(pin.x, 0.16 if pin.down else 0.3, pin.z)
        if pin.down:
            glRotatef(80, 1, 0, 0)
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


def _draw_hud(game, camera):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_LIGHTING)
    glColor3f(1, 1, 1)
    lines = [game.message, f"Aim {math.degrees(game.aim):.0f} deg | Power {game.power:.1f} | Start {game.start_x:+.2f}",
             f"Standing pins {game.standing_pins}/10 | Camera {camera.mode}",
             "Mouse drag/release throw | A/D position | arrows aim/power | Space throw | C camera | R reset"]
    for row, line in enumerate(lines):
        glRasterPos2i(24, WINDOW_HEIGHT - 34 - row * 26)
        for char in line:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    glEnable(GL_LIGHTING)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_scene(game, camera, ball_model, pin_model):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(*camera.position, *camera.target, 0, 1, 0)
    _draw_room()
    _draw_lane()
    _draw_pins(game.pins, pin_model)
    _draw_ball(game.ball, ball_model)
    if game.phase == "aiming":
        _draw_trajectory(game.trajectory())
    _draw_hud(game, camera)
    glutSwapBuffers()
