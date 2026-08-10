"""What the player owns, and what the save cannot say either way.

Rune ownership was the advisor's open problem: the save never writes "owns this rune",
only rune identifiers that turned up in a preset or a match, so counting those
undercounts whatever the player holds but has never equipped. It is decidable after all,
by a different route. Every rune granted by a character's skill tree names the node that
grants it, the save lists the nodes the player has bought, and a node in that list is a
rune in hand whether or not it was ever used.

Runes that no tree grants come through the other half of the same idea. Each names the
achievement that unlocks it, the save records which achievements are complete, and a
completed one is a rune in hand. That half was unreadable until the achievement domain
was decoded, and it is the larger half: sixty-two of the catalogued runes against
sixty-six.

Both routes reason about how a rune is unlocked. A third reads the player's own history
instead: a rune sitting in a saved preset was selectable when that preset was saved, so
it is a rune in hand no matter what the other two can work out. It settles only what
they leave open, which is why the module opens by calling preset identifiers an
undercount. They are, as a total; as a floor they are direct evidence, and the two runes
they settle here are exactly the ones whose achievement the install and the save name
differently, so no join could have reached them.

What is left undecidable is a rune naming neither, which is now a gap in the catalog
rather than a limit of the save. The distinction still matters more than the count: an
advisor that reports a rune the player lacks and a rune it cannot see in the same words
is guessing in the half of those cases where it is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.achievements import Achievement
from grimoire.catalog import Catalog
from grimoire.skilltree import SkillTreeNode


class OwnershipError(Exception):
    """A rune was asked about that the catalog never described."""


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
        if identifier in self.undecidable:
            return "undecidable"
        # Not a third state. An identifier that is in none of the three was never in
        # the catalog, and answering "undecidable" for it would dress a catalog miss as
        # a known limit of the save, which is the one confusion this class exists to
        # prevent. A typo in a build would read as a rune the tool merely cannot see.
        raise OwnershipError(
            f"no rune record for {identifier!r}, so its ownership was never "
            "considered. Add one to packs/<game>/catalog/runes.toml with its evidence."
        )


def read_rune_ownership(
    catalog: Catalog,
    nodes: list[SkillTreeNode],
    achievements: list[Achievement] | None = None,
    preset_runes: list[str] | None = None,
) -> RuneOwnership:
    """Split every rune in the catalog by what this save can prove about it.

    Achievements are optional so a caller that has not read that domain gets an honest
    undecidable for the runes they unlock, rather than sixty-two runes reported as not
    owned on the strength of a file nobody opened. Presets are optional for the same
    reason, and settle only what the other two leave open.
    """
    equipped = set(preset_runes or ())
    unknown = catalog.missing(sorted(equipped))
    if unknown:
        # A rune the player has equipped and the catalog has never heard of. That is a
        # catalog gap, and on a save written by a newer build than the pack was
        # extracted from it is the staleness the project requires to be reportable.
        raise OwnershipError(
            f"the save holds these runes in a preset and the catalog describes none of "
            f"them: {', '.join(unknown)}. Add them to "
            "packs/<game>/catalog/runes.toml with their evidence, or re-extract "
            "against the installed build."
        )
    # A node only appears in the save once bought, and every node in a real profile
    # carried a level of at least one, so presence is the whole test. Levels are read
    # anyway rather than assumed away: a zero would mean the opposite of what presence
    # means here, and it should not pass silently if the game ever writes one.
    bought = {node.node_id for node in nodes if node.level >= 1}

    known = None if achievements is None else {a.achievement_id for a in achievements}
    earned = (
        None
        if achievements is None
        else {a.achievement_id for a in achievements if a.completed}
    )

    owned, not_owned, undecidable = [], [], []
    for entry in sorted(catalog.entries_of_kind("rune"), key=lambda e: e.id):
        if entry.unlocked_by is not None:
            (owned if entry.unlocked_by in bought else not_owned).append(entry.id)
        elif entry.unlocked_by_achievement is None or known is None:
            undecidable.append(entry.id)
        elif entry.unlocked_by_achievement not in known:
            # The save holds no record of this achievement at all, which is not the
            # same as holding one that is unfinished. Reading absence as incomplete
            # reported three runes the player has equipped as runes they do not own.
            undecidable.append(entry.id)
        elif entry.unlocked_by_achievement in earned:
            owned.append(entry.id)
        else:
            not_owned.append(entry.id)

    contradicted = sorted(equipped.intersection(not_owned))
    if contradicted:
        # Two readings of one save disagreeing, so one of them is wrong: either the
        # record names the wrong node or achievement, or a patch moved the unlock and
        # the preset predates it. Promoting the rune anyway would bury a broken join,
        # and leaving it not owned would contradict a rune the player has equipped.
        raise OwnershipError(
            f"these runes sit in a saved preset while the catalog's unlock route says "
            f"they are not owned: {', '.join(contradicted)}. One of the two readings "
            "is wrong; check the record's unlocked_by or unlocked_by_achievement "
            "against the installed build."
        )
    promoted = equipped.intersection(undecidable)
    return RuneOwnership(
        tuple(sorted(owned + sorted(promoted))),
        tuple(not_owned),
        tuple(i for i in undecidable if i not in promoted),
    )
