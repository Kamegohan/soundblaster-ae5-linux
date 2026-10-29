import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ae5control import mixer as mx

SAMPLE = (Path(__file__).parent / "sample_contents.txt").read_text()


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.ctls = mx.parse_contents(SAMPLE)

    def test_only_mixer_controls(self):
        self.assertNotIn("Headphone Jack", self.ctls)

    def test_integer_with_range(self):
        c = self.ctls["Master Playback Volume"]
        self.assertEqual((c.type, c.minimum, c.maximum, c.values), ("INTEGER", 0, 99, [58]))

    def test_boolean_per_channel(self):
        self.assertEqual(self.ctls["Front Playback Switch"].values, [1, 0])

    def test_enumerated_items_and_range(self):
        c = self.ctls["AE-5: Headphone Gain"]
        self.assertEqual(c.items[2], "High (150-600  Ohms)")
        self.assertEqual((c.minimum, c.maximum, c.values), (0, 2, [2]))

    def test_iec958_has_no_values(self):
        self.assertEqual(self.ctls["IEC958 Playback Default"].values, [])

    def test_read_only_flag(self):
        self.assertFalse(self.ctls["Read Only Thing"].writable)


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.ctls = mx.parse_contents(SAMPLE)
        self.calls = []

        def runner(cmd, **kw):
            self.calls.append((cmd, kw.get("input")))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        self.mixer = mx.Mixer(runner=runner)
        patcher = mock.patch.object(mx, "find_card", return_value=1)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_batches_and_clamps(self):
        skipped = self.mixer.write(
            {"EQ Band0 Playback Volume": [99], "FX: Crystalizer Playback Switch": [0]}, self.ctls
        )
        self.assertEqual(skipped, [])
        cmd, script = self.calls[0]
        self.assertEqual(cmd[:4], ["amixer", "-c", "1", "-q"])
        self.assertIn("cset name='EQ Band0 Playback Volume' 48", script)
        self.assertIn("cset name='FX: Crystalizer Playback Switch' 0", script)

    def test_skips_unknown_and_read_only(self):
        skipped = self.mixer.write({"Nope": [1], "Read Only Thing": [1]}, self.ctls)
        self.assertEqual(sorted(skipped), ["Nope", "Read Only Thing"])
        self.assertEqual(self.calls, [])

    def test_error_raises(self):
        bad = mx.Mixer(runner=lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="kaputt"))
        with self.assertRaises(mx.MixerError):
            bad.write({"EQ Band0 Playback Volume": [1]}, self.ctls)


class FindCardTests(unittest.TestCase):
    def test_finds_by_id(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for n, cid in ((0, "HDMI"), (3, "Creative")):
                p = Path(d) / f"card{n}"
                p.mkdir()
                (p / "id").write_text(cid + "\n")
            self.assertEqual(mx.find_card(Path(d)), 3)

    def test_missing_card(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, self.assertRaises(mx.MixerError):
            mx.find_card(Path(d))


if __name__ == "__main__":
    unittest.main()
