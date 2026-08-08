"""Map website domain/ORM objects to public API schemas."""

from __future__ import annotations

from app.application.catalog import html_sanitize
from app.infrastructure.persistence.models import Menu, WebProfile
from app.presentation.schemas.public import MenuNodeOut, WebProfileOut


def web_profile_to_out(profile: WebProfile) -> WebProfileOut:
    return WebProfileOut(
        id=profile.id,
        profile_name=profile.profile_name,
        online_payment_enabled=bool(profile.online_payment_enabled),
        title=profile.title,
        description=profile.description,
        logo_url=profile.logo_url,
        favicon_url=profile.favicon_url,
        email=profile.email,
        phone=profile.phone,
        hotline=profile.hotline,
        whatsapp=profile.whatsapp,
        address=profile.address,
        facebook_url=profile.facebook_url,
        zalo_url=profile.zalo_url,
        map_embedded=html_sanitize.sanitize_map(profile.map_embedded),
        policy_content=html_sanitize.sanitize(profile.policy_content),
        introduction_content=html_sanitize.sanitize(profile.introduction_content),
    )


def build_menu_tree(menus: list[Menu]) -> list[MenuNodeOut]:
    by_parent: dict[int, list[Menu]] = {}
    for m in menus:
        pid = m.parent_id if m.parent_id is not None else -1
        by_parent.setdefault(pid, []).append(m)

    def children_of(parent_id: int, depth: int = 0) -> list[MenuNodeOut]:
        if depth > 4:
            return []
        nodes = sorted(by_parent.get(parent_id, []), key=lambda x: (-x.priority, x.id))
        return [
            MenuNodeOut(
                id=m.id,
                name=m.name,
                url=m.url,
                parent_id=m.parent_id,
                priority=m.priority,
                type=m.type,
                related_id=m.related_id,
                children=children_of(m.id, depth + 1),
            )
            for m in nodes
        ]

    return children_of(-1)
