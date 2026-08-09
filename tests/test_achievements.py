"""The achievement domain reader.

Hermetic: every payload here is built byte by byte rather than read from a save, because
a save is the player's own data and is never tracked. Building them also means the
malformed cases can be constructed exactly, which is most of what is worth testing in a
binary reader.
"""

from __future__ import annotations

import struct

import pytest

from grimoire.achievements import read_achievements
from grimoire.savegame import SaveFormatError

TAG = b"\x00"
MARKER = b"\x01"


def text(value: str) -> bytes:
    """A .NET BinaryWriter string: 7-bit encoded length, then UTF-8."""
    raw = value.encode("utf-8")
    if len(raw) > 127:
        raise ValueError("the test builder only writes short strings")
    return bytes([len(raw)]) + raw


def record(achievement_id: str, progress: float, completed_at: int) -> bytes:
    return (
        b"\x00" * 5
        + text(achievement_id)
        + struct.pack("<f", progress)
        + struct.pack("<q", completed_at)
    )


def collection(entries: list[bytes]) -> bytes:
    return MARKER + struct.pack("<i", len(entries)) + b"".join(entries)


def payload(
    records: list[bytes], completed: list[str], trailing: list[str] | None = None
) -> bytes:
    return (
        TAG
        + struct.pack("<i", 1026)
        + collection(records)
        + collection([text(c) for c in completed])
        + collection([text(t) for t in trailing or []])
    )


DONE_AT = 639_000_000_000_000_000


class TestReadingAProfile:
    def test_progress_and_completion_come_back_per_achievement(self) -> None:
        data = payload(
            [record("Finished", 1.0, DONE_AT), record("Partway", 0.727686, 0)],
            ["Finished"],
        )
        finished, partway = read_achievements(data)
        assert (finished.achievement_id, finished.completed) == ("Finished", True)
        assert partway.completed is False
        assert partway.progress == pytest.approx(0.727686)

    def test_completion_is_the_timestamp_and_not_the_progress(self) -> None:
        # Progress reaching 1.0 without a stamp is the state the game writes on the
        # tick before it credits an achievement. Reading completion off the fraction
        # would report it as earned slightly early, which for runic power means
        # claiming a point the player cannot yet spend.
        data = payload([record("AtTheLine", 1.0, 0)], [])
        assert read_achievements(data)[0].completed is False

    def test_an_empty_profile_reads_as_no_achievements(self) -> None:
        assert read_achievements(payload([], [])) == []


class TestWhatMakesTheLayoutTrustworthy:
    def test_a_completed_set_that_disagrees_with_the_records_is_refused(self) -> None:
        # The file states its completed set twice and this is why that redundancy is
        # read rather than skipped. A layout wrong by one field still yields plausible
        # records; it does not also yield a second list that agrees with them.
        data = payload([record("Finished", 1.0, DONE_AT)], ["SomethingElse"])
        with pytest.raises(SaveFormatError, match="does not match"):
            read_achievements(data)

    def test_bytes_left_over_are_fatal(self) -> None:
        with pytest.raises(SaveFormatError, match="bytes remain"):
            read_achievements(payload([], []) + b"\x00\x00")

    def test_a_third_collection_with_entries_stops_the_read(self) -> None:
        # It is empty in every profile seen, so anything in it means the shape is not
        # what this understands, and carrying on would be reading past an unknown.
        with pytest.raises(SaveFormatError, match="third collection"):
            read_achievements(payload([], [], ["Unexpected"]))

    def test_a_missing_collection_marker_is_refused(self) -> None:
        data = bytearray(payload([record("A", 1.0, DONE_AT)], ["A"]))
        data[5] = 2
        with pytest.raises(SaveFormatError, match="collection marker"):
            read_achievements(bytes(data))

    def test_a_negative_record_count_is_refused(self) -> None:
        data = TAG + struct.pack("<i", 1026) + MARKER + struct.pack("<i", -1)
        with pytest.raises(SaveFormatError, match="negative count"):
            read_achievements(data)

    def test_a_truncated_record_names_which_one(self) -> None:
        data = payload(
            [record("A", 1.0, DONE_AT), record("B", 1.0, DONE_AT)], ["A", "B"]
        )
        with pytest.raises(SaveFormatError, match="record 1 of 2"):
            read_achievements(data[:-20])

    def test_a_progress_value_that_is_not_a_number_is_refused(self) -> None:
        # Four bytes read at a drifted offset decode as a denormal or a nan far more
        # often than as a plausible fraction, so this is where a layout that has moved
        # says so instead of returning a value that only looks wrong much later.
        data = payload([record("A", float("nan"), DONE_AT)], ["A"])
        with pytest.raises(SaveFormatError, match="not a number"):
            read_achievements(data)
