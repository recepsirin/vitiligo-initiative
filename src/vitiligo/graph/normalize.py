"""Entity name normalization for graph deduplication."""

from __future__ import annotations

import re

from vitiligo.storage.models import EntityKind, RelationKind

VITILIGO_ENTITY_NAME = "Vitiligo"
VITILIGO_ENTITY_KEY = "vitiligo"

_VALID_ENTITY_KINDS = frozenset(k.value for k in EntityKind)
_VALID_RELATIONS = frozenset(k.value for k in RelationKind)

_ENTITY_KIND_ALIASES: dict[str, EntityKind] = {
    "gene": EntityKind.TARGET,
    "protein": EntityKind.TARGET,
    "medication": EntityKind.DRUG,
    "compound": EntityKind.DRUG,
    "condition": EntityKind.DISEASE,
}


def normalize_entity_key(name: str) -> str:
    """Map a display name to a stable deduplication key."""
    key = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())
    return key.strip("_")[:120] or "unknown"


def coerce_entity_kind(raw: str | None) -> EntityKind | None:
    if not raw:
        return None
    text = raw.strip().lower()
    if text in _VALID_ENTITY_KINDS:
        return EntityKind(text)
    return _ENTITY_KIND_ALIASES.get(text)


def coerce_relation_kind(raw: str | None) -> RelationKind | None:
    if not raw:
        return None
    text = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if text in _VALID_RELATIONS:
        return RelationKind(text)
    return None
