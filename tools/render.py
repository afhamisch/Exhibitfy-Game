"""A small software rasteriser used to preview the asset.

It exists so the build can be verified without a DCC app: z-buffered
triangles, perspective-correct UVs, three-point lighting, optional wireframe
overlay for checking edge loops.
"""

import math

from . import vec
from .gltf import build_primitive
from .imaging import Canvas, linear_to_srgb, srgb_to_linear


class Camera:
    def __init__(self, eye=(0, 0, 0), target=(0, 0, -1), up=(0, 1, 0),
                 fov_deg=58.0, near=0.01):
        self.eye = eye
        self.fov = math.radians(fov_deg)
        self.near = near
        z = vec.norm(vec.sub(eye, target))       # camera looks down -Z
        x = vec.norm(vec.cross(up, z))
        y = vec.cross(z, x)
        self.view = vec.rigid_inverse(vec.mat_from_basis(x, y, z, eye))


DEFAULT_LIGHTS = [
    # (direction towards the light, colour, intensity)
    ((-0.35, 0.72, 0.60), (1.0, 0.96, 0.90), 1.15),   # key, over left shoulder
    ((0.75, 0.10, 0.35), (0.55, 0.66, 0.85), 0.45),   # cool fill from the right
    ((0.05, -0.35, -0.85), (1.0, 0.72, 0.45), 0.35),  # warm bounce from below
]

AMBIENT_SKY = (0.30, 0.34, 0.42)
AMBIENT_GROUND = (0.16, 0.13, 0.11)


