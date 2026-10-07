#!/usr/bin/env python3
"""Render BackgroundFX effects to PNG so you can look at them without Omarchy.

The compiled shader (rain.frag.qsb) is drawn by a real Qt Quick ShaderEffect
over a stand-in wallpaper gradient, exactly as the widget draws it, then
saved as an image. Use it to check a new or edited effect.

  # One effect at several moments (seconds of animation time):
  python3 tools/render_effect.py --effect Meteors --time 2 6 12

  # Options: intensity 1-3, speed 0.5-3, tint colour, any uniform by name:
  python3 tools/render_effect.py --effect Fog --intensity 3 --tint "#ff7ab8"
  python3 tools/render_effect.py --effect Rain --set uStrike=1 uStrikePos=0.5,0.7

  # One frame of every effect on a single contact sheet:
  python3 tools/render_effect.py --all

  # Prove an edit changed nothing: compare every effect against another .qsb
  python3 tools/render_effect.py --all --compare /path/to/old/rain.frag.qsb

Images go to fx-previews/ (git-ignored); the paths are printed.

Needs PySide6 (pip install PySide6) and an OpenGL-capable display. Without a
display it re-runs itself under xvfb-run; Mesa's software renderer is enough.
On Debian/Ubuntu: apt-get install xvfb libgl1-mesa-dri libegl1 libxkbcommon-x11-0
libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xkb1
libxcb-render-util0 libxcb-image0.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "fx-previews")
QML_TYPES = {"float": "real", "vec2": "vector2d", "vec3": "vector3d", "vec4": "vector4d"}


def effect_ids():
    """Effect name -> uEffect id, read from Rain.qml so it never goes stale."""
    with open(os.path.join(ROOT, "Rain.qml"), encoding="utf-8") as handle:
        qml = handle.read()
    block = re.search(r"effectIds: \{(.*?)\n  \}", qml, re.S).group(1)
    return {name: int(num) for name, num in re.findall(r'"([^"]+)":\s*(\d+)', block)}


def uniforms():
    """(name, glsl type) for every custom uniform in rain.frag's buffer."""
    with open(os.path.join(ROOT, "rain.frag"), encoding="utf-8") as handle:
        frag = handle.read()
    block = re.search(r"uniform buf \{(.*?)\};", frag, re.S).group(1)
    found = re.findall(r"^\s*(float|vec2|vec3|vec4)\s+(\w+)\s*;", block, re.M)
    return [(name, kind) for kind, name in found if not name.startswith("qt_")]


def parse_hex(text):
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", text or "")
    if not match:
        raise SystemExit("--tint must look like #ff7ab8")
    h = match.group(1)
    return [int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1.0]


def build_scene(qsb_path, width, height):
    props = []
    for name, kind in uniforms():
        props.append("    property %s %s" % (QML_TYPES[kind], name))
    return """import QtQuick
Item {
  width: %(w)d; height: %(h)d
  Rectangle {
    anchors.fill: parent
    gradient: Gradient {
      GradientStop { position: 0.0; color: "#3a4a6b" }
      GradientStop { position: 0.5; color: "#6f6170" }
      GradientStop { position: 1.0; color: "#c08a5a" }
    }
  }
  ShaderEffect {
    objectName: "fx"
    anchors.fill: parent
%(props)s
    vertexShader: "%(vert)s"
    fragmentShader: "%(frag)s"
  }
}
""" % {
        "w": width, "h": height, "props": "\n".join(props),
        "vert": "file://" + os.path.join(ROOT, "rain.vert.qsb"),
        "frag": "file://" + qsb_path,
    }


