# AGENTS.md: building BackgroundFX effects

Instructions for a coding agent adding or changing an animated effect in this
plugin. Follow them in order. Every step has a command that tells you whether
it worked; do not skip those checks.

## 1. What this project is

An Omarchy bar widget. Clicking its wand icon shows an animated effect (rain,
snow, starfield...) on a full-screen layer between the wallpaper and the
windows. **All drawing happens in one GPU fragment shader, `rain.frag`.**
The GPU runs it once for every pixel, every frame (up to 60 per second).

| File | What it is | You edit it when |
| --- | --- | --- |
| `rain.frag` | The shader. Helpers, `scene()` (one `if` branch per effect), `tint()`, `main()` | Always |
| `rain.frag.qsb` | Compiled shader. Qt loads only this | Rebuild after **every** `rain.frag` edit (step 4) |
| `Rain.qml` | Widget, settings menu, uniform bindings | New effect (the scaffolder does it) or new setting |
| `write_settings.py` | Saves settings; rejects unknown values | New effect (scaffolder) or new setting |
| `manifest.json` | Settings schema | New effect (scaffolder) or new setting |
| `README.md` | User docs | New effect (scaffolder adds the row) |
| `tools/new_effect.py` | Registers a new effect in all of the above | Never; run it |
| `tools/build_shader.sh` | Compiles `rain.frag` to `rain.frag.qsb` | Never; run it |
| `tools/render_effect.py` | Renders effects to PNG so you can see them | Never; run it |
| `rain.vert`, `upscale.frag`, `*.vert.qsb`, `upscale.frag.qsb` | Fixed plumbing | **Never** |

## 2. Hard rules

0. **Work only in your own checkout, from its root.** Run every command from
   the directory that contains `Rain.qml`, and only run the `tools/` inside
   that same checkout. If `tools/new_effect.py` or this file's tools are
   missing from your checkout, **stop and report it**: you are on an old
   branch. Never borrow tools or files from another copy of the repository,
   and never hand-edit the effect tables as a workaround.
1. **Never edit a `.qsb` file by hand.** Only `tools/build_shader.sh` writes `rain.frag.qsb`.
2. **Commit `rain.frag` and `rain.frag.qsb` together.** `tools/build_shader.sh --check` must say "up to date".
3. **Don't change other effects' output.** Before finishing, run the comparison in step 6. Only the effects you meant to change may differ.
4. **Never reorder or edit the Rain and Snow branches** (`uEffect < 0.5`, `uEffect < 1.5`). They rely on being first.
5. **Register effects only with `tools/new_effect.py`.** Hand-editing the tables is how effects end up in the menu but fail to save.
6. **Animate with `flow`, never `time`.** `flow = time * uSpeed`, so the speed slider keeps working.
7. **Always return `vec4(col, alpha * qt_Opacity)`** from your branch.
8. **All tests must pass:** `python3 -m unittest discover -s tests`.

## 3. One-time setup

Run these from the repository root. Each one prints something you can check.

```sh
# Python with PySide6 (provides the Qt shader compiler and the renderer).
python3 -m venv .venv-fx
.venv-fx/bin/pip install PySide6
export PATH="$PWD/.venv-fx/bin:$PATH"        # repeat in every new shell

# Debian/Ubuntu only: software OpenGL and a virtual display for rendering.
sudo apt-get install -y xvfb libgl1-mesa-dri libegl1 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xkb1 \
  libxcb-render-util0 libxcb-image0 libfontconfig1

# Check: both must succeed.
tools/build_shader.sh --check                  # -> "rain.frag.qsb is up to date."
python3 tools/render_effect.py --effect Rain   # -> prints fx-previews/rain_t7.png
```

On Arch (Omarchy) the system `qt6-shadertools` package provides
`/usr/lib/qt6/bin/qsb`, which `build_shader.sh` finds on its own; the renderer
still needs `pip install PySide6` or the `pyside6` package.

If `build_shader.sh --check` says "stale" before you have changed anything,
stop and report it. The repository was already inconsistent.

## 4. Recipe: add a new effect

Example: an effect called `Lanterns`.

**Step 1: scaffold.** From the repository root:

```sh
python3 tools/new_effect.py Lanterns \
  --label "Sky Lanterns" \
  --description "Warm paper lanterns drifting slowly upward" \
  --intensity-label "LANTERN COUNT" \
  --speed-label "RISE SPEED" \
  --after Embers
```

