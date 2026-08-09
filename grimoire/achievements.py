"""Read the achievement domain: what is complete, and how far along the rest is.

The domain that was holding back two separate answers. Rune ownership stops at the skill
tree, because sixty-two catalogued runes unlock through an achievement instead and the
tree says nothing about those. Runic power capacity is a range for the same reason,
half of it granted by achievements, so a build between the bounds gets no verdict.
Both need this file and nothing else.

Three collections, written back to back. The first holds one record per achievement with
its progress and, once complete, when. The second lists the completed ones by name. That
is redundant with the first and is exactly why it is worth reading: the two must agree,
and a layout wrong by one field will not produce two views that happen to match. The
third is empty in every profile seen so far, and what it would hold is unknown, so it is
read and required to be empty rather than skipped.

Progress is a fraction rather than a count. An achievement at 0.727686 is at that share
of its target, so the target itself is not in the save and the number cannot be turned
back into "how many enemies left" without a source for what the target is.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.savegame import PayloadReader, SaveFormatError

# Ticks per second in a .NET DateTime, whose epoch is the start of year 1. Only used to
# tell a real completion stamp from the zero an unfinished achievement carries; the
# calendar date is not something this needs to compute.
_UNSET_TIMESTAMP = 0

# Each record opens with five bytes that were zero in all 431 records of every profile
# read. The skill tree domain opens the same way, and there too what those five divide
# into is not decidable from zeros alone.
_UNIDENTIFIED_RECORD_PREFIX = 5

_COLLECTION_MARKER = 1


@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    progress: float
    completed: bool


def read_achievements(data: bytes) -> list[Achievement]:
    """Every achievement with its progress, in the file's own order."""
    reader = PayloadReader(data)
    reader.read_int32()  # write counter, see savegame.read_write_counter
    achievements = _read_progress(reader)
    _check_against_completed_list(achievements, _read_string_collection(reader))

    trailing = _read_string_collection(reader)
    if trailing:
        raise SaveFormatError(
            f"achievements: the third collection held {len(trailing)} entries where "
            "every profile read so far has it empty, so its meaning is unestablished "
            "and reading past it would be guessing"
        )
    if reader.remaining:
        raise SaveFormatError(
            f"achievements: {reader.remaining} bytes remain after three collections, "
            "so the record layout does not match this payload"
        )
    return achievements


def _read_progress(reader: PayloadReader) -> list[Achievement]:
    count = _read_collection_header(reader, "progress")
    achievements = []
    for index in range(count):
        try:
            reader.skip(_UNIDENTIFIED_RECORD_PREFIX)
            achievement_id = reader.read_string()
            progress = reader.read_float32()
            completed_at = reader.read_int64()
        except (SaveFormatError, UnicodeDecodeError) as err:
            raise SaveFormatError(
                f"achievements: record {index} of {count}: {err}"
            ) from err
        achievements.append(
            Achievement(
                achievement_id=achievement_id,
                progress=progress,
                completed=completed_at != _UNSET_TIMESTAMP,
            )
        )
    return achievements


def _read_string_collection(reader: PayloadReader) -> list[str]:
    count = _read_collection_header(reader, "string list")
    return [reader.read_string() for _ in range(count)]


def _read_collection_header(reader: PayloadReader, what: str) -> int:
    marker = reader.read_byte()
    if marker != _COLLECTION_MARKER:
        raise SaveFormatError(
            f"achievements: {what} expected collection marker "
            f"{_COLLECTION_MARKER}, got {marker}"
        )
    count = reader.read_int32()
    if count < 0:
        raise SaveFormatError(f"achievements: {what} has negative count {count}")
    return count


def _check_against_completed_list(
    achievements: list[Achievement], completed: list[str]
) -> None:
    """The file states its completed set twice, so the two are made to agree.

    This is the check that earns trust in the layout. A record layout wrong by one
    field consumes the stream just as willingly and yields plausible records; it would
    not also yield a second list that matches them.
    """
    from_records = {a.achievement_id for a in achievements if a.completed}
    from_list = set(completed)
    if from_records != from_list:
        only_records = sorted(from_records - from_list)[:3]
        only_list = sorted(from_list - from_records)[:3]
        raise SaveFormatError(
            "achievements: the completed set read from the records does not match the "
            f"one the file lists separately. In records only: {only_records}. In the "
            f"list only: {only_list}"
        )
