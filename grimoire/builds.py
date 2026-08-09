"""Load a target build and check that it refers to things it actually declares.

A build is a set of catalog references, never a list of names (AGENTS.md,
"Architectural principles"). This module is the part of that rule that runs: it
loads the file and refuses one whose internal references do not resolve.

The catalog itself does not exist yet, so references cannot be checked against it.
What can be checked now is the file's internal consistency and the presence of the
fields that make a later check possible: every entry's evidence, and the game build
the whole thing was verified against. Those are cheap to require now and impossible
to add retroactively to records already written without them.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# An entry whose identifier is not yet resolved is allowed, and is marked rather than
# omitted: a rune the build needs but cannot yet be named is a known gap, while a
# missing entry is indistinguishable from an oversight.
UNRESOLVED = "unresolved"


class BuildError(Exception):
    """A build file is missing something that makes it checkable."""


@dataclass(frozen=True)
class Build:
    build_id: str
    character: str
    weapon: str
    verified_against: str
    confidence: float
    skill_ids: tuple[str, ...]
    rune_ids: tuple[str, ...]
    disagreements: tuple[str, ...] = field(default=())

    @property
    def has_unresolved_references(self) -> bool:
        return UNRESOLVED in self.rune_ids or UNRESOLVED in self.skill_ids


def load(path: Path) -> Build:
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as err:
        raise BuildError(f"{path.name} is not valid TOML: {err}") from err

    meta = _require(raw, "meta", path)
    for key in ("build_id", "character", "weapon", "verified_against", "confidence"):
        if key not in meta:
            raise BuildError(f"{path.name}: [meta] is missing {key!r}")

    skills = raw.get("skills", [])
    runes = raw.get("runes", [])
    if not skills:
        raise BuildError(f"{path.name}: a build with no skills is not a build")

    for section, entries in (("skills", skills), ("runes", runes)):
        for n, entry in enumerate(entries):
            if "id" not in entry:
                raise BuildError(f"{path.name}: {section}[{n}] has no id")
            if "evidence" not in entry:
                # Without this the record cannot be aged, and a record that cannot be
                # aged silently becomes a guess as the game moves.
                raise BuildError(f"{path.name}: {section}[{n}] has no evidence")

    skill_ids = tuple(e["id"] for e in skills)
    _check_internal_references(raw, skill_ids, path)

    disagreements = tuple(
        f"{e.get('display', e['id'])}: {e['disagreement']}"
        for e in (*skills, *runes)
        if "disagreement" in e
    )

    return Build(
        build_id=meta["build_id"],
        character=meta["character"],
        weapon=meta["weapon"],
        verified_against=meta["verified_against"],
        confidence=float(meta["confidence"]),
        skill_ids=skill_ids,
        rune_ids=tuple(e["id"] for e in runes),
        disagreements=disagreements,
    )


def _check_internal_references(
    raw: dict, skill_ids: tuple[str, ...], path: Path
) -> None:
    """Anything naming a skill must name one the file declares.

    This is the whole point of storing references rather than names: a typo in a
    priority rule is a silent downgrade of the build's main damage source, and
    nothing else in the pipeline would ever notice.
    """
    focus = raw.get("priorities", {}).get("focus_skill")
    if focus and focus not in skill_ids:
        raise BuildError(
            f"{path.name}: priorities.focus_skill {focus!r} is not one of this "
            f"build's skills ({', '.join(skill_ids)})"
        )


def _require(raw: dict, key: str, path: Path) -> dict:
    if key not in raw:
        raise BuildError(f"{path.name}: missing [{key}]")
    return raw[key]