- `Lanterns` is the **key**: the internal name saved in settings and used in
  every table. Keep it short, one word if possible, capitalised. It is
  *not* the menu text: never use the label (`"Sky Lanterns"`) as the key.
- `--label` is the menu text people see. `--after` sets the menu position (default: last).
- It prints `Editing the repository at <path>`: check that `<path>` is your
  checkout. Then it prints the `uEffect` id it chose (the lowest free number).
- It refuses (exit 1, nothing changed) if the key exists or an argument is bad.

**Step 2: find your branch.** `grep -n "TODO(Lanterns)" rain.frag`. The
scaffolder put a working starter branch (white glowing dots) just above
`// Effects not yet implemented render nothing.`

**Step 3: build and look at the starter** before changing anything, so you
know the pipeline works:

```sh
tools/build_shader.sh
python3 tools/render_effect.py --effect Lanterns --time 2 6 12
```

Open the printed PNGs. You should see small white dots over a blue-to-orange
gradient (the stand-in wallpaper).

**Step 4: write the effect.** Replace everything inside the branch's braces,
and replace the two `TODO` comment lines above the `if` with a real
description of the look. Pick a pattern from section 5 as your starting
point. Keep the `if (uEffect > N.5 && uEffect < M.5)` line exactly as
generated.

**Step 5: build, render, look, repeat.** After each change:

```sh
tools/build_shader.sh                                   # compile errors appear here
python3 tools/render_effect.py --effect Lanterns --time 2 6 12
python3 tools/render_effect.py --effect Lanterns --time 6 --intensity 1 --out fx-previews/low
python3 tools/render_effect.py --effect Lanterns --time 6 --intensity 3 --out fx-previews/high
python3 tools/render_effect.py --effect Lanterns --time 6 --tint "#ff7ab8" --out fx-previews/tint
```

Check every image against the acceptance list in section 7. Different
`--time` values must look different (it is animated), intensity 1 must be
visibly lighter than 3, and the wallpaper gradient must stay visible.

**Step 6: prove nothing else changed.** Compare against the committed build:

```sh
git show HEAD:rain.frag.qsb > /tmp/before.qsb
python3 tools/render_effect.py --all --compare /tmp/before.qsb
```

Only your new effect may say `DIFFERS`. If any other effect differs, you
changed shared code (a helper or `tint()`); undo that and use a new helper.

**Step 7: tests and commit.**

```sh
python3 -m unittest discover -s tests     # must say OK
tools/build_shader.sh --check             # must say up to date
git add rain.frag rain.frag.qsb Rain.qml write_settings.py manifest.json README.md
git commit -m "Add Lanterns effect"
```

A test fails if a `TODO(` starter branch is still in `rain.frag`.

## 5. Shader cookbook

### What your branch receives

| Name | Type | Meaning |
| --- | --- | --- |
| `p` | `vec2` | This pixel, in pixels. (0,0) is the **top-left**; y grows **downward** |
| `uRes` | `vec2` | Render size in pixels. `p / uRes` is 0..1 across the screen |
| `flow` | `float` | Animation clock in seconds, already scaled by the speed slider. Use it for all motion |
| `uIntensity` | `float` | The intensity slider, always 1..3. Map it yourself, e.g. `float i = 1.0 + (uIntensity - 1.0) * 0.5;` |
| `uAudio` | `float` | Smoothed audio level 0..1 (only non-zero for Aurora today) |
| `qt_Opacity` | `float` | Multiply your alpha by this |

Helpers you can call:

| Helper | Returns |
| --- | --- |
| `hash(vec2)` | Repeatable pseudo-random 0..1 for a coordinate |
| `hash2(vec2)` | Two of them |
| `vnoise(vec2)` | Smooth noise 0..1, one blob per unit |
| `fbm(vec2)` | Layered noise 0..1 with fine detail (4 `vnoise` calls) |
| `starDust(p, flow, cellPx, chance)` | Faint twinkling background stars, 0..1 |
| `fireflyLayer`, `emberLayer`, `dustLayer`, `snowLayer` | One layer of soft glowing particles (see their comments) |
| `leafLayer`, `confettiLayer` | One layer of coloured tumbling shapes, as `vec3` |
| `segDistSq(p, a, b)` | Squared distance from `p` to the segment a-b |

