"""Unit tests for additive seed helpers (no DB required)."""

from pathlib import Path

from scripts.seeds.common import load_seed_rows, strip_primary_key
from scripts.seeds.registry import UPDATES, get_update


class TestAdditiveSeedRegistry:
    def test_hotels_tours_update_is_registered(self):
        mod = get_update("20260808_hotels_tours_menus")
        assert mod is UPDATES[0]
        assert "hotel" in mod.DESCRIPTION.lower() or "Sapa" in mod.DESCRIPTION

    def test_route_menu_priorities_update_is_registered(self):
        mod = get_update("20260809_route_menu_priorities")
        assert mod is UPDATES[1]
        assert "priority" in mod.DESCRIPTION.lower() or "corridor" in mod.DESCRIPTION.lower()


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

    def test_route_menu_seed_priorities_and_urls(self):
        routes = {r["slug"]: r["priority"] for r in load_seed_rows("routes.json")}
        assert routes["ha-noi-sapa"] > routes["sapa-ha-noi"] > routes["ha-noi-ninh-binh"]
        assert routes["ha-noi-ninh-binh"] > routes["ha-noi-hue"] > routes["ha-noi-da-nang"]
        assert routes["ha-noi-hoi-an"] > routes["ninh-binh-ha-noi"]
        assert routes["hoi-an-ha-noi"] > routes["ha-noi-phong-nha"]
        assert routes["ha-noi-phong-nha"] > routes["sapa-ninh-binh"]

        menus = load_seed_rows("menus.json")
        route_menus = [
            m for m in menus if (m.get("url") or "").startswith("/tuyen-duong/")
        ]
        ordered = sorted(route_menus, key=lambda m: (-m["priority"], m["id"]))
        assert [m["url"] for m in ordered[:4]] == [
            "/tuyen-duong/ha-noi-sapa",
            "/tuyen-duong/sapa-ha-noi",
            "/tuyen-duong/ha-noi-ninh-binh",
            "/tuyen-duong/ha-noi-hue",
        ]
        assert len(route_menus) >= 12


class TestScriptsLayout:
    def test_dev_probes_moved_out_of_scripts_root(self):
        root = Path(__file__).resolve().parent.parent / "scripts"
        assert (root / "seeds" / "apply.py").is_file()
        assert (root / "dev" / "mysql_smoke_probe.py").is_file()
        assert not (root / "mysql_smoke_probe.py").exists()
        assert not (root / "mail_live_probe.py").exists()
