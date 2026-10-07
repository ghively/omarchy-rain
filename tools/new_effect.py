#!/usr/bin/env python3
"""Scaffold a new BackgroundFX effect in every file that has to know about it.

A new effect must be registered in five places that are easy to get out of
step. This script does all of them at once, then you only write the shader
code inside the branch it creates:

  rain.frag          a working starter branch in scene(), marked TODO
  Rain.qml           effectKeys, effectLabels, effectIds, settingsTitles,
                     intensityLabels, speedLabels, implementedEffects
  write_settings.py  the EFFECTS allowlist (saving fails without it)
  manifest.json      the `effect` enum options
  README.md          a row in the effects table and the `effect` settings row

Usage (from the repository root):

  python3 tools/new_effect.py Meteors \\
      --label "Meteor Shower" \\
      --description "Shooting stars streaking across a dark sky" \\
      --intensity-label "METEOR COUNT" \\
      --speed-label "METEOR SPEED" \\
      --after Starfield

Every file is checked before any file is written, so a failed run changes
nothing. It does not rebuild rain.frag.qsb: run tools/build_shader.sh next.
"""

import argparse
import json
import os
import re
import sys

KEY_RE = re.compile(r"^[A-Z][A-Za-z ]{1,30}[A-Za-z]$")
FALLBACK_MARK = "    // Effects not yet implemented render nothing."


class ScaffoldError(Exception):
    pass


def read(root, name):
    with open(os.path.join(root, name), encoding="utf-8") as handle:
        return handle.read()


def quoted(text):
    return re.findall(r'"([^"]+)"', text)


def insert_in_list(src, prop, key, after):
    """Insert "key" into the QML list literal `prop: [ ... ]`."""
    match = re.search(r"(%s: \[)(.*?)(\])" % re.escape(prop), src, re.S)
    if not match:
        raise ScaffoldError("Rain.qml: could not find the %s list" % prop)
    inner = match.group(2)
    items = quoted(inner)
    if key in items:
        raise ScaffoldError("Rain.qml: %s already contains %r" % (prop, key))
    anchor = after if after in items else items[-1]
    new_inner = inner.replace('"%s"' % anchor, '"%s", "%s"' % (anchor, key), 1)
    return src[:match.start(2)] + new_inner + src[match.end(2):]


def insert_in_map(src, prop, key, value):
    """Append `"key": value` to the QML object literal `prop: { ... }`."""
    match = re.search(r"(%s: \{)(.*?)(\n  \})" % re.escape(prop), src, re.S)
    if not match:
        raise ScaffoldError("Rain.qml: could not find the %s map" % prop)
    if re.search(r'"%s"\s*:' % re.escape(key), match.group(2)):
        raise ScaffoldError("Rain.qml: %s already has %r" % (prop, key))
    addition = ',\n    "%s": %s' % (key, value)
    return src[:match.end(2)] + addition + src[match.end(2):]


def used_ids(qml):
    match = re.search(r"effectIds: \{(.*?)\n  \}", qml, re.S)
    if not match:
        raise ScaffoldError("Rain.qml: could not find the effectIds map")
    return {name: int(num) for name, num in re.findall(r'"([^"]+)":\s*(\d+)', match.group(1))}


def starter_branch(key, effect_id, description):
    lo, hi = effect_id - 0.5, effect_id + 0.5
    return (
        "    // %(key)s: %(description)s\n"
        "    // TODO(%(key)s): replace this starter body with the real effect. It\n"
        "    // draws three layers of white glowing dots so the effect visibly\n"
        "    // renders before you start. AGENTS.md section 5 says which layer\n"
        "    // helper fits which motion, and how to draw a real shape.\n"
        "    if (uEffect > %(lo).1f && uEffect < %(hi).1f) {\n"
        "        float i = 1.0 + (uIntensity - 1.0) * 0.5;\n"
        "        float a1 = fireflyLayer(p, vec2(80.0, 90.0) / i, 2.0, flow, vec2(1.3, 7.7), flow * 1.0) * 0.7;\n"
        "        float a2 = fireflyLayer(p, vec2(160.0, 175.0) / i, 2.8, flow, vec2(5.9, 2.4), flow * 1.6) * 0.9;\n"
        "        float a3 = fireflyLayer(p, vec2(280.0, 300.0) / i, 3.6, flow, vec2(8.2, 6.1), flow * 2.2) * 1.0;\n"
        "        float lum = clamp(a1 + a2 + a3, 0.0, 1.0);\n"
        "        vec3 col = vec3(1.0) * lum;\n"
        "        float alpha = clamp(lum * 0.9, 0.0, 1.0);\n"
        "        return vec4(col, alpha * qt_Opacity);\n"
        "    }\n"
        "\n"
    ) % {"key": key, "description": description, "lo": lo, "hi": hi}


