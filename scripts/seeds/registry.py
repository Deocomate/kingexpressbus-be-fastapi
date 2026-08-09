"""Registry of additive seed update modules (newest last)."""

from __future__ import annotations

from types import ModuleType

from scripts.seeds import u20260808_hotels_tours_menus, u20260809_route_menu_priorities

# Order = apply order when using --all.
UPDATES: list[ModuleType] = [
    u20260808_hotels_tours_menus,
    u20260809_route_menu_priorities,
]


def get_update(name: str) -> ModuleType:
    for mod in UPDATES:
        if mod.NAME == name:
            return mod
    known = ", ".join(m.NAME for m in UPDATES) or "(none)"
    raise KeyError(f"Unknown seed update {name!r}. Known: {known}")
