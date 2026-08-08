"""Unit tests for additive seed helpers (no DB required)."""

from pathlib import Path

from scripts.seeds.common import load_seed_rows, strip_primary_key
from scripts.seeds.registry import UPDATES, get_update


class TestAdditiveSeedRegistry:
    def test_hotels_tours_update_is_registered(self):
        mod = get_update("20260808_hotels_tours_menus")
        assert mod is UPDATES[0]
        assert "hotel" in mod.DESCRIPTION.lower() or "Sapa" in mod.DESCRIPTION


class TestSeedDataLoad:
    def test_hotels_and_tours_json_present(self):
        hotels = load_seed_rows("hotels.json")
        tours = load_seed_rows("tours.json")
        rooms = load_seed_rows("hotel_rooms.json")
        assert hotels[0]["slug"] == "sapa-cosy-hotel"
        assert {t["slug"] for t in tours} >= {
            "fansipan-day-trip",
            "cat-cat-village",
            "sapa-city-ham-rong",
        }
        assert all(r["hotel_id"] == 1 for r in rooms)

    def test_strip_primary_key(self):
        assert strip_primary_key({"id": 9, "slug": "x"}) == {"slug": "x"}


class TestScriptsLayout:
    def test_dev_probes_moved_out_of_scripts_root(self):
        root = Path(__file__).resolve().parent.parent / "scripts"
        assert (root / "seeds" / "apply.py").is_file()
        assert (root / "dev" / "mysql_smoke_probe.py").is_file()
        assert not (root / "mysql_smoke_probe.py").exists()
        assert not (root / "mail_live_probe.py").exists()