### What your branch returns

`return vec4(col, alpha * qt_Opacity);` The screen shows
`col + (1 - alpha) * wallpaper`. So:

- **Glowing light** (stars, embers, sparks): make `col` brighter than
  `alpha`, e.g. `col = colour * glow * 1.2; alpha = glow * 0.9;`. This adds
  light to the wallpaper.
- **Matte veil** (fog, smoke, shadow): `col = colour * a; alpha = a;`. This
  covers the wallpaper.
- **A faint full-screen wash** is a small constant in alpha, e.g. `+ 0.05`.
  Keep it under 0.2 or the desktop gets murky.

Colours are `vec3(r, g, b)` with 0..1 channels: `vec3(1.0, 0.6, 0.2)` is
orange.

### Pattern A: falling or rising particles (snow, embers, lanterns)

Call a particle layer three times: small, dense and dim at the back; large,
sparse and bright at the front. Smaller `cell` sizes mean more particles.

```glsl
float i = 1.0 + (uIntensity - 1.0) * 0.5;
float a1 = emberLayer(p, vec2( 80.0, 110.0) / i, 2.4,  flow, vec2(1.3, 7.7), flow * 0.6) * 0.7;
float a2 = emberLayer(p, vec2(150.0, 200.0) / i, 3.3,  flow, vec2(5.9, 2.4), flow * 1.1) * 0.9;
float a3 = emberLayer(p, vec2(260.0, 340.0) / i, 4.35, flow, vec2(8.2, 6.1), flow * 1.7) * 1.0;
float glow = clamp(a1 + a2 + a3, 0.0, 1.0);
vec3 col = vec3(1.0, 0.75, 0.40) * glow * 1.3;
float alpha = clamp(glow * 0.9 + 0.02, 0.0, 1.0);
return vec4(col, alpha * qt_Opacity);
```

Arguments: `(p, cell size px, particle size px, flow, seed, sideways drift px)`.
Use different `seed` numbers from every other effect. To change how a
particle moves or looks, copy the layer function, rename it (`lanternLayer`),
put the copy next to the original, and edit the copy. **Never edit a shared
layer function**; other effects use it.

### Pattern B: clouds, fog, smoke (noise fields)

```glsl
vec2 n = p / uRes.y;                       // screen-height units: no stretching
float t = flow * 0.05;                     // slow drift
float cloud = fbm(n * 1.5 + vec2(t, 0.0)); // 0..1; bigger multiplier = smaller blobs
float a = smoothstep(0.45, 0.85, cloud);   // raise 0.45 for more gaps
a *= 0.6 * (0.75 + (uIntensity - 1.0) * 0.35);
vec3 col = vec3(0.82, 0.85, 0.90) * a;     // matte veil
return vec4(col, a * qt_Opacity);
```

For billowing shapes, bend the input with another noise ("domain warp"); see
the Fog branch. For colour variation, use a second `fbm` to pick between
colours with `mix(colourA, colourB, smoothstep(0.35, 0.65, other))`; see
Nebula.

### Pattern C: occasional events (meteors, sparks, flashes)

No timer is needed. Split time into periods per "slot"; each period launches
one event whose random properties come from hashing the slot and period
number:

```glsl
for (int k = 0; k < 8; k++) {                       // loop bound must be a constant
    float kk = float(k);
    float period = 4.0 + 8.0 * hash(vec2(kk, 1.7));  // seconds between events in this slot
    float local = flow / period + hash(vec2(kk, 9.2));
    float launch = floor(local);                     // which event this is
    float t = fract(local) * period / 0.9;           // 0..1 during a 0.9 s event
    if (t >= 1.0) continue;                          // between events: nothing
    vec2 r = hash2(vec2(launch * 3.1 + kk, kk * 7.7 + launch));  // this event's randoms
    vec2 at = r * uRes;                              // e.g. where it happens
    ... draw it, fading with smoothstep(0.0, 0.1, t) * (1.0 - smoothstep(0.7, 1.0, t)) ...
}
```

See the Meteors branch for a complete example.

### Pattern D: shapes

Distance to a shape, then a soft edge:
`float d = length(p - centre); float disc = 1.0 - smoothstep(r - 1.0, r + 1.0, d);`.
For a line use `sqrt(segDistSq(p, a, b))`. For a box,
`vec2 q = abs(p - centre) - halfSize; float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);`.
Use about 1 pixel of softness so edges don't look jagged.

