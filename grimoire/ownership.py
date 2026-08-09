"""What the player owns, and what the save cannot say either way.

Rune ownership was the advisor's open problem: the save never writes "owns this rune",
only rune identifiers that turned up in a preset or a match, so counting those
undercounts whatever the player holds but has never equipped. It is decidable after all,
by a different route. Every rune granted by a character's skill tree names the node that
grants it, the save lists the nodes the player has bought, and a node in that list is a
rune in hand whether or not it was ever used.

The route stops where the trees do. Runes unlocked by an achievement have no node, so
the save proves nothing about them here, and they are returned as unknown rather than
folded into either answer. That distinction is the point: an advisor that reports a
missing rune and an unreadable one the same way is guessing in the half of the cases
where it happens to be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.catalog import Catalog
from grimoire.skilltree import SkillTreeNode


@dataclass(frozen=True)
class RuneOwnership:
    owned: tuple[str, ...]
    not_owned: tuple[str, ...]
    undecidable: tuple[str, ...]

    def describe(self, identifier: str) -> str:
        if identifier in self.owned:
            return "owned"
        if identifier in self.not_owned:
            return "not owned"
        return "undecidable"


def read_rune_ownership(catalog: Catalog, nodes: list[SkillTreeNode]) -> RuneOwnership:
    """Split every rune in the catalog by what this save can prove about it."""
    # A node only appears in the save once bought, and every node in a real profile
    # carried a level of at least one, so presence is the whole test. Levels are read
    # anyway rather than assumed away: a zero would mean the opposite of what presence
    # means here, and it should not pass silently if the game ever writes one.
    bought = {node.node_id for node in nodes if node.level >= 1}

    owned, not_owned, undecidable = [], [], []
    for entry in sorted(catalog.entries_of_kind("rune"), key=lambda e: e.id):
        if entry.unlocked_by is None:
            undecidable.append(entry.id)
        elif entry.unlocked_by in bought:
            owned.append(entry.id)
        else:
            not_owned.append(entry.id)
    return RuneOwnership(tuple(owned), tuple(not_owned), tuple(undecidable))
