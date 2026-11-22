"""Fixed-step bowling motion, pin contacts, and side-guide routing."""

import math

from config import (
    BALL_PIN_IMPULSE,
    BALL_RADIUS,
    BALL_START_Z,
    BALL_STOP_Z,
    GUIDE_ALIGNMENT_LENGTH,
    GUIDE_CENTER_X,
    GUIDE_PATH_SAMPLES,
    GUIDE_RESET_X,
    GUIDE_TURN_RADIUS,
    GUIDE_TURN_START_Z,
    LANE_BALL_CENTER_LIMIT,
    PIN_ANGULAR_DAMPING,
    PIN_FALL_ANGLE,
    PIN_LINEAR_DAMPING,
    PIN_MAX_TILT,
    PIN_PIN_RESTITUTION,
    PIN_RADIUS,
    PIN_STOP_SPEED,
    PIN_UPRIGHT_STIFFNESS,
    RESET_ZONE_Z,
)


def predict_trajectory(aim_angle: float, speed: float, start_x: float = 0.0,
                       samples: int = 36):
    """Return a preview that follows the side guide after a wide aim."""
    points = []
    duration = max(0.0, (BALL_STOP_Z - BALL_START_Z) / max(speed, 0.1))
    previous_x = start_x
    for index in range(samples + 1):
        t = duration * index / samples
        x = start_x + math.sin(aim_angle) * speed * t
        z = BALL_START_Z + math.cos(aim_angle) * speed * t
        if abs(x) >= LANE_BALL_CENTER_LIMIT:
            side = 1.0 if x >= 0 else -1.0
            fraction = (side * LANE_BALL_CENTER_LIMIT - previous_x) / (x - previous_x)
            fraction = max(0.0, min(1.0, fraction))
            z = points[-1][2] + (z - points[-1][2]) * fraction if points else z
            x = side * LANE_BALL_CENTER_LIMIT
            points.append((x, 0.08, z))
            route, _lengths = make_guide_curve(side, x, z)
            points.extend((route_x, 0.08, route_z) for route_x, route_z in route[1:])
            break
        points.append((x, 0.08, z))
        previous_x = x
    return points


def _point_segment_distance(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    length_sq = dx * dx + dz * dz
    if length_sq <= 1e-12:
        return math.hypot(px - ax, pz - az), ax, az
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / length_sq))
    cx, cz = ax + t * dx, az + t * dz
    return math.hypot(px - cx, pz - cz), cx, cz