### GLSL rules that trip agents up

- Write floats with a decimal point: `1.0`, not `1`. `0.5 * 2` is an error.
- Convert explicitly: `float(k)`, `int(x)`.
- Loops need a constant bound: `for (int k = 0; k < 10; k++)`. For a variable
  count, add `if (float(k) >= count) break;`.
- Use `mod(x, y)` for floats; `%` is integers only.
- No recursion, no `#include`, no textures (the shader cannot see the wallpaper).
- Declare helper functions **above** `scene()`, next to the other helpers.
- Every code path in your branch must `return`.

## 6. Performance budget

Every line runs for every pixel. Per pixel, stay within roughly:

- 3 particle layers, **or** 6 `fbm` calls, **or** a loop of at most 12 short iterations.
- No loop inside a loop.
- Exit early when a pixel is far from anything visible (`if (d > reach) continue;`).

If an effect needs more, say so in your summary; users can lower the
Resolution slider.

## 7. Acceptance checks for a new effect

Look at the PNGs from step 5. All must hold:

1. Something visible appears at intensity 2, time 6.
2. The wallpaper gradient is still recognisable behind it (it is a background effect, not a cover).
3. Frames at different `--time` values differ (it moves).
4. Intensity 1 is clearly lighter or sparser than intensity 3.
5. With `--tint "#ff7ab8"` the effect turns pink, keeping its shape.
6. No hard straight seams, grid lines, or visible repeating tiles.
7. Step 6's comparison shows only your effect as `DIFFERS`.
8. Tests pass and `build_shader.sh --check` is up to date.

## 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `build_shader.sh` prints an error with a line number | GLSL error in `rain.frag` at that line; see "GLSL rules" |
| `qsb not found` | Do the setup in section 3, or `export QSB=/path/to/qsb` |
| Render is only the gradient, no effect | Branch never runs: wrong `uEffect` range, or branch placed after the fallback, or you forgot to rebuild |
| Render is solid colour or black | `alpha` too high or `col` huge; clamp both. Check for division by zero |
| Effect doesn't move between times | You used `time`, a constant, or forgot `flow` |
| Speckles / noise everywhere | Hash input too small or identical seeds; scale the input or change seeds |
| Visible square grid | Particles reach the cell edge; shrink the particle or add the edge cull used in the layer functions |
| `render_effect.py`: "No display, and xvfb-run is not installed" | `apt-get install xvfb` (section 3) |
| Test `scaffolded starter branch was never replaced` | Replace the `TODO(...)` starter body and comment |
| Test about tables listing different effects | Someone edited the tables by hand; re-check with `git diff` and fix to match |
| `new_effect: ... is not the BackgroundFX repository root` | `cd` to the directory containing `Rain.qml` and rerun |
| `tools/` doesn't exist | Old branch. Stop and report; don't copy tools from elsewhere |
| `--compare` shows other effects differ | You changed a shared helper, `tint()`, or the uniform block; revert and add a new helper instead |

## 9. Other kinds of change

**Tune an existing effect:** edit only its branch (or a renamed copy of its
layer function), then steps 5 to 7. The README "Tuning" notes and the comments
above each branch say which numbers control what.

**Add a setting** (a slider or menu just for one effect): follow how
`straightness` is wired through every layer. Add a schema entry in
`manifest.json`, an allowlist entry in `write_settings.py` (`NUMERIC_LIMITS`,
`BOOLEAN_KEYS` or `ENUM_KEYS`), a property, setter and control in `Rain.qml`
(`visible: root.effect === "YourEffect"`), a `property real uName` on the
`ShaderEffect`, and `float uName;` at the **end** of `uniform buf` in
`rain.frag`. `render_effect.py` picks up new uniforms automatically; set one
with `--set uName=1.5`. Add a test case to `tests/test_write_settings.py` for
the new value's valid and invalid inputs.

**Remove an effect:** remove its branch and every table entry by hand, then
run the tests; they list anything you missed.

## 10. When you report back

State what effect you added or changed, its `uEffect` id, the PNG paths you
checked, the output of the `--compare` run, and the test result. If you could
not run the renderer, say so plainly instead of claiming it looks right.
