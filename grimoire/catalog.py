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

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# One file per kind, and the kind is the table name inside it. Adding a kind means
# adding a file, which keeps a record's kind out of the record itself where it would
# be one more field to get wrong.
KINDS = ("weapon", "rune", "achievement")

REQUIRED_FIELDS = ("id", "display", "confidence", "evidence")

# Fields a kind cannot do without, beyond the ones every record carries. A rune with no
# cost would be counted as free by the budget check and a rune with no slot as belonging
# to no section, and both read as an answer rather than as a gap.
REQUIRED_PER_KIND = {
    "rune": ("slot", "runic_power_cost"),
    # Stated on every achievement record rather than defaulted, for the reason a
    # rune states its cost: a missing number reads as zero, and zero is a claim.
    "achievement": ("grants_runic_power",),
}

SLOTS = ("tenacity", "versatility")

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
    # The skill tree node that grants this, where one does. It is what makes ownership
    # decidable from the save rather than asked of the player: the save lists the nodes
    # bought, so a record naming its node can be answered, and a record without one can
    # only be reported as unknown. Optional because most kinds have no such node.
    unlocked_by: str | None = None
    # The achievement a rune unlocks through, spelled the way the save spells it rather
    # than the way the install does, because the save is what this is matched against.
    # The two vocabularies overlap without being the same set, so the value here is a
    # translation the extractor documents and a save was used to falsify.
    unlocked_by_achievement: str | None = None
    # The numeric parameters the installed game stores for this record, in its own
    # order. Kept apart from the prose effect on purpose: the prose comes from whichever
    # source described the rune and the numbers are read from the build itself, so a
    # source that has fallen behind a patch shows up as the two disagreeing rather than
    # as one silently overwriting the other.
    parameters: tuple[float, ...] = ()
    slot: str | None = None
    # Signed, because one rune raises the runic power ceiling rather than spending from
    # it and is written as a negative cost. Summing magnitudes would reject the build
    # that rune exists to make possible.
    runic_power_cost: int = 0
    # How much runic power completing this achievement adds to the ceiling. The
    # game grants it through five of them, and which five is not readable from
    # the install, so it is a community claim carried on a record with its
    # source rather than a list buried in the code that reads the save.
    grants_runic_power: int = 0


class Catalog:
    """Resolution in both directions, with the failure naming what is missing."""

    def __init__(self, entries: list[CatalogEntry]) -> None:
        self._by_id = {e.id: e for e in entries}
        self._by_display = {e.display: e for e in entries}

    def __len__(self) -> int:
        return len(self._by_id)

    def entries_of_kind(self, kind: str) -> list[CatalogEntry]:
        return [e for e in self._by_id.values() if e.kind == kind]

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
    for field in REQUIRED_FIELDS + REQUIRED_PER_KIND.get(kind, ()):
        if field not in record:
            raise CatalogError(f"{where} has no {field}")
    if "unlocked_by" in record and "unlocked_by_achievement" in record:
        # Ownership answers from the node and never looks at the achievement, so a
        # record naming both would report a rune as missing while the achievement that
        # granted it sits completed in the save. Whether the game has runes with two
        # routes is unestablished, and a record that asserts one is asking for a reading
        # nothing here implements.
        raise CatalogError(
            f"{where} names both unlocked_by and unlocked_by_achievement, and only one "
            "of the two decides ownership. Keep the route the save can prove."
        )
    return CatalogEntry(
        id=_read_text(where, record, "id"),
        display=_read_text(where, record, "display"),
        kind=kind,
        confidence=_read_confidence(where, record),
        evidence=_read_evidence(where, record),
        unlocked_by=_read_optional_text(where, record, "unlocked_by"),
        unlocked_by_achievement=_read_optional_text(
            where, record, "unlocked_by_achievement"
        ),
        parameters=_read_parameters(where, record),
        slot=_read_slot(where, record),
        runic_power_cost=_read_whole_number(where, record, "runic_power_cost"),
        grants_runic_power=_read_whole_number(where, record, "grants_runic_power"),
    )


def _read_slot(where: str, record: Mapping[str, object]) -> str | None:
    slot = _read_optional_text(where, record, "slot")
    if slot is not None and slot not in SLOTS:
        raise CatalogError(f"{where}: slot {slot!r} is not one of {', '.join(SLOTS)}")
    return slot


def _read_whole_number(where: str, record: Mapping[str, object], field: str) -> int:
    value = record.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CatalogError(f"{where}: {field} must be a whole number")
    return value


def _read_parameters(where: str, record: Mapping[str, object]) -> tuple[float, ...]:
    values = record.get("parameters", [])
    if not isinstance(values, list):
        raise CatalogError(f"{where}: parameters must be an array of numbers")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise CatalogError(f"{where}: parameter {value!r} is not a number")
        # TOML has nan and inf and they are floats, so the check above admits them.
        # A non-finite parameter is not a magnitude the effect engine can use; it is
        # a number-shaped hole that would propagate through arithmetic unnoticed.
        if not math.isfinite(value):
            raise CatalogError(f"{where}: parameter {value!r} is not a finite number")
    return tuple(float(v) for v in values)


def _read_optional_text(
    where: str, record: Mapping[str, object], field: str
) -> str | None:
    if field not in record:
        return None
    return _read_text(where, record, field)


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