def ensure_display():
    """Re-run under xvfb-run when there is no display to render into."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.environ.get("FX_NO_XVFB"):
        return
    if not shutil.which("xvfb-run"):
        raise SystemExit("No display, and xvfb-run is not installed (apt-get install xvfb).")
    env = dict(os.environ, FX_NO_XVFB="1")
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable] + sys.argv
    sys.exit(subprocess.call(cmd, env=env))


def main():
    parser = argparse.ArgumentParser(description="Render BackgroundFX effects to PNG.")
    parser.add_argument("--effect", action="append", default=[], help="Effect name (repeatable)")
    parser.add_argument("--all", action="store_true", help="Every effect, one frame each, plus a contact sheet")
    parser.add_argument("--time", type=float, nargs="+", default=[7.0], help="Animation seconds to capture")
    parser.add_argument("--intensity", type=float, default=2.0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--tint", help='Colour tint, e.g. "#ff7ab8" (default: effect colours)')
    parser.add_argument("--set", nargs="+", default=[], metavar="uName=v[,v...]", help="Set any uniform")
    parser.add_argument("--size", default="960x540", help="Image size WxH (default 960x540)")
    parser.add_argument("--qsb", default=os.path.join(ROOT, "rain.frag.qsb"), help=argparse.SUPPRESS)
    parser.add_argument("--compare", metavar="OTHER.qsb", help="Report pixel differences against another build")
    parser.add_argument("--out", default=OUT_DIR, help="Output directory (default fx-previews/)")
    args = parser.parse_args()

    ids = effect_ids()
    names = sorted(ids, key=ids.get) if args.all else args.effect
    if not names:
        parser.error("give --effect NAME or --all")
    for name in names:
        if name not in ids:
            parser.error("unknown effect %r; known: %s" % (name, ", ".join(ids)))
    width, height = (int(v) for v in args.size.lower().split("x"))

    ensure_display()
    os.environ.setdefault("QSG_RHI_BACKEND", "opengl")
    os.environ.setdefault("LANG", "C.UTF-8")

    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QVector2D, QVector3D, QVector4D
    from PySide6.QtQuick import QQuickItem, QQuickView

    app = QGuiApplication(sys.argv[:1])
    kinds = dict(uniforms())
    vec = {"vec2": QVector2D, "vec3": QVector3D, "vec4": QVector4D}

    def make_view(qsb_path, tmpdir, tag):
        path = os.path.join(tmpdir, "scene_%s.qml" % tag)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(build_scene(os.path.abspath(qsb_path), width, height))
        view = QQuickView()
        view.setSource(QUrl.fromLocalFile(path))
        if view.status() != QQuickView.Ready:
            raise SystemExit("\n".join(e.toString() for e in view.errors()))
        view.show()
        return view, view.rootObject().findChild(QQuickItem, "fx")

    def set_uniform(fx, name, values):
        kind = kinds.get(name)
        if kind is None:
            raise SystemExit("unknown uniform %r; known: %s" % (name, ", ".join(kinds)))
        fx.setProperty(name, float(values[0]) if kind == "float" else vec[kind](*[float(v) for v in values]))

    def configure(fx, effect, t):
        for name, kind in kinds.items():
            if kind == "float":
                fx.setProperty(name, 0.0)
        fx.setProperty("uRes", QVector2D(width, height))
        fx.setProperty("time", t)
        fx.setProperty("uEffect", float(ids[effect]))
        fx.setProperty("uIntensity", args.intensity)
        fx.setProperty("uSpeed", args.speed)
        if "uStraightness" in kinds:
            fx.setProperty("uStraightness", 1.0)
        if "uStrikePos" in kinds:
            fx.setProperty("uStrikePos", QVector2D(0.5, 0.6))
        if "uTint" in kinds:
            fx.setProperty("uTint", QVector4D(*(parse_hex(args.tint) if args.tint else [0, 0, 0, 0])))
        for item in args.set:
            name, _, raw = item.partition("=")
            set_uniform(fx, name, raw.split(","))

    def grab(view):
        loop = QEventLoop()
        QTimer.singleShot(120, loop.quit)
        loop.exec()
        return view.grabWindow()

    os.makedirs(args.out, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="fx-render-")
    view, fx = make_view(args.qsb, tmpdir, "main")
    other = make_view(args.compare, tmpdir, "other") if args.compare else None

    frames = []
    differing = []
    for name in names:
        for t in args.time:
            configure(fx, name, t)
            image = grab(view)
            slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
            path = os.path.join(args.out, "%s_t%g.png" % (slug, t))
            image.save(path)
            frames.append((name, t, image))
            if other:
                configure(other[1], name, t)
                if grab(other[0]) != image:
                    differing.append("%s @ %gs" % (name, t))
                    print("DIFFERS   %s" % path)
                else:
                    print("identical %s" % path)
            else:
                print(path)

    if args.all:
        cols = 4
        thumb_w, thumb_h = width // 2, height // 2
        rows = (len(frames) + cols - 1) // cols
        sheet = QImage(cols * thumb_w, rows * thumb_h, QImage.Format_RGB32)
        sheet.fill(QColor("#101018"))
        painter = QPainter(sheet)
        for n, (name, t, image) in enumerate(frames):
            x, y = (n % cols) * thumb_w, (n // cols) * thumb_h
            painter.drawImage(x, y, image.scaled(thumb_w, thumb_h))
            painter.setPen(QColor("white"))
            painter.drawText(x + 8, y + 18, "%s (uEffect %d)" % (name, ids[name]))
        painter.end()
        path = os.path.join(args.out, "contact_sheet.png")
        sheet.save(path)
        print(path)

    shutil.rmtree(tmpdir, ignore_errors=True)
    if other:
        print("%d of %d frames differ" % (len(differing), len(frames)))
        return 1 if differing else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
