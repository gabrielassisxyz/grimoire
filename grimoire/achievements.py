"""Read the achievement domain: what is complete, and how far along the rest is.

The domain that was holding back two separate answers. Rune ownership stops at the skill
tree, because sixty-two catalogued runes unlock through an achievement instead and the
tree says nothing about those. Runic power capacity is a range for the same reason,
half of it granted by achievements, so a build between the bounds gets no verdict.
Both need this file and nothing else.

Three collections, written back to back, and the install names all three. The type
``PlayerProfileAchievementProgression`` in ``il2cpp_data/Metadata/global-metadata.dat``
lists its fields in the order the payload writes them: ``achievements``,
``completedToView``, ``completedToNotify``. The first holds one record per achievement
with its progress and, once complete, when.

``completedToNotify`` is a queue the game drains as it shows the popup, so it carries a
completion for exactly the one write that follows earning it. Reading it as a
permanently empty tail made the reader refuse a good save for the span between earning
an achievement and being told about it, which is the span this tool is most worth
consulting in.

``completedToView`` is what the completed records are checked against, and that check is
worth more than the field's name suggests: a layout wrong by one field consumes the
stream just as willingly and yields plausible records, but it will not also yield a
second list that agrees with them. The name says queue while the data says mirror,
holding every completion including long-earned ones across ten consecutive writes. Which
it is has not been settled, so equality is required and a profile where it ever drains
will say so rather than pass quietly.

Progress is a fraction rather than a count. An achievement at 0.727686 is at that share
of its target, so the target itself is not in the save and the number cannot be turned
back into "how many enemies left" without a source for what the target is.
"""

from __future__ import annotations

from collections import Counter
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
    _refuse_repeats("the progress records", [a.achievement_id for a in achievements])
    completed = {a.achievement_id for a in achievements if a.completed}
    _check_against_completed_list(
        completed, _read_string_collection(reader, "completedToView")
    )
    _check_notification_queue(
        completed, _read_string_collection(reader, "completedToNotify")
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


def _read_string_collection(reader: PayloadReader, what: str) -> list[str]:
    count = _read_collection_header(reader, what)
    entries = [reader.read_string() for _ in range(count)]
    _refuse_repeats(what, entries)
    return entries


def _refuse_repeats(what: str, identifiers: list[str]) -> None:
    """Each collection names an achievement once, and a repeat is not a profile.

    The checks below compare sets, which cannot see a repeat: two identical completed
    records agree perfectly with a list that names the achievement once. What the repeat
    reaches is the runic power total, where a grant counted twice is a build reported as
    fitting a ceiling it does not fit.
    """
    counted = Counter(identifiers)
    repeated = sorted(i for i, times in counted.items() if times > 1)
    if repeated:
        raise SaveFormatError(
            f"achievements: {what} names {repeated[:3]} more than once, so this is not "
            "one entry per achievement"
        )


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


def _check_against_completed_list(completed: set[str], to_view: list[str]) -> None:
    """``completedToView`` is made to agree with the records, which earns the layout.

    See the module docstring for why equality is required of a field whose name says
    queue.
    """
    listed = set(to_view)
    if completed != listed:
        only_records = sorted(completed - listed)[:3]
        only_list = sorted(listed - completed)[:3]
        raise SaveFormatError(
            "achievements: the completed set read from the records does not match the "
            f"one the file lists separately. In records only: {only_records}. In the "
            f"list only: {only_list}"
        )


def _check_notification_queue(completed: set[str], to_notify: list[str]) -> None:
    """``completedToNotify``: the completions the game has not shown a popup for yet.

    Nothing consumes it, so it is read for what it can falsify rather than for what it
    holds. A queued achievement the records do not have as complete means the stream has
    drifted, which is what requiring this collection to be empty used to catch before
    the field had a name.
    """
    unknown = sorted(set(to_notify) - completed)
    if unknown:
        raise SaveFormatError(
            f"achievements: the notification queue holds {unknown[:3]}, which the "
            "records do not have as complete, so the three collections are not "
            "describing one profile"
        )
