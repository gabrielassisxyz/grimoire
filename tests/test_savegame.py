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
import os
import struct
from pathlib import Path

import pytest

from grimoire.savegame import (
    PayloadReader,
    SaveFormatError,
    decompress,
    discover,
    newest_per_domain,
    parse_name,
    read_identifiers,
    read_write_counter,
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
    def test_the_unsuffixed_name_is_rotation_zero(self) -> None:
        parsed = parse_name(Path("playerProfile-0-currencies.savgs"))
        assert parsed is not None
        assert (parsed.profile, parsed.domain, parsed.rotation) == (0, "currencies", 0)

    def test_rotation_number_is_separated_from_the_domain(self) -> None:
        parsed = parse_name(Path("playerProfile-0-currencies-3.savgs"))
        assert parsed is not None
        assert (parsed.domain, parsed.rotation) == ("currencies", 3)

    def test_a_domain_containing_no_digits_is_not_mistaken_for_a_rotation(self) -> None:
        parsed = parse_name(Path("playerProfile-0-gamestatsmatchhistory.savgs"))
        assert parsed is not None
        assert parsed.domain == "gamestatsmatchhistory"
        assert parsed.rotation == 0

    def test_a_hyphenated_domain_is_put_back_together(self) -> None:
        # The name is split on hyphens to find the rotation number, so a domain that
        # contains one has to survive being rejoined rather than arriving truncated.
        parsed = parse_name(Path("playerProfile-0-map-progression-4.savgs"))
        assert parsed is not None
        assert (parsed.domain, parsed.rotation) == ("map-progression", 4)

    def test_the_profile_number_is_kept(self) -> None:
        parsed = parse_name(Path("playerProfile-2-currencies.savgs"))
        assert parsed is not None
        assert parsed.profile == 2

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
    def test_a_domain_is_ordered_by_rotation(self, tmp_path: Path) -> None:
        for name in (
            "playerProfile-0-currencies-2.savgs",
            "playerProfile-0-currencies.savgs",
            "playerProfile-0-currencies-1.savgs",
            "unrelated.txt",
        ):
            (tmp_path / name).write_bytes(b"")
        assert [f.rotation for f in discover(tmp_path)] == [0, 1, 2]

    def test_an_empty_directory_yields_nothing_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        assert discover(tmp_path) == []


class TestNewestPerDomain:
    def write(
        self, tmp_path: Path, name: str, counter: int, mtime: float = 0.0
    ) -> None:
        """A save whose header says which write produced it."""
        path = tmp_path / name
        path.write_bytes(gzip.compress(payload(i32(counter))))
        if mtime:
            os.utime(path, (mtime, mtime))

    def test_a_numbered_slot_wins_when_it_holds_the_later_write(
        self, tmp_path: Path
    ) -> None:
        # The case that made this function exist: on a real profile the unsuffixed
        # file held 31 unlocked weapons and a numbered slot held 37, because the ten
        # names are a ring the game writes round rather than a file and its backups.
        self.write(tmp_path, "playerProfile-0-unlockedweapons.savgs", 20)
        self.write(tmp_path, "playerProfile-0-unlockedweapons-7.savgs", 27)
        self.write(tmp_path, "playerProfile-0-unlockedweapons-8.savgs", 22)
        newest = newest_per_domain(discover(tmp_path), profile=0)
        assert newest["unlockedweapons"].rotation == 7

    def test_the_unsuffixed_file_wins_when_it_holds_the_later_write(
        self, tmp_path: Path
    ) -> None:
        self.write(tmp_path, "playerProfile-0-currencies.savgs", 51)
        self.write(tmp_path, "playerProfile-0-currencies-4.savgs", 44)
        newest = newest_per_domain(discover(tmp_path), profile=0)
        assert newest["currencies"].rotation == 0

    def test_the_counter_decides_even_when_timestamps_say_otherwise(
        self, tmp_path: Path
    ) -> None:
        # A copy or a restore rewrites modification times and leaves the payload
        # alone, so the two can disagree and only one of them is evidence.
        self.write(tmp_path, "playerProfile-0-currencies.savgs", 51, mtime=1000.0)
        self.write(tmp_path, "playerProfile-0-currencies-4.savgs", 44, mtime=9000.0)
        assert (
            newest_per_domain(discover(tmp_path), profile=0)["currencies"].rotation == 0
        )

    def test_each_domain_is_resolved_on_its_own(self, tmp_path: Path) -> None:
        # Domains are written independently, so the newest slot differs between them
        # and picking one number for the whole directory would be wrong for most.
        self.write(tmp_path, "playerProfile-0-currencies.savgs", 90)
        self.write(tmp_path, "playerProfile-0-currencies-1.savgs", 10)
        self.write(tmp_path, "playerProfile-0-skilltree.savgs", 10)
        self.write(tmp_path, "playerProfile-0-skilltree-1.savgs", 90)
        newest = newest_per_domain(discover(tmp_path), profile=0)
        assert newest["currencies"].rotation == 0
        assert newest["skilltree"].rotation == 1

    def test_one_profile_never_answers_for_another(self, tmp_path: Path) -> None:
        # Both profiles have the same domains, and the higher counter belongs to the
        # one that was not asked for. Merging them would report a stranger's save.
        self.write(tmp_path, "playerProfile-0-currencies.savgs", 12)
        self.write(tmp_path, "playerProfile-1-currencies.savgs", 99)
        newest = newest_per_domain(discover(tmp_path), profile=0)
        assert newest["currencies"].path.name == "playerProfile-0-currencies.savgs"

    def test_a_profile_with_no_files_resolves_to_nothing(self, tmp_path: Path) -> None:
        self.write(tmp_path, "playerProfile-0-currencies.savgs", 12)
        assert newest_per_domain(discover(tmp_path), profile=3) == {}

    def test_an_exact_counter_tie_resolves_the_same_way_every_time(
        self, tmp_path: Path
    ) -> None:
        self.write(tmp_path, "playerProfile-0-currencies-2.savgs", 70)
        self.write(tmp_path, "playerProfile-0-currencies-5.savgs", 70)
        assert (
            newest_per_domain(discover(tmp_path), profile=0)["currencies"].rotation == 5
        )

    def test_nothing_in_yields_nothing_out(self) -> None:
        assert newest_per_domain([], profile=0) == {}


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

    def test_a_byte_is_read_as_its_own_value(self) -> None:
        assert PayloadReader(payload(b"\x01")).read_byte() == 1

    def test_skipping_moves_past_bytes_without_interpreting_them(self) -> None:
        reader = PayloadReader(payload(b"\x00" * 5, text("DamageModifier"), i32(5)))
        reader.skip(5)
        assert reader.read_string() == "DamageModifier"
        assert reader.read_int32() == 5

    def test_skipping_past_the_end_raises_rather_than_silently_stopping(self) -> None:
        with pytest.raises(SaveFormatError, match="cannot skip 5 bytes"):
            PayloadReader(payload(b"\x00\x00")).skip(5)

    def test_skipping_backwards_is_refused_rather_than_rewinding(self) -> None:
        # A bounds check alone passes a negative count and moves the position back,
        # so the same bytes are read twice and the second reading looks like a record.
        reader = PayloadReader(payload(i32(1), i32(2)))
        with pytest.raises(SaveFormatError, match="cannot skip backwards"):
            reader.skip(-4)
        assert reader.remaining == 8

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


class TestWriteCounter:
    def test_the_header_integer_is_read_apart_from_the_records(self) -> None:
        # Six currencies follow it, which is exactly what the game's header bar shows.
        counts = (148272, 115, 101, 82, 98, 58)
        data = payload(i32(651), *(i32(n) for n in counts))
        assert read_write_counter(data) == 651
        reader = PayloadReader(data)
        reader.read_int32()
        assert tuple(reader.read_int32() for _ in counts) == counts
        assert reader.remaining == 0


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
