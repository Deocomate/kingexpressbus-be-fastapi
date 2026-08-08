"""Additive, production-safe seed updates.

Unlike ``scripts/seed.py`` (truncate + full reload, local/dev only), modules
under this package insert missing catalog rows by natural keys (slug / url)
and never truncate booking or user tables.

Usage (from backend root, with .venv active)::

    python -m scripts.seeds.apply --list
    python -m scripts.seeds.apply 20260808_hotels_tours_menus
    python -m scripts.seeds.apply --all
    python -m scripts.seeds.apply 20260808_hotels_tours_menus --update
    python -m scripts.seeds.apply 20260808_hotels_tours_menus --dry-run
"""