def render(scene, cam, width=960, height=640, background=(0.055, 0.06, 0.075),
           lights=None, wireframe=False, exposure=1.0, ambient_scale=1.0):
    lights = lights or DEFAULT_LIGHTS
    img = Canvas(width, height, background)
    zbuf = [1e30] * (width * height)
    aspect = width / height
    focal = 1.0 / math.tan(cam.fov * 0.5)
    near = cam.near

    tex_cache = {}

    def sample_tex(name, u, v):
        c = scene.images.get(name)
        if c is None:
            return (1.0, 1.0, 1.0)
        k = (name, round(u, 4), round(v, 4))
        got = tex_cache.get(k)
        if got is None:
            got = c.sample(u, v)
            if len(tex_cache) < 400000:
                tex_cache[k] = got
        return got

    def project(p):
        """View-space point -> (screen x, screen y, view z)."""
        x = p[0] * focal / aspect
        y = p[1] * focal
        w = -p[2]
        return ((x / w * 0.5 + 0.5) * width, (0.5 - y / w * 0.5) * height, w)

    for world, mesh in scene.flatten():
        mat = scene.materials.get(mesh.material)
        pos, nrm, uvs, tris = build_primitive(mesh)
        vp = [vec.xform_point(cam.view, vec.xform_point(world, p)) for p in pos]
        vn = [vec.norm(vec.xform_dir(cam.view, vec.xform_dir(world, n)))
              for n in nrm]

        base_factor = mat.base_color[:3] if mat else (0.8, 0.8, 0.8)
        metal = mat.metallic if mat else 0.0
        rough = mat.roughness if mat else 0.6
        btex = mat.base_tex if mat else None
        mrtex = mat.mr_tex if mat else None

        for tri in tris:
            poly = [(vp[i], vn[i], uvs[i]) for i in tri]
            # near-plane clip so geometry behind the camera doesn't wrap around
            clipped = []
            n = len(poly)
            for i in range(n):
                a = poly[i]
                b = poly[(i + 1) % n]
                da = -a[0][2] - near
                db = -b[0][2] - near
                if da >= 0:
                    clipped.append(a)
                if (da >= 0) != (db >= 0):
                    t = da / (da - db)
                    clipped.append((
                        vec.lerp(a[0], b[0], t),
                        vec.norm(vec.lerp(a[1], b[1], t)),
                        (a[2][0] + (b[2][0] - a[2][0]) * t,
                         a[2][1] + (b[2][1] - a[2][1]) * t),
                    ))
            if len(clipped) < 3:
                continue

            for k in range(1, len(clipped) - 1):
                v0, v1, v2 = clipped[0], clipped[k], clipped[k + 1]
                s0 = project(v0[0])
                s1 = project(v1[0])
                s2 = project(v2[0])
                area = (s1[0] - s0[0]) * (s2[1] - s0[1]) - \
                       (s2[0] - s0[0]) * (s1[1] - s0[1])
                if abs(area) < 1e-9:
                    continue
                x0 = max(0, int(math.floor(min(s0[0], s1[0], s2[0]))))
                x1 = min(width - 1, int(math.ceil(max(s0[0], s1[0], s2[0]))))
                y0 = max(0, int(math.floor(min(s0[1], s1[1], s2[1]))))
                y1 = min(height - 1, int(math.ceil(max(s0[1], s1[1], s2[1]))))
                if x1 < x0 or y1 < y0:
                    continue
                iw0, iw1, iw2 = 1.0 / s0[2], 1.0 / s1[2], 1.0 / s2[2]
                inv_area = 1.0 / area
                for py in range(y0, y1 + 1):
                    yc = py + 0.5
                    row = py * width
                    for px in range(x0, x1 + 1):
                        xc = px + 0.5
                        w0 = ((s1[0] - xc) * (s2[1] - yc) -
                              (s2[0] - xc) * (s1[1] - yc)) * inv_area
                        if w0 < 0:
                            continue
                        w1 = ((s2[0] - xc) * (s0[1] - yc) -
                              (s0[0] - xc) * (s2[1] - yc)) * inv_area
                        if w1 < 0:
                            continue
                        w2 = 1.0 - w0 - w1
                        if w2 < 0:
                            continue
                        iw = w0 * iw0 + w1 * iw1 + w2 * iw2
                        z = 1.0 / iw
                        di = row + px
                        if z >= zbuf[di]:
                            continue
                        zbuf[di] = z
                        b0 = w0 * iw0 / iw
                        b1 = w1 * iw1 / iw
                        b2 = w2 * iw2 / iw
                        nx = v0[1][0] * b0 + v1[1][0] * b1 + v2[1][0] * b2
                        ny = v0[1][1] * b0 + v1[1][1] * b1 + v2[1][1] * b2
                        nz = v0[1][2] * b0 + v1[1][2] * b1 + v2[1][2] * b2
                        nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                        nx, ny, nz = nx / nl, ny / nl, nz / nl
                        # rasteriser sees both faces; flip toward the eye
                        if nz < 0.0:
                            nx, ny, nz = -nx, -ny, -nz

                        albedo = base_factor
                        if btex:
                            u = v0[2][0] * b0 + v1[2][0] * b1 + v2[2][0] * b2
                            v = v0[2][1] * b0 + v1[2][1] * b1 + v2[2][1] * b2
                            t = srgb_to_linear(sample_tex(btex, u, v))
                            albedo = (albedo[0] * t[0], albedo[1] * t[1],
                                      albedo[2] * t[2])
                            if mrtex:
                                mr = sample_tex(mrtex, u, v)
                                rough_p = max(0.04, min(1.0, rough * mr[1]))
                                metal_p = max(0.0, min(1.0, metal * mr[2]))
                            else:
                                rough_p, metal_p = rough, metal
                        else:
                            rough_p, metal_p = rough, metal

                        # hemispheric ambient
                        hemi = 0.5 + 0.5 * ny
                        amb = (
                            (AMBIENT_GROUND[0] + (AMBIENT_SKY[0] - AMBIENT_GROUND[0]) * hemi) * ambient_scale,
                            (AMBIENT_GROUND[1] + (AMBIENT_SKY[1] - AMBIENT_GROUND[1]) * hemi) * ambient_scale,
                            (AMBIENT_GROUND[2] + (AMBIENT_SKY[2] - AMBIENT_GROUND[2]) * hemi) * ambient_scale,
                        )
                        diff_k = 1.0 - metal_p
                        r = albedo[0] * amb[0] * diff_k
                        g = albedo[1] * amb[1] * diff_k
                        b = albedo[2] * amb[2] * diff_k
                        spec_col = (
                            0.04 + (albedo[0] - 0.04) * metal_p,
                            0.04 + (albedo[1] - 0.04) * metal_p,
                            0.04 + (albedo[2] - 0.04) * metal_p,
                        )
                        shininess = 2.0 / max(1e-3, rough_p ** 4) - 2.0
                        shininess = min(shininess, 4096.0)
                        for (ld, lc, li) in lights:
                            ndl = nx * ld[0] + ny * ld[1] + nz * ld[2]
                            if ndl <= 0.0:
                                continue
                            r += albedo[0] * lc[0] * li * ndl * diff_k
                            g += albedo[1] * lc[1] * li * ndl * diff_k
                            b += albedo[2] * lc[2] * li * ndl * diff_k
                            # half vector against the view direction (0,0,1)
                            hx, hy, hz = ld[0], ld[1], ld[2] + 1.0
                            hl = math.sqrt(hx * hx + hy * hy + hz * hz) or 1.0
                            ndh = (nx * hx + ny * hy + nz * hz) / hl
                            if ndh > 0.0:
                                s = (ndh ** shininess) * li * (1.0 - rough_p * 0.75)
                                r += spec_col[0] * lc[0] * s
                                g += spec_col[1] * lc[1] * s
                                b += spec_col[2] * lc[2] * s
                        # cheap environment reflection so metals don't read
                        # as black -- stands in for the engine's IBL probe
                        if metal_p > 0.01 or rough_p < 0.5:
                            rx_ = 2.0 * nz * nx
                            ry_ = 2.0 * nz * ny
                            rz_ = 2.0 * nz * nz - 1.0
                            hemi_r = 0.5 + 0.5 * ry_
                            env = (
                                AMBIENT_GROUND[0] + (AMBIENT_SKY[0] * 2.4 - AMBIENT_GROUND[0]) * hemi_r,
                                AMBIENT_GROUND[1] + (AMBIENT_SKY[1] * 2.4 - AMBIENT_GROUND[1]) * hemi_r,
                                AMBIENT_GROUND[2] + (AMBIENT_SKY[2] * 2.4 - AMBIENT_GROUND[2]) * hemi_r,
                            )
                            sun = max(0.0, rx_ * -0.35 + ry_ * 0.72 + rz_ * 0.60)
                            sun = sun ** 24 * 3.0
                            k = (1.0 - rough_p * 0.8)
                            r += spec_col[0] * (env[0] + sun) * k
                            g += spec_col[1] * (env[1] + sun) * k
                            b += spec_col[2] * (env[2] + sun) * k

                        # rim light for silhouette separation
                        rim = (1.0 - nz) ** 3 * 0.35
                        r += rim * 0.55
                        g += rim * 0.62
                        b += rim * 0.78

                        i3 = di * 3
                        img.px[i3] = r * exposure
                        img.px[i3 + 1] = g * exposure
                        img.px[i3 + 2] = b * exposure

    # tone map linear -> sRGB
    for i in range(len(img.px)):
        img.px[i] = img.px[i] / (1.0 + img.px[i] * 0.6)
    for i in range(0, len(img.px), 3):
        c = linear_to_srgb((img.px[i], img.px[i + 1], img.px[i + 2]))
        img.px[i], img.px[i + 1], img.px[i + 2] = c

    if wireframe:
        _draw_wire(scene, cam, img, zbuf, width, height, focal, aspect, near)
    return img


