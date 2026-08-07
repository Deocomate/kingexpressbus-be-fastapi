"""HTML sanitization at response time (nh3) — never on save.

Ports Laravel HtmlContentService: `default` (rich text) and `map` (allows iframes).
"""

from __future__ import annotations

import nh3

# Tags/attrs aligned with HtmlContentService::baseConfig (Symfony allowlists)
_DEFAULT_TAGS = {
    "u",
    "s",
    "sub",
    "sup",
    "del",
    "mark",
    "abbr",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "b",
    "i",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "colgroup",
    "col",
    "a",
    "div",
    "span",
    "img",
}

_DEFAULT_ATTRIBUTES = {
    "abbr": {"title"},
    "a": {"href", "target", "rel", "title"},
    "div": {"style", "class"},
    "span": {"style", "class"},
    "table": {"style"},
    "th": {"colspan", "rowspan", "style"},
    "td": {"colspan", "rowspan", "style"},
    "col": {"span"},
    "img": {"src", "alt", "width", "height", "title", "loading"},
}

_MAP_TAGS = _DEFAULT_TAGS | {"iframe"}
_MAP_ATTRIBUTES = {
    **_DEFAULT_ATTRIBUTES,
    "iframe": {
        "src",
        "width",
        "height",
        "frameborder",
        "allowfullscreen",
        "loading",
        "referrerpolicy",
        "style",
    },
}

_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def sanitize(html: str | None) -> str:
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_DEFAULT_TAGS,
        attributes=_DEFAULT_ATTRIBUTES,
        url_schemes=_URL_SCHEMES,
        link_rel=None,
    )


def sanitize_map(html: str | None) -> str:
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_MAP_TAGS,
        attributes=_MAP_ATTRIBUTES,
        url_schemes={"http", "https"},
        link_rel=None,
    )
