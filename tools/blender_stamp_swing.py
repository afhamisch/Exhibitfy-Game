"""Blender-side setup for the Stamp_Swing action.

Run it either way:

    blender --python tools/blender_stamp_swing.py -- build/exhibitfy_fpv_arms.glb

or open Blender, paste this file into the Text Editor, and press Run Script
(it will find and import the GLB relative to the .blend, or use whatever is
already in the scene).

What it does, and why each step is needed:

* Sets the scene to 30 fps with frame range 0-22. Blender defaults to 24 fps
  and frames 1-250, which is the usual reason a freshly imported swing looks
  wrong or appears to do nothing for most of the timeline.
* Imports the GLB if the rig is not already in the scene.
* Names every imported action `Stamp_Swing` (Blender appends .001, .002 ... to
  keep names unique -- see the note below).
* Makes sure each action is assigned and unmuted so Spacebar plays the whole
  swing, and so selecting any rig object shows `Stamp_Swing` in the Action
  Editor / Dope Sheet.
* Leaves the playhead on frame 0 with the ready pose showing.

NOTE on "one action": glTF stores object-level animation as per-node channels,
and Blender's importer turns each animated object into its own Action. So a
23-frame swing across 13 objects imports as 13 actions that all belong to the
one `Stamp_Swing` clip -- that is Blender's data model, not a broken export.
They are frame-locked to each other and play together as a single motion.
Pass --nla to additionally push them onto NLA tracks named `Stamp_Swing`, which
is the tidier setup if you plan to layer or blend clips later.
"""

import os
import sys

import bpy

ACTION_NAME = "Stamp_Swing"
FPS = 30
FRAME_START = 0
FRAME_END = 22
RIG_ROOT = "TomRexington_FPV_Rig"


def _argv():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def find_glb(explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    roots = [os.path.dirname(bpy.data.filepath or ""), os.getcwd()]
    try:
        roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except NameError:
        pass
    for root in roots:
        if not root:
            continue
        for rel in ("build/exhibitfy_fpv_arms.glb", "exhibitfy_fpv_arms.glb"):
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                return p
    return None


def rig_present():
    return any(o.name.startswith(RIG_ROOT) or o.name.startswith("Stamp_")
               for o in bpy.data.objects)


def setup(glb_path=None, use_nla=False):
    scene = bpy.context.scene

    if not rig_present():
        path = find_glb(glb_path)
        if not path:
            raise RuntimeError(
                "no rig in the scene and no exhibitfy_fpv_arms.glb found -- "
                "pass the path: blender --python this.py -- /path/to.glb")
        print("importing %s" % path)
        bpy.ops.import_scene.gltf(filepath=path)

    # --- timeline: 30 fps, 0-22, so Spacebar plays exactly the swing
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.frame_set(FRAME_START)

    animated = [o for o in bpy.data.objects
                if o.animation_data and (o.animation_data.action
                                         or o.animation_data.nla_tracks)]
    if not animated:
        raise RuntimeError(
            "nothing in the scene is animated -- re-import the GLB with "
            "'Animation' enabled in the glTF import options")

    # --- pull any NLA-stashed actions back onto the objects first
    for obj in animated:
        ad = obj.animation_data
        if ad.action is None:
            for track in list(ad.nla_tracks):
                if track.strips:
                    ad.action = track.strips[0].action
                    ad.nla_tracks.remove(track)
                    break

    renamed = 0
    for obj in animated:
        ad = obj.animation_data
        if ad.action is None:
            continue
        if not ad.action.name.startswith(ACTION_NAME):
            ad.action.name = ACTION_NAME          # Blender uniquifies as .00N
            renamed += 1
        ad.action.use_fake_user = True
        ad.use_nla = False                        # active action drives it
        for track in ad.nla_tracks:
            track.mute = True
        # keys land exactly on frames; constant-ish easing is baked already
        for fc in ad.action.fcurves:
            fc.mute = False
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.update()

    if use_nla:
        for obj in animated:
            ad = obj.animation_data
            if ad.action is None:
                continue
            track = ad.nla_tracks.new()
            track.name = ACTION_NAME
            track.mute = False
            track.strips.new(ACTION_NAME, int(FRAME_START), ad.action)
            ad.action = None
            ad.use_nla = True

    # --- select the stamp so the Action Editor opens on something useful
    stamp = bpy.data.objects.get("Stamp_Exhibitfy")
    if stamp:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        stamp.select_set(True)
        bpy.context.view_layer.objects.active = stamp

    keyed = sum(len(o.animation_data.action.fcurves)
                for o in animated
                if o.animation_data and o.animation_data.action)
    print("-" * 62)
    print("%s ready: %d animated objects, %d f-curves, %d action(s) renamed"
          % (ACTION_NAME, len(animated), keyed, renamed))
    print("timeline: %d-%d @ %d fps (%.3f s)"
          % (FRAME_START, FRAME_END, FPS, (FRAME_END - FRAME_START) / FPS))
    print("beats: 0 ready | 4-5 cocked | 11-13 planted on the plane | 22 ready")
    print("press Spacebar in the Timeline to play%s"
          % (" (NLA strips)" if use_nla else ""))
    print("-" * 62)
    return animated


if __name__ == "__main__":
    args = _argv()
    setup(glb_path=next((a for a in args if a.endswith(".glb")), None),
          use_nla="--nla" in args)
