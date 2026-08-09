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

A record's evidence is a list rather than a single entry, because a pair can rest on
two independent readings and that is exactly what separates a record worth trusting
from one worth re-checking. Each entry states the fields its class needs to be checked
by someone who was not there.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# One file per kind, and the kind is the table name inside it. Adding a kind means
# adding a file, which keeps a record's kind out of the record itself where it would
# be one more field to get wrong.
KINDS = ("weapon", "rune")

REQUIRED_FIELDS = ("id", "display", "confidence", "evidence")

# What each class of evidence must state for a stranger to be able to check it. These
# are the project's own provenance rules moved from prose into the loader: a rule that
# lives only in a document is a rule that is already half broken by the time anyone
# notices, and provenance is the one thing publication cannot repair afterwards.
EVIDENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "game_asset": ("asset_path", "build_id"),
    "game_screen": ("fixture", "window", "build_id"),
    # A save reading names the write it came from, not just the file: the ten slots of
    # a domain are a ring the game writes round, so a slot alone identifies a position
    # that has since been overwritten, while the counter identifies the payload.
    "save_file": ("domain", "slot", "write_counter", "build_id"),
    "community_source": ("url", "retrieved", "game_version"),
    "measured": ("procedure", "before", "after"),
}


class CatalogError(Exception):
    """A catalog file is unusable, or a reference into it does not resolve."""


@dataclass(frozen=True)
class Evidence:
    type: str
    detail: Mapping[str, str]


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    display: str
    kind: str
    confidence: float
    evidence: tuple[Evidence, ...]


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
        instead of a lookup worth narrowing. A displayed name is unique across every
        kind, which the loader enforces, so there is nothing for a kind to narrow.
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

    records = raw.get(kind, [])
    if not isinstance(records, list):
        raise CatalogError(f"{path.name}: {kind} must be a table array, [[{kind}]]")
    return [
        _read_record(f"{path.name}: {kind}[{index}]", kind, record)
        for index, record in enumerate(records)
    ]


def _read_record(where: str, kind: str, record: object) -> CatalogEntry:
    if not isinstance(record, dict):
        raise CatalogError(f"{where} is not a table")
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise CatalogError(f"{where} has no {field}")
    return CatalogEntry(
        id=_read_text(where, record, "id"),
        display=_read_text(where, record, "display"),
        kind=kind,
        confidence=_read_confidence(where, record),
        evidence=_read_evidence(where, record),
    )


def _read_text(where: str, record: Mapping[str, object], field: str) -> str:
    value = record[field]
    if not isinstance(value, str) or not value:
        raise CatalogError(f"{where}: {field} must be a non-empty string")
    return value


def _read_confidence(where: str, record: Mapping[str, object]) -> float:
    value = record["confidence"]
    # A bool is an int in Python, so confidence = true would otherwise read as 1.0,
    # which is the highest claim the schema can make and the least deliberate one.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CatalogError(f"{where}: confidence must be a number, got {value!r}")
    if not 0.0 <= value <= 1.0:
        raise CatalogError(f"{where}: confidence {value} is outside 0.0 to 1.0")
    return float(value)


def _read_evidence(where: str, record: Mapping[str, object]) -> tuple[Evidence, ...]:
    listed = record["evidence"]
    if not isinstance(listed, list) or not listed:
        raise CatalogError(f"{where}: evidence must be a non-empty array of tables")
    return tuple(
        _read_one_evidence(f"{where} evidence[{index}]", entry)
        for index, entry in enumerate(listed)
    )


def _read_one_evidence(where: str, entry: object) -> Evidence:
    if not isinstance(entry, dict):
        raise CatalogError(f"{where} is not a table")
    evidence_type = entry.get("type")
    if evidence_type not in EVIDENCE_FIELDS:
        # An unrecognised class cannot be weighed against the others later, which is
        # the only reason a record carries its evidence in the first place.
        raise CatalogError(
            f"{where} has type {evidence_type!r}, not one of "
            f"{', '.join(EVIDENCE_FIELDS)}"
        )
    detail = {key: value for key, value in entry.items() if key != "type"}
    for key, value in detail.items():
        # Everything is spelled as a string, including dates and build ids, so that an
        # unquoted date or a version that looks numeric cannot change type under the
        # reader depending on how it happened to be written.
        if not isinstance(value, str) or not value:
            raise CatalogError(f"{where}: {key} must be a non-empty string")
    absent = [f for f in EVIDENCE_FIELDS[evidence_type] if f not in detail]
    if absent:
        raise CatalogError(
            f"{where} is {evidence_type} and states no {', no '.join(absent)}"
        )
    return Evidence(type=evidence_type, detail=detail)


def _refuse_duplicates(entries: list[CatalogEntry], directory: Path) -> None:
    """Two records claiming one name is a contradiction, not a preference.

    Whichever the loader kept would be arbitrary, and the one it dropped would go on
    being cited in a build that now resolves to something else. Names collide across
    kinds as readily as within one, so the check spans the whole catalog.
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