def scaffold(root, key, label, description, intensity_label, speed_label, after=None, effect_id=None):
    if not KEY_RE.match(key):
        raise ScaffoldError("effect key %r must be 3-32 letters/spaces and start with a capital" % key)
    if '"' in label or '"' in description or '\n' in description:
        raise ScaffoldError("label and description must not contain quotes or newlines")

    qml = read(root, "Rain.qml")
    frag = read(root, "rain.frag")
    helper = read(root, "write_settings.py")
    manifest = read(root, "manifest.json")
    readme = read(root, "README.md")

    ids = used_ids(qml)
    if key in ids:
        raise ScaffoldError("effect %r already exists (id %d)" % (key, ids[key]))
    if after is not None and after not in ids:
        raise ScaffoldError("--after %r is not an existing effect" % after)
    if effect_id is None:
        effect_id = 0
        while effect_id in ids.values():
            effect_id += 1
    elif effect_id in ids.values():
        raise ScaffoldError("effect id %d is already used" % effect_id)
    if effect_id < 0 or effect_id > 99:
        raise ScaffoldError("effect id must be 0-99")

    # --- Rain.qml
    title = "%s SETTINGS" % label.upper()
    qml = insert_in_list(qml, "effectKeys", key, after)
    qml = insert_in_list(qml, "implementedEffects", key, after)
    qml = insert_in_map(qml, "effectLabels", key, json.dumps(label))
    qml = insert_in_map(qml, "effectIds", key, str(effect_id))
    qml = insert_in_map(qml, "settingsTitles", key, json.dumps(title))
    qml = insert_in_map(qml, "intensityLabels", key, json.dumps(intensity_label.upper()))
    qml = insert_in_map(qml, "speedLabels", key, json.dumps(speed_label.upper()))

    # --- rain.frag
    if frag.count(FALLBACK_MARK) != 1:
        raise ScaffoldError("rain.frag: could not find the fallback comment in scene()")
    if re.search(r"uEffect > %s\b" % re.escape("%.1f" % (effect_id - 0.5)), frag):
        raise ScaffoldError("rain.frag: a branch for id %d already exists" % effect_id)
    frag = frag.replace(FALLBACK_MARK, starter_branch(key, effect_id, description) + FALLBACK_MARK, 1)

    # --- write_settings.py
    match = re.search(r"EFFECTS = \{\n(.*?)\n\}", helper, re.S)
    if not match:
        raise ScaffoldError("write_settings.py: could not find the EFFECTS set")
    lines = match.group(1).split("\n")
    names = [line.strip().strip(",").strip('"') for line in lines]
    position = names.index(after) + 1 if after in names else len(lines)
    lines.insert(position, '    "%s",' % key)
    helper = helper[:match.start(1)] + "\n".join(lines) + helper[match.end(1):]

    # --- manifest.json (edited as text to keep its formatting)
    match = re.search(r'("key": "effect",.*?"options": \[)(.*?)(\])', manifest, re.S)
    if not match:
        raise ScaffoldError("manifest.json: could not find the effect options")
    options = quoted(match.group(2))
    anchor = after if after in options else options[-1]
    manifest = (manifest[:match.start(2)]
                + match.group(2).replace('"%s"' % anchor, '"%s", "%s"' % (anchor, key), 1)
                + manifest[match.end(2):])
    json.loads(manifest)

    # --- README.md: effects table row, and the `effect` settings row
    rows = readme.split("\n")
    table_rows = [n for n, line in enumerate(rows) if re.match(r"^\| `[^`]+` \| ", line)
                  and not line.startswith("| `effect`") and "| string |" not in line
                  and "| number |" not in line and "| boolean |" not in line]
    if not table_rows:
        raise ScaffoldError("README.md: could not find the effects table")
    target = table_rows[-1]
    for n in table_rows:
        if rows[n].startswith("| `%s` |" % after):
            target = n
    rows.insert(target + 1, "| `%s` | %s |" % (key, description))
    readme = "\n".join(rows)
    effect_row = re.search(r"^\| `effect` \| string \|.*$", readme, re.M)
    if effect_row:
        row = effect_row.group(0)
        listed = re.findall(r"`([^`]+)`", row)
        anchor = after if after in listed else [n for n in listed if n in ids][-1]
        row = row.replace("`%s`" % anchor, "`%s`, `%s`" % (anchor, key), 1)
        readme = readme[:effect_row.start()] + row + readme[effect_row.end():]

    files = {
        "Rain.qml": qml,
        "rain.frag": frag,
        "write_settings.py": helper,
        "manifest.json": manifest,
        "README.md": readme,
    }
    for name, text in files.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    return effect_id


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scaffold a new BackgroundFX effect.")
    parser.add_argument("key", help='Effect key stored in shell.json, e.g. "Meteors"')
    parser.add_argument("--label", help="Menu label (default: the key)")
    parser.add_argument("--description", required=True, help="One line for the README and the shader comment")
    parser.add_argument("--intensity-label", default="AMOUNT", help="Intensity slider label (default AMOUNT)")
    parser.add_argument("--speed-label", default="SPEED", help="Speed slider label (default SPEED)")
    parser.add_argument("--after", help="Place the effect after this one in the menu (default: last)")
    parser.add_argument("--id", type=int, dest="effect_id", help="uEffect id (default: lowest free id)")
    parser.add_argument("--root", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    # Edit the checkout you are standing in, never the one this script
    # happens to live in: running another checkout's copy of the tool must
    # not silently change that other checkout.
    root = os.path.abspath(args.root or os.getcwd())
    if not all(os.path.isfile(os.path.join(root, name)) for name in ("Rain.qml", "rain.frag", "write_settings.py")):
        print("new_effect: %s is not the BackgroundFX repository root; cd there first" % root, file=sys.stderr)
        return 1
    print("Editing the repository at %s" % root)
    try:
        effect_id = scaffold(root, args.key, args.label or args.key, args.description,
                             args.intensity_label, args.speed_label, args.after, args.effect_id)
    except ScaffoldError as error:
        print("new_effect: " + str(error), file=sys.stderr)
        return 1
    print("Added %s as uEffect %d. Next:" % (args.key, effect_id))
    print("  1. Write the effect in the TODO(%s) branch of scene() in rain.frag" % args.key)
    print("  2. tools/build_shader.sh")
    print("  3. python3 tools/render_effect.py --effect %s --time 2 6 12" % json.dumps(args.key))
    print("  4. python3 -m unittest discover -s tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
