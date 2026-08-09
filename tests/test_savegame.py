"""Tests for the save reader.

Every payload here is built in the test from bytes this file writes. None of it comes
from a real save: a real one is the player's own data and is never tracked, so a test
that depended on it could not run in any other checkout. Building the bytes also means
the expected value is stated rather than observed, which is what makes a failure
readable.

The byte layouts asserted here were confirmed against a real file first, including a
currencies payload whose decoded values matched the counts the game displays on screen.
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path

import pytest

from grimoire.savegame import (
    PayloadReader,
    SaveFormatError,
    decompress,
    discover,
    parse_name,
    read_identifiers,
)

TAG = b"\x00"


def payload(*parts: bytes) -> bytes:
    """A payload with its leading format tag."""
    return TAG + b"".join(parts)


def i32(value: int) -> bytes:
    return struct.pack("<i", value)


def text(value: str) -> bytes:
    """A string as BinaryWriter emits it: 7-bit length prefix, then UTF-8."""
    raw = value.encode("utf-8")
    assert len(raw) < 128, "the multi-byte length path has its own test"
    return bytes([len(raw)]) + raw


class TestName:
    def test_live_file_has_no_backup_number(self) -> None:
        parsed = parse_name(Path("playerProfile-0-currencies.savgs"))
        assert parsed is not None
        assert (parsed.slot, parsed.domain, parsed.backup) == (0, "currencies", None)
        assert parsed.is_live

    def test_backup_number_is_separated_from_the_domain(self) -> None:
        parsed = parse_name(Path("playerProfile-0-currencies-3.savgs"))
        assert parsed is not None
        assert (parsed.domain, parsed.backup) == ("currencies", 3)
        assert not parsed.is_live

    def test_a_domain_containing_no_digits_is_not_mistaken_for_a_backup(self) -> None:
        parsed = parse_name(Path("playerProfile-0-gamestatsmatchhistory.savgs"))
        assert parsed is not None
        assert parsed.domain == "gamestatsmatchhistory"
        assert parsed.backup is None

    @pytest.mark.parametrize(
        "name",
        [
            "notaprofile-0-currencies.savgs",  # wrong prefix
            "playerProfile-x-currencies.savgs",  # slot is not a number
            "playerProfile-0.savgs",  # no domain
            "playerProfile-0-currencies.txt",  # wrong suffix
        ],
    )
    def test_unrecognised_names_are_rejected_rather_than_guessed(
        self, name: str
    ) -> None:
        assert parse_name(Path(name)) is None


class TestDiscover:
    def test_live_file_sorts_before_its_backups(self, tmp_path: Path) -> None:
        for name in (
            "playerProfile-0-currencies-2.savgs",
            "playerProfile-0-currencies.savgs",
            "playerProfile-0-currencies-1.savgs",
            "unrelated.txt",
        ):
            (tmp_path / name).write_bytes(b"")
        found = discover(tmp_path)
        assert [f.backup for f in found] == [None, 1, 2]

    def test_an_empty_directory_yields_nothing_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        assert discover(tmp_path) == []


class TestReader:
    def test_the_tag_byte_is_skipped_so_int32s_land_on_their_boundaries(self) -> None:
        # Reading the tag as data is the failure this guards: it does not raise, it
        # returns integers shifted by one byte that look entirely plausible.
        reader = PayloadReader(payload(i32(148272), i32(115)))
        assert reader.read_int32() == 148272
        assert reader.read_int32() == 115

    def test_reading_without_skipping_the_tag_gives_a_different_and_wrong_answer(
        self,
    ) -> None:
        shifted = PayloadReader(payload(i32(148272)), skip_tag=False)
        assert shifted.read_int32() != 148272

    def test_negative_int32_round_trips(self) -> None:
        assert PayloadReader(payload(i32(-554425287))).read_int32() == -554425287

    def test_string_reads_its_declared_length(self) -> None:
        reader = PayloadReader(payload(text("WeaponBarbarian-01")))
        assert reader.read_string() == "WeaponBarbarian-01"

    def test_a_length_over_127_uses_the_continuation_bit(self) -> None:
        value = "x" * 200
        encoded = bytes([(200 & 0x7F) | 0x80, 200 >> 7]) + value.encode()
        assert PayloadReader(payload(encoded)).read_string() == value

    def test_mixed_stream_reads_in_order(self) -> None:
        reader = PayloadReader(payload(i32(21), text("Spellbreaker"), i32(7)))
        assert reader.read_int32() == 21
        assert reader.read_string() == "Spellbreaker"
        assert reader.read_int32() == 7
        assert reader.remaining == 0

    def test_a_truncated_int32_raises_instead_of_returning_a_short_read(self) -> None:
        with pytest.raises(SaveFormatError, match="int32 needs 4 bytes"):
            PayloadReader(payload(b"\x01\x02")).read_int32()

    def test_a_string_longer_than_the_buffer_raises(self) -> None:
        with pytest.raises(SaveFormatError, match="needs more than"):
            PayloadReader(payload(b"\x40" + b"short")).read_string()

    def test_an_unterminated_length_prefix_raises(self) -> None:
        with pytest.raises(SaveFormatError, match="truncated"):
            PayloadReader(payload(b"\x80\x80\x80")).read_length()

    def test_an_absurd_length_prefix_is_refused_rather_than_looping(self) -> None:
        with pytest.raises(SaveFormatError, match="over 5 bytes"):
            PayloadReader(payload(b"\x80" * 6)).read_length()


class TestDecompress:
    def test_reads_a_gzip_payload(self, tmp_path: Path) -> None:
        path = tmp_path / "playerProfile-0-currencies.savgs"
        path.write_bytes(gzip.compress(payload(i32(148272))))
        assert decompress(path) == payload(i32(148272))

    def test_a_file_that_is_not_gzip_fails_with_its_name(self, tmp_path: Path) -> None:
        path = tmp_path / "playerProfile-0-currencies.savgs"
        path.write_bytes(b"not gzip at all")
        with pytest.raises(SaveFormatError, match="playerProfile-0-currencies.savgs"):
            decompress(path)


class TestIdentifiers:
    def test_finds_identifiers_across_an_unknown_header(self) -> None:
        data = payload(
            b"\x15\x00\x00\x00\x01\x1f\x00\x00\x00",  # header, layout not yet decoded
            text("WeaponBarbarian-01"),
            text("WeaponPyromancer-01"),
            text("WeaponHoundMaster-01"),
        )
        assert read_identifiers(data) == [
            "WeaponBarbarian-01",
            "WeaponPyromancer-01",
            "WeaponHoundMaster-01",
        ]

    def test_a_payload_of_only_numbers_yields_nothing(self) -> None:
        # The currencies domain holds no identifiers, and an empty result is the
        # correct answer rather than a failure.
        assert (
            read_identifiers(payload(*(i32(n) for n in (148272, 115, 101, 82)))) == []
        )

    def test_a_format_change_reads_as_empty_rather_than_as_wrong_data(self) -> None:
        # The property that makes this scan safe to ship before the record layouts are
        # understood: bytes that are not this format produce no identifiers, so a
        # caller sees nothing instead of seeing plausible nonsense.
        assert read_identifiers(payload(bytes(range(128, 256)))) == []