def _draw_wire(scene, cam, img, zbuf, width, height, focal, aspect, near,
               color=(0.06, 0.95, 0.75)):
    """Depth-tested quad wireframe so edge loops are legible."""
    def project(p):
        w = -p[2]
        x = p[0] * focal / aspect
        y = p[1] * focal
        return ((x / w * 0.5 + 0.5) * width, (0.5 - y / w * 0.5) * height, w)

    drawn = set()
    for world, mesh in scene.flatten():
        wpos = [vec.xform_point(cam.view, vec.xform_point(world, p))
                for p in mesh.pos]
        for idx, _grp in mesh.faces:
            n = len(idx)
            for i in range(n):
                a = idx[i]
                b = idx[(i + 1) % n]
                key = (id(mesh), min(a, b), max(a, b))
                if key in drawn:
                    continue
                drawn.add(key)
                pa, pb = wpos[a], wpos[b]
                if -pa[2] < near or -pb[2] < near:
                    continue
                sa = project(pa)
                sb = project(pb)
                steps = int(max(abs(sb[0] - sa[0]), abs(sb[1] - sa[1]))) + 1
                if steps > 400:
                    continue
                for s in range(steps + 1):
                    t = s / steps
                    x = sa[0] + (sb[0] - sa[0]) * t
                    y = sa[1] + (sb[1] - sa[1]) * t
                    z = sa[2] + (sb[2] - sa[2]) * t
                    xi, yi = int(x), int(y)
                    if 0 <= xi < width and 0 <= yi < height:
                        if z <= zbuf[yi * width + xi] * 1.004:
                            img.blend(xi, yi, color, 0.85)
