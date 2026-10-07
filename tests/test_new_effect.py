import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ("Rain.qml", "rain.frag", "write_settings.py", "manifest.json", "README.md")


def load_tool():
    spec = importlib.util.spec_from_file_location("new_effect", ROOT / "tools" / "new_effect.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def catalogue(root):
    """The effect lists from every file the scaffolder edits."""
    qml = (root / "Rain.qml").read_text()
    lists = {
        "implementedEffects": re.findall(r'"([^"]+)"', re.search(r"implementedEffects: \[(.*?)\]", qml, re.S).group(1)),
        "effectKeys": re.findall(r'"([^"]+)"', re.search(r"effectKeys: \[(.*?)\]", qml, re.S).group(1)),
    }
    for name in ("effectLabels", "effectIds", "settingsTitles", "intensityLabels", "speedLabels"):
        block = re.search(r"%s: \{(.*?)\n  \}" % name, qml, re.S).group(1)
        lists[name] = re.findall(r'"([^"]+)":', block)
    helper = (root / "write_settings.py").read_text()
    lists["EFFECTS"] = re.findall(r'"([^"]+)"', re.search(r"EFFECTS = \{(.*?)\}", helper, re.S).group(1))
    manifest = json.loads((root / "manifest.json").read_text())
    lists["manifest"] = next(i for i in manifest["barWidget"]["schema"] if i["key"] == "effect")["options"]
    return lists


class NewEffectTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.tmp = Path(tempfile.mkdtemp())
        for name in FILES:
            shutil.copy(ROOT / name, self.tmp / name)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.tool.main(list(args) + ["--root", str(self.tmp)])
        return code, out.getvalue() + err.getvalue()

    def test_registers_effect_everywhere(self):
        code, output = self.run_tool("Lanterns", "--label", "Sky Lanterns", "--description",
                                     "Warm paper lanterns rising slowly", "--after", "Embers")
        self.assertEqual(code, 0, output)
        lists = catalogue(self.tmp)
        for name, items in lists.items():
            with self.subTest(table=name):
                self.assertIn("Lanterns", items)
                self.assertEqual(set(items), set(lists["effectIds"]))
        order = lists["implementedEffects"]
        self.assertEqual(order[order.index("Embers") + 1], "Lanterns")
        qml = (self.tmp / "Rain.qml").read_text()
        effect_id = int(re.search(r'"Lanterns": (\d+)', qml).group(1))
        ids = [int(n) for n in re.findall(r'": (\d+)', re.search(r"effectIds: \{(.*?)\n  \}", qml, re.S).group(1))]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(effect_id, min(set(range(100)) - set(ids) | {effect_id}))
        frag = (self.tmp / "rain.frag").read_text()
        self.assertIn("uEffect > %.1f && uEffect < %.1f" % (effect_id - 0.5, effect_id + 0.5), frag)
        self.assertLess(frag.index("TODO(Lanterns)"), frag.index("// Effects not yet implemented"))
        readme = (self.tmp / "README.md").read_text()
        self.assertIn("| `Lanterns` | Warm paper lanterns rising slowly |", readme)
        self.assertRegex(readme, r"`Embers`, `Lanterns`")

    def test_scaffolded_effect_saves(self):
        self.assertEqual(self.run_tool("Lanterns", "--description", "x")[0], 0)
        spec = importlib.util.spec_from_file_location("ws_tmp", self.tmp / "write_settings.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        self.assertEqual(helper.validate_changes({"effect": "Lanterns"}), {"effect": "Lanterns"})

    def test_refuses_bad_input_without_writing(self):
        before = {name: (self.tmp / name).read_text() for name in FILES}
        for args in (("Rain", "--description", "x"),
                     ("lowercase", "--description", "x"),
                     ("Lanterns", "--description", "x", "--after", "Nope"),
                     ("Lanterns", "--description", "x", "--id", "0")):
            with self.subTest(args=args):
                code, _ = self.run_tool(*args)
                self.assertEqual(code, 1)
                for name in FILES:
                    self.assertEqual((self.tmp / name).read_text(), before[name])


class RepositoryCatalogueTests(unittest.TestCase):
    def test_every_table_lists_the_same_effects(self):
        lists = catalogue(ROOT)
        expected = set(lists["effectIds"])
        for name, items in lists.items():
            with self.subTest(table=name):
                self.assertEqual(set(items), expected)
                self.assertEqual(len(items), len(set(items)))

    def test_every_effect_has_a_shader_branch(self):
        qml = (ROOT / "Rain.qml").read_text()
        frag = (ROOT / "rain.frag").read_text()
        ids = re.findall(r'"([^"]+)": (\d+)', re.search(r"effectIds: \{(.*?)\n  \}", qml, re.S).group(1))
        for name, num in ids:
            with self.subTest(effect=name):
                n = int(num)
                if n <= 1:
                    continue  # Rain and Snow use the older one-sided tests
                self.assertIn("uEffect > %.1f && uEffect < %.1f" % (n - 0.5, n + 0.5), frag)
        self.assertNotIn("TODO(", frag, "a scaffolded starter branch was never replaced")


if __name__ == "__main__":
    unittest.main()