def make_guide_curve(side: int, start_x=None, start_z=None, samples=GUIDE_PATH_SAMPLES):
    """Sample a smooth bypass curve from a lane edge to its reset pocket."""
    sign = 1 if side >= 0 else -1
    if start_x is None:
        start_x = sign * LANE_BALL_CENTER_LIMIT
    if start_z is None:
        start_z = BALL_START_Z
    points = []
    align_steps = max(12, samples // 6)
    target_x = sign * GUIDE_CENTER_X
    for index in range(align_steps + 1):
        t = index / align_steps
        smooth = t * t * (3.0 - 2.0 * t)
        points.append((start_x + (target_x - start_x) * smooth,
                       start_z + GUIDE_ALIGNMENT_LENGTH * t))

    turn_z = max(GUIDE_TURN_START_Z,
                 start_z + GUIDE_ALIGNMENT_LENGTH + 0.45)
    if turn_z > points[-1][1]:
        straight_steps = max(2, int((turn_z - points[-1][1]) / 0.14))
        for index in range(1, straight_steps + 1):
            t = index / straight_steps
            points.append((target_x,
                           points[align_steps][1] + (turn_z - points[align_steps][1]) * t))

    # A quarter-circle with a radius equal to the ball radius turns the
    # bypass inward after it has cleared the rear of the pin formation.
    radius = GUIDE_TURN_RADIUS
    arc_steps = max(12, samples // 8)
    arc_center_x = sign * GUIDE_RESET_X
    for index in range(1, arc_steps + 1):
        angle = (math.pi * 0.5) * index / arc_steps
        points.append((arc_center_x + sign * radius * math.cos(angle),
                       turn_z + radius * math.sin(angle)))

    end_z = max(RESET_ZONE_Z, turn_z + radius + 0.95)
    tail_start_z = points[-1][1]
    straight_steps = max(2, int((end_z - points[-1][1]) / 0.14))
    for index in range(1, straight_steps + 1):
        t = index / straight_steps
        points.append((arc_center_x,
                       tail_start_z + (end_z - tail_start_z) * t))

    cumulative = [0.0]
    for index in range(1, len(points)):
        cumulative.append(cumulative[-1] + math.hypot(
            points[index][0] - points[index - 1][0],
            points[index][1] - points[index - 1][1]))
    return points, cumulative


def _enter_guide(ball, side, crossing_x, crossing_z):
    ball.on_guide = True
    ball.guide_side = side
    ball.x, ball.z = crossing_x, crossing_z
    ball.guide_points, ball.guide_lengths = make_guide_curve(
        side, crossing_x, crossing_z)
    ball.guide_distance = 0.0


def _advance_guide(ball, dt):
    points, lengths = ball.guide_points, ball.guide_lengths
    if not points or not lengths or lengths[-1] <= 1e-8:
        ball.reached_reset = True
        return
    speed = max(0.0, math.hypot(ball.vx, ball.vz))
    ball.guide_distance = min(lengths[-1], ball.guide_distance + speed * dt)
    index = 1
    while index < len(lengths) - 1 and lengths[index] < ball.guide_distance:
        index += 1
    before, after = lengths[index - 1], lengths[index]
    fraction = 0.0 if after <= before else (ball.guide_distance - before) / (after - before)
    ax, az = points[index - 1]
    bx, bz = points[index]
    ball.x = ax + (bx - ax) * fraction
    ball.z = az + (bz - az) * fraction
    segment_length = max(after - before, 1e-8)
    ball.vx = (bx - ax) / segment_length * speed
    ball.vz = (bz - az) / segment_length * speed
    if ball.guide_distance >= lengths[-1]:
        ball.reached_reset = True
        ball.vx = ball.vz = 0.0


def _apply_pin_impulse(pin, nx, nz, impulse):
    pin.vx += nx * impulse
    pin.vz += nz * impulse
    # A forward push tips the pin forward around X; a side push tips around Z.
    pin.omega_x += nz * impulse * 0.85
    pin.omega_z -= nx * impulse * 0.85


def _hit_pins_with_ball(ball, pins, ax, az, bx, bz):
    speed = math.hypot(ball.vx, ball.vz)
    if speed <= 1e-6:
        return
    for pin in pins:
        if pin.ball_contacted:
            continue
        distance, cx, cz = _point_segment_distance(pin.x, pin.z, ax, az, bx, bz)
        if distance > BALL_RADIUS + PIN_RADIUS:
            continue
        dx, dz = pin.x - cx, pin.z - cz
        magnitude = math.hypot(dx, dz)
        if magnitude <= 1e-8:
            nx, nz = ball.vx / speed, ball.vz / speed
        else:
            nx, nz = dx / magnitude, dz / magnitude
        _apply_pin_impulse(pin, nx, nz, speed * BALL_PIN_IMPULSE)
        pin.ball_contacted = True


def _resolve_pin_pairs(pins):
    count = len(pins)
    for i in range(count):
        a = pins[i]
        for j in range(i + 1, count):
            b = pins[j]
            dx, dz = b.x - a.x, b.z - a.z
            distance = math.hypot(dx, dz)
            min_distance = PIN_RADIUS * (2.0 if not (a.down or b.down) else 2.4)
            if distance >= min_distance:
                continue
            if distance <= 1e-8:
                nx, nz, distance = 1.0, 0.0, 1e-8
            else:
                nx, nz = dx / distance, dz / distance
            overlap = min_distance - distance
            a.x -= nx * overlap * 0.5
            a.z -= nz * overlap * 0.5
            b.x += nx * overlap * 0.5
            b.z += nz * overlap * 0.5

            relative_speed = (b.vx - a.vx) * nx + (b.vz - a.vz) * nz
            if relative_speed >= 0:
                continue
            impulse = -(1.0 + PIN_PIN_RESTITUTION) * relative_speed * 0.5
            a.vx -= impulse * nx
            a.vz -= impulse * nz
            b.vx += impulse * nx
            b.vz += impulse * nz
            _apply_pin_impulse(a, -nx, -nz, impulse * 1.4)
            _apply_pin_impulse(b, nx, nz, impulse * 1.4)


def _step_pins(pins, dt):
    linear_decay = math.exp(-PIN_LINEAR_DAMPING * dt)
    angular_decay = math.exp(-PIN_ANGULAR_DAMPING * dt)
    for pin in pins:
        pin.x += pin.vx * dt
        pin.z += pin.vz * dt
        pin.vx *= linear_decay
        pin.vz *= linear_decay
        if math.hypot(pin.vx, pin.vz) < PIN_STOP_SPEED:
            pin.vx = pin.vz = 0.0

        if not pin.down:
            pin.omega_x -= pin.tilt_x * PIN_UPRIGHT_STIFFNESS * dt
            pin.omega_z -= pin.tilt_z * PIN_UPRIGHT_STIFFNESS * dt
        pin.tilt_x += pin.omega_x * dt
        pin.tilt_z += pin.omega_z * dt
        pin.omega_x *= angular_decay
        pin.omega_z *= angular_decay
        tilt = math.hypot(pin.tilt_x, pin.tilt_z)
        if tilt >= PIN_FALL_ANGLE:
            pin.down = True
        if tilt > PIN_MAX_TILT:
            scale = PIN_MAX_TILT / tilt
            pin.tilt_x *= scale
            pin.tilt_z *= scale
            pin.omega_x *= 0.25
            pin.omega_z *= 0.25
        if pin.down and math.hypot(pin.omega_x, pin.omega_z) < 0.04:
            pin.omega_x = pin.omega_z = 0.0
        elif not pin.down and math.hypot(pin.omega_x, pin.omega_z) < 0.025:
            pin.omega_x = pin.omega_z = 0.0
            pin.tilt_x = pin.tilt_z = 0.0


def step_physics(ball, pins, dt):
    """Advance one small physics step; return True when the ball reaches reset."""
    if ball.reached_reset:
        _step_pins(pins, dt)
        _resolve_pin_pairs(pins)
        return True

    if ball.on_guide:
        _advance_guide(ball, dt)
    else:
        ax, az = ball.x, ball.z
        bx = ax + ball.vx * dt
        bz = az + ball.vz * dt
        side = 1 if bx > LANE_BALL_CENTER_LIMIT else -1 if bx < -LANE_BALL_CENTER_LIMIT else 0
        if side:
            boundary_x = side * LANE_BALL_CENTER_LIMIT
            dx = bx - ax
            fraction = 0.0 if abs(dx) < 1e-9 else (boundary_x - ax) / dx
            fraction = max(0.0, min(1.0, fraction))
            crossing_z = az + (bz - az) * fraction
            _hit_pins_with_ball(ball, pins, ax, az, boundary_x, crossing_z)
            _enter_guide(ball, side, boundary_x, crossing_z)
            _advance_guide(ball, dt * (1.0 - fraction))
        else:
            _hit_pins_with_ball(ball, pins, ax, az, bx, bz)
            ball.x, ball.z = bx, bz

        if ball.z >= BALL_STOP_Z:
            ball.z = BALL_STOP_Z
            ball.vx = ball.vz = 0.0
            ball.reached_reset = True

    _step_pins(pins, dt)
    _resolve_pin_pairs(pins)
    return ball.reached_reset
