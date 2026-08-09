"""Read the skill tree domain: what the player has permanently invested in.

The first domain whose record layout is decoded rather than scanned. It is worth
decoding early for a reason that is not obvious from its name: alongside the stat
nodes it holds the run's finite counters, ``Rerolls``, ``Banish``, ``Lock``,
``DashCount`` and ``DeathGuards``. Those were expected to cost a screen read at every
level-up, and their starting values turn out to be sitting in the save, free of any
vision problem. ``SkillTreeRunicPower`` is here too, which is what bounds how many
runes a preset can carry.

The layout was settled against a real profile: 148 records read, zero bytes left over.
That last part is the check that matters, and it is enforced below, because a record
layout that is wrong by one field consumes the stream just as happily and ends up
somewhere else.

Node identifiers come in two shapes and this module reads both without treating them
differently: a bare name for an account-wide node, and ``<Character>_T<tier>N<node>``
or ``...S<node>`` for one belonging to a character. Splitting them apart would mean
asserting what the tiers mean, which no source has established yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.savegame import PayloadReader, SaveFormatError

# Every record opens with five bytes that were zero in all 148 records of the profile
# this was decoded against. Zeros carry no field boundaries, so how those five divide
# into fields is not decidable from them and any name given here would be invented.
_UNIDENTIFIED_RECORD_PREFIX = 5

# The byte between the write counter and the record count, 1 in every domain read so
# far. What another value would mean is unknown, which is the reason to stop at one
# rather than to carry on: an unexplained header byte in front of a record layout is
# not evidence that the layout still holds.
_COLLECTION_MARKER = 1


@dataclass(frozen=True)
class SkillTreeNode:
    node_id: str
    level: int


def read_skill_tree(data: bytes) -> list[SkillTreeNode]:
    """Every skill tree node with the level invested in it, in the file's own order."""
    reader = PayloadReader(data)
    reader.read_int32()  # write counter, see savegame.read_write_counter
    marker = reader.read_byte()
    if marker != _COLLECTION_MARKER:
        raise SaveFormatError(
            f"skill tree: expected collection marker {_COLLECTION_MARKER}, got {marker}"
        )
    count = reader.read_int32()
    if count < 0:
        raise SaveFormatError(f"skill tree: negative record count {count}")

    nodes = []
    for index in range(count):
        try:
            reader.skip(_UNIDENTIFIED_RECORD_PREFIX)
            node_id = reader.read_string()
            level = reader.read_int32()
        except (SaveFormatError, UnicodeDecodeError) as err:
            raise SaveFormatError(
                f"skill tree: record {index} of {count}: {err}"
            ) from err
        nodes.append(SkillTreeNode(node_id=node_id, level=level))

    if reader.remaining:
        raise SaveFormatError(
            f"skill tree: {count} records read but {reader.remaining} bytes remain, "
            "so the record layout does not match this payload"
        )
    return nodes
