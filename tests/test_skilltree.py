"""Tests for the skill tree reader.

Payloads are assembled here rather than read from a save: a real one is the player's
own data and is never tracked. The layout being asserted was settled against a real
profile, where it read 148 records and left zero bytes over, and that leftover count
is the property most of these tests are about.
"""

from __future__ import annotations

import struct

import pytest

from grimoire.savegame import SaveFormatError
from grimoire.skilltree import SkillTreeNode, read_skill_tree

TAG = b"\x00"
GAP = b"\x00" * 5  # the five unidentified bytes each record opens with


def i32(value: int) -> bytes:
    return struct.pack("<i", value)


def text(value: str) -> bytes:
    raw = value.encode("utf-8")
    return bytes([len(raw)]) + raw


def record(node_id: str, level: int) -> bytes:
    return GAP + text(node_id) + i32(level)


def tree(*records: bytes, version: int = 513, marker: int = 1) -> bytes:
    return TAG + i32(version) + bytes([marker]) + i32(len(records)) + b"".join(records)


class TestRead:
    def test_nodes_keep_the_order_the_file_wrote_them_in(self) -> None:
        data = tree(
            record("DamageModifier", 5),
            record("Rerolls", 5),
            record("DashCount", 1),
        )
        assert read_skill_tree(data) == [
            SkillTreeNode("DamageModifier", 5),
            SkillTreeNode("Rerolls", 5),
            SkillTreeNode("DashCount", 1),
        ]

    def test_a_node_belonging_to_a_character_reads_like_any_other(self) -> None:
        # No tier or slot meaning is asserted, because no source has established one.
        data = tree(record("Barbarian_T02N04", 5), record("Barbarian_T01S01", 1))
        assert [n.node_id for n in read_skill_tree(data)] == [
            "Barbarian_T02N04",
            "Barbarian_T01S01",
        ]

    def test_an_uninvested_node_is_a_level_of_zero_and_not_an_absence(self) -> None:
        assert read_skill_tree(tree(record("BlockChance", 0))) == [
            SkillTreeNode("BlockChance", 0)
        ]

    def test_a_tree_with_no_records_is_empty_rather_than_an_error(self) -> None:
        assert read_skill_tree(tree()) == []


class TestRefusal:
    def test_bytes_left_over_are_refused_rather_than_ignored(self) -> None:
        # The failure this guards against: a layout wrong by one field still consumes
        # the stream and still returns records, just the wrong ones. The leftover is
        # the only symptom, so it has to be fatal.
        data = tree(record("DamageModifier", 5)) + b"\x00\x00\x00"
        with pytest.raises(SaveFormatError, match="3 bytes remain"):
            read_skill_tree(data)

    def test_a_count_larger_than_the_records_names_the_record_it_died_on(self) -> None:
        data = TAG + i32(513) + b"\x01" + i32(3) + record("Armor", 5)
        with pytest.raises(SaveFormatError, match="record 1 of 3"):
            read_skill_tree(data)

    def test_a_negative_count_is_refused_before_anything_is_read(self) -> None:
        data = TAG + i32(513) + b"\x01" + i32(-1)
        with pytest.raises(SaveFormatError, match="negative record count"):
            read_skill_tree(data)

    def test_an_unexpected_collection_marker_stops_the_read(self) -> None:
        # A different marker means this is not the layout below, and carrying on would
        # produce records rather than a complaint.
        with pytest.raises(SaveFormatError, match="collection marker"):
            read_skill_tree(tree(record("Armor", 5), marker=2))

    def test_a_payload_from_another_domain_does_not_decode_into_nodes(self) -> None:
        currencies = TAG + i32(651) + b"".join(i32(n) for n in (148272, 115, 101))
        with pytest.raises(SaveFormatError):
            read_skill_tree(currencies)
