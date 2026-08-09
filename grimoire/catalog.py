"""Join the two vocabularies a record can be written in, and refuse to invent a join.

Every source speaks one of two languages. A save file and the game's own content ids
say ``RuneExtraCritChance``; a guide, a spreadsheet and the interface say "Vulnerable
Target". Neither can be checked against the other until something states the pair, and
that something has to be evidence rather than a rule, because the pairs are sometimes
obvious (``RuneCriticalMastery`` is "Critical Mastery") and sometimes unrelated. A
resolver built on the resemblance would be right often enough to be relied on and wrong
precisely where the names diverge.

So there is no fuzzy matching here and no nearest match. A name either has a record or
it does not, and not having one is an answer the caller can act on: the failure names
the missing thing and the file that would fix it.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

# One file per kind, and the kind is the table name inside it. Adding a kind means
# adding a file, which keeps a record's kind out of the record itself where it would
# be one more field to get wrong.
KINDS = ("weapon", "rune")

REQUIRED_FIELDS = ("id", "display", "confidence", "evidence")

EVIDENCE_TYPES = ("game_asset", "game_screen", "community_source", "measured")


class CatalogError(Exception):
    """A catalog file is unusable, or a reference into it does not resolve."""


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    display: str
    kind: str
    confidence: float
    evidence_type: str


class Catalog:
    """Resolution in both directions, with the failure naming what is missing."""

    def __init__(self, entries: list[CatalogEntry]) -> None:
        self._by_id = {e.id: e for e in entries}
        self._by_display = {e.display: e for e in entries}

    def __len__(self) -> int:
        return len(self._by_id)

    def entry(self, identifier: str) -> CatalogEntry:
        found = self._by_id.get(identifier)
        if found is None:
            raise CatalogError(
                f"catalog miss: no record for id {identifier!r}. Add one to the "
                f"matching file under packs/<game>/catalog/ with its evidence."
            )
        return found

    def id_for(self, display: str, *, kind: str | None = None) -> str:
        """The internal identifier a displayed name refers to.

        The kind is optional and is checked rather than used to search, since a name
        that resolves to the wrong kind is a mistake in the caller worth reporting
        instead of a lookup worth narrowing.
        """
        found = self._by_display.get(display)
        if found is None:
            raise CatalogError(
                f"catalog miss: no record for the name {display!r}. Add one to the "
                f"matching file under packs/<game>/catalog/ with its evidence."
            )
        if kind is not None and found.kind != kind:
            raise CatalogError(
                f"{display!r} is a {found.kind} in the catalog, asked for as a {kind}"
            )
        return found.id

    def display_for(self, identifier: str) -> str:
        return self.entry(identifier).display

    def missing(self, identifiers: list[str]) -> list[str]:
        """Which of these identifiers have no record, in the order given.

        Reporting the whole set at once rather than dying on the first one, because a
        build that is missing four records should say so in one pass instead of over
        four runs.
        """
        return [i for i in identifiers if i not in self._by_id]


def load(directory: Path) -> Catalog:
    """Every catalog file in a pack's catalog directory."""
    entries: list[CatalogEntry] = []
    for kind in KINDS:
        path = directory / f"{kind}s.toml"
        if not path.exists():
            continue
        entries.extend(_read_file(path, kind))
    _refuse_duplicates(entries, directory)
    return Catalog(entries)


def _read_file(path: Path, kind: str) -> list[CatalogEntry]:
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as err:
        raise CatalogError(f"{path.name} is not valid TOML: {err}") from err

    entries = []
    for index, record in enumerate(raw.get(kind, [])):
        for field in REQUIRED_FIELDS:
            if field not in record:
                raise CatalogError(f"{path.name}: {kind}[{index}] has no {field}")
        evidence_type = record["evidence"].get("type")
        if evidence_type not in EVIDENCE_TYPES:
            # An unrecognised class cannot be weighed against the others later, which
            # is the only reason a record carries its evidence in the first place.
            raise CatalogError(
                f"{path.name}: {kind}[{index}] has evidence type "
                f"{evidence_type!r}, not one of {', '.join(EVIDENCE_TYPES)}"
            )
        entries.append(
            CatalogEntry(
                id=record["id"],
                display=record["display"],
                kind=kind,
                confidence=float(record["confidence"]),
                evidence_type=evidence_type,
            )
        )
    return entries


def _refuse_duplicates(entries: list[CatalogEntry], directory: Path) -> None:
    """Two records claiming one name is a contradiction, not a preference.

    Whichever the loader kept would be arbitrary, and the one it dropped would go on
    being cited in a build that now resolves to something else.
    """
    for attribute in ("id", "display"):
        seen: dict[str, CatalogEntry] = {}
        for entry in entries:
            key = getattr(entry, attribute)
            clash = seen.get(key)
            if clash is not None:
                raise CatalogError(
                    f"{directory}: {attribute} {key!r} is claimed by both "
                    f"{clash.kind} {clash.id} and {entry.kind} {entry.id}"
                )
            seen[key] = entry
