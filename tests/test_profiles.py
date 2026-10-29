import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ae5control import core
from ae5control.profiles import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name))

    def test_roundtrip_drops_volume(self):
        self.store.save_profile("Test", {
            "FX: Crystalizer Playback Switch": [1],
            "Master Playback Volume": [99],  # darf nie im Profil landen
        })
        self.assertEqual(self.store.load_profile("Test"), {"FX: Crystalizer Playback Switch": [1]})

    def test_defaults_created_once(self):
        self.store.ensure_defaults()
        self.assertIn("Gaming", self.store.list_profiles())
        self.store.delete_profile("Gaming")
        self.store.ensure_defaults()
        self.assertNotIn("Gaming", self.store.list_profiles())

    def test_unsafe_names_stay_inside(self):
        self.store.save_profile("../böse/name", {"FX: Crystalizer Playback Switch": [0]})
        files = list((Path(self.tmp.name) / "profiles").iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(self.store.list_profiles(), ["../böse/name"])

    def test_delete_active_clears_state(self):
        self.store.save_profile("A", {})
        self.store.set_active_profile("A")
        self.store.delete_profile("A")
        self.assertIsNone(self.store.active_profile())

    def test_device_only_keeps_device_controls(self):
        self.store.save_device({"AE-5: Headphone Gain": [2], "EQ Band0 Playback Volume": [1]})
        self.assertEqual(self.store.load_device(), {"AE-5: Headphone Gain": [2]})


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name))
        self.mixer = mock.Mock()
        self.mixer.write.return_value = []

    def test_apply_merges_device_and_profile(self):
        self.store.save_device({"AE-5: Headphone Gain": [2]})
        self.store.save_profile("P", {"FX: X-Bass Playback Switch": [1]})
        core.apply_profile("P", self.mixer, self.store)
        self.mixer.write.assert_called_once_with(
            {"AE-5: Headphone Gain": [2], "FX: X-Bass Playback Switch": [1]}
        )
        self.assertEqual(self.store.active_profile(), "P")

    def test_apply_active_without_profile_writes_device(self):
        self.store.save_device({"AE-5: Headphone Gain": [1]})
        self.assertIsNone(core.apply_active(self.mixer, self.store))
        self.mixer.write.assert_called_once_with({"AE-5: Headphone Gain": [1]})


if __name__ == "__main__":
    unittest.main()


class PresetAndDefaultTests(unittest.TestCase):
    def test_presets_have_ten_bands_in_range(self):
        from ae5control.catalog import EQ_PRESET_DB, eq_raw
        for name, dbs in EQ_PRESET_DB.items():
            self.assertEqual(len(dbs), 10, name)
            self.assertTrue(all(0 <= eq_raw(d) <= 48 for d in dbs), name)

    def test_eq_mapping_is_one_db_per_step(self):
        from ae5control.catalog import eq_db, eq_raw
        self.assertEqual((eq_db(0), eq_db(24), eq_db(48)), (-24, 0, 24))
        self.assertEqual((eq_raw(-1.2), eq_raw(4.2), eq_raw(99)), (23, 28, 48))

    def test_defaults_are_complete(self):
        from ae5control.catalog import EQ_BANDS, PROFILE_CONTROLS
        from ae5control.profiles import DEFAULT_PROFILES
        for name, ctl in DEFAULT_PROFILES.items():
            self.assertTrue(all(b in ctl for b in EQ_BANDS), name)
            self.assertTrue(set(ctl) <= set(PROFILE_CONTROLS), name)

    def test_restore_builtin_and_migration(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            store.save_profile("Gaming", {"FX: Surround Playback Switch": [0]})  # alt/unvollständig
            store.save_profile("Eigenes", {"FX: Surround Playback Switch": [1]})
            store.ensure_defaults()
            self.assertIn("EQ Band0 Playback Volume", store.load_profile("Gaming"))
            self.assertEqual(store.load_profile("Eigenes"), {"FX: Surround Playback Switch": [1]})
            self.assertTrue(store.is_builtin("Gaming"))
            self.assertFalse(store.is_builtin("Eigenes"))


class LanguageTests(unittest.TestCase):
    def test_builtin_names_in_both_languages(self):
        for name in ("Musik", "Music", "Film", "Movie", "Gaming", "Neutral"):
            self.assertTrue(Store.is_builtin(name), name)
        self.assertFalse(Store.is_builtin("Meine Einstellungen"))

    def test_tr_picks_one_language(self):
        from ae5control import i18n
        self.assertIn(i18n.tr("de", "en"), ("de", "en"))
        self.assertEqual(i18n.tr("de", "en"), "de" if i18n.GERMAN else "en")
