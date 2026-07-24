"""Minimal 3D math: vectors as 3-tuples, matrices as row-major 16-float lists.

Everything here is dependency-free so the asset build runs on a bare Python 3.
Only rigid transforms (rotation + translation) are used for node placement so
the resulting glTF nodes stay cleanly decomposable in any DCC tool.
"""

import math

# ---------------------------------------------------------------- vectors


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def mad(a, b, s):
    """a + b * s"""
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def norm(a):
    l = length(a)
    if l < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def lerp(a, b, t):
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def bezier3(p0, p1, p2, t):
    """Quadratic bezier."""
    u = 1.0 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
        u * u * p0[2] + 2 * u * t * p1[2] + t * t * p2[2],
    )


def bezier4(p0, p1, p2, p3, t):
    """Cubic bezier."""
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
        a * p0[2] + b * p1[2] + c * p2[2] + d * p3[2],
    )


# ---------------------------------------------------------------- matrices
# Row-major: m[row * 4 + col]. Point transform is m * v (column vector).

IDENTITY = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]


def mat_mul(a, b):
    out = [0.0] * 16
    for r in range(4):
        for c in range(4):
            out[r * 4 + c] = (
                a[r * 4 + 0] * b[0 * 4 + c]
                + a[r * 4 + 1] * b[1 * 4 + c]
                + a[r * 4 + 2] * b[2 * 4 + c]
                + a[r * 4 + 3] * b[3 * 4 + c]
            )
    return out


def mat_from_basis(x_axis, y_axis, z_axis, origin=(0.0, 0.0, 0.0)):
    """Basis vectors become the matrix columns."""
    return [
        x_axis[0], y_axis[0], z_axis[0], origin[0],
        x_axis[1], y_axis[1], z_axis[1], origin[1],
        x_axis[2], y_axis[2], z_axis[2], origin[2],
        0.0, 0.0, 0.0, 1.0,
    ]


def translate(t):
    return [
        1.0, 0.0, 0.0, t[0],
        0.0, 1.0, 0.0, t[1],
        0.0, 0.0, 1.0, t[2],
        0.0, 0.0, 0.0, 1.0,
    ]


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, c, -s, 0.0,
        0.0, s, c, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [
        c, 0.0, s, 0.0,
        0.0, 1.0, 0.0, 0.0,
        -s, 0.0, c, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [
        c, -s, 0.0, 0.0,
        s, c, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def rot_axis(axis, angle):
    x, y, z = norm(axis)
    c, s = math.cos(angle), math.sin(angle)
    k = 1.0 - c
    return [
        c + x * x * k, x * y * k - z * s, x * z * k + y * s, 0.0,
        y * x * k + z * s, c + y * y * k, y * z * k - x * s, 0.0,
        z * x * k - y * s, z * y * k + x * s, c + z * z * k, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def scale(s):
    if isinstance(s, (int, float)):
        s = (s, s, s)
    return [
        s[0], 0.0, 0.0, 0.0,
        0.0, s[1], 0.0, 0.0,
        0.0, 0.0, s[2], 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def xform_point(m, p):
    return (
        m[0] * p[0] + m[1] * p[1] + m[2] * p[2] + m[3],
        m[4] * p[0] + m[5] * p[1] + m[6] * p[2] + m[7],
        m[8] * p[0] + m[9] * p[1] + m[10] * p[2] + m[11],
    )


def xform_dir(m, v):
    return (
        m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
        m[4] * v[0] + m[5] * v[1] + m[6] * v[2],
        m[8] * v[0] + m[9] * v[1] + m[10] * v[2],
    )


def rigid_inverse(m):
    """Inverse of a rotation+translation matrix (no scale/shear)."""
    r = [
        m[0], m[4], m[8],
        m[1], m[5], m[9],
        m[2], m[6], m[10],
    ]
    t = (m[3], m[7], m[11])
    ti = (
        -(r[0] * t[0] + r[1] * t[1] + r[2] * t[2]),
        -(r[3] * t[0] + r[4] * t[1] + r[5] * t[2]),
        -(r[6] * t[0] + r[7] * t[1] + r[8] * t[2]),
    )
    return [
        r[0], r[1], r[2], ti[0],
        r[3], r[4], r[5], ti[1],
        r[6], r[7], r[8], ti[2],
        0.0, 0.0, 0.0, 1.0,
    ]


def to_gltf(m):
    """glTF wants column-major floats."""
    return [
        m[0], m[4], m[8], m[12],
        m[1], m[5], m[9], m[13],
        m[2], m[6], m[10], m[14],
        m[3], m[7], m[11], m[15],
    ]


def look_basis(forward, up_hint=(0.0, 1.0, 0.0), origin=(0.0, 0.0, 0.0)):
    """Build an orthonormal frame whose local +Z is `forward`."""
    z = norm(forward)
    if abs(dot(z, norm(up_hint))) > 0.999:
        up_hint = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 0.0, 1.0)
    x = norm(cross(up_hint, z))
    y = cross(z, x)
    return mat_from_basis(x, y, z, origin)


def parallel_frames(points, up_hint=(0.0, 1.0, 0.0)):
    """Parallel-transport frames along a polyline: minimal twist, stable rings."""
    n = len(points)
    tangents = []
    for i in range(n):
        if i == 0:
            t = sub(points[1], points[0])
        elif i == n - 1:
            t = sub(points[-1], points[-2])
        else:
            t = sub(points[i + 1], points[i - 1])
        tangents.append(norm(t))

    frames = []
    ref = norm(up_hint)
    if abs(dot(ref, tangents[0])) > 0.99:
        ref = (1.0, 0.0, 0.0)
    x = norm(cross(ref, tangents[0]))
    y = cross(tangents[0], x)
    frames.append((x, y, tangents[0]))
    for i in range(1, n):
        t_prev = tangents[i - 1]
        t = tangents[i]
        axis = cross(t_prev, t)
        if length(axis) < 1e-9:
            x_new, y_new = x, y
        else:
            ang = math.acos(max(-1.0, min(1.0, dot(t_prev, t))))
            r = rot_axis(axis, ang)
            x_new = norm(xform_dir(r, x))
            y_new = norm(xform_dir(r, y))
        # re-orthogonalise against drift
        x_new = norm(sub(x_new, mul(t, dot(x_new, t))))
        y_new = cross(t, x_new)
        frames.append((x_new, y_new, t))
        x, y = x_new, y_new
    return frames
