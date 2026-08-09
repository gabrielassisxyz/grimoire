"""Whether a set of runes fits the runic power the player actually has.

Two limits, and they are separate. Runic power is spent across every rune equipped, and
each section has its own count of slots, so a build can fail either by costing more than
the player can pay or by asking for a fifth tenacity rune that costs nothing at all.

The capacity comes from two places. Five points come from a skill tree node this reads
directly; the rest come from achievements, which a caller may or may not have read. So
capacity is a range rather than a number, and the verdict says "fits", "does not fit" or
"undecidable" accordingly. The middle answer is the one worth having: a build costing
nine is not a build that fits, it is a build whose fit depends on a fact nothing has
established, and reporting that names what would establish it.

The range does not close just because the achievements were read. A save holds no record
of an achievement until something about it has happened, so a granting achievement that
is simply absent leaves the ceiling open while adding nothing to the floor. Reading that
absence as unearned is the same mistake ownership already refuses to make, and it fails
in the expensive direction: it produces an exact capacity, which reads as an answer.

Cost is summed as a signed total on purpose. One rune raises the ceiling instead of
spending from it and the wiki writes it as a cost of -2, so a check that summed
magnitudes would reject the one build most likely to need it.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.achievements import Achievement
from grimoire.catalog import Catalog
from grimoire.skilltree import SkillTreeNode

# The node that carries the skill tree's contribution, and the ceiling the game puts on
# it. Named here rather than inlined because the reading below is only as good as the
# node still being spelled this way after a patch.
RUNIC_POWER_NODE = "SkillTreeRunicPower"

# What each half can contribute at most. The wiki gives five from the skill tree and
# five from achievements, for a ceiling of ten.
MAX_FROM_SKILL_TREE = 5

# The ceiling on the achievement half, stated by the game independently of which
# achievements the catalog happens to describe. It bounds a caller that has read no
# achievements at all, and it is what the catalog's own grants are checked against.
MAX_FROM_ACHIEVEMENTS = 5

SLOTS = {"tenacity": 4, "versatility": 3}


class BudgetError(Exception):
    """A set of runes that is not a build, so pricing it would answer nothing."""


@dataclass(frozen=True)
class AchievementCapacity:
    at_least: int
    at_most: int
    # The granting achievements this save holds no record of. They are what separates
    # the two bounds, so the verdict can name them instead of saying it does not know.
    unread: tuple[str, ...]


@dataclass(frozen=True)
class BudgetVerdict:
    cost: int
    capacity_at_least: int
    capacity_at_most: int
    verdict: str
    reasons: tuple[str, ...]


def read_capacity(nodes: list[SkillTreeNode]) -> int:
    """The runic power the skill tree grants, which is the half the save states."""
    levels = [n.level for n in nodes if n.node_id == RUNIC_POWER_NODE]
    if not levels:
        return 0
    # A save is a file on disk that anyone can edit, and this number decides whether a
    # build is loadable. A level the game cannot grant, or the node appearing twice,
    # means the reading is wrong or the file is not what it claims, and either way a
    # verdict computed from it would be confident and baseless.
    if len(levels) > 1:
        raise BudgetError(f"{RUNIC_POWER_NODE} appears {len(levels)} times in the save")
    level = levels[0]
    if not 0 <= level <= MAX_FROM_SKILL_TREE:
        raise BudgetError(
            f"{RUNIC_POWER_NODE} is at level {level}, outside the 0 to "
            f"{MAX_FROM_SKILL_TREE} the game grants"
        )
    return level


def read_achievement_capacity(
    catalog: Catalog, achievements: list[Achievement]
) -> AchievementCapacity:
    """The runic power the achievements grant, bounded rather than asserted.

    Completion comes from the save and the grant from the catalog, which is the whole
    reason this is two arguments: the game decides which achievements pay a point and
    the profile decides which of those are done, and neither source knows the other.
    An achievement the catalog does not describe grants nothing, because a catalog that
    does not mention it is not evidence that it pays.

    An achievement the catalog describes and the save does not mention is the other
    case, and it is not the same one. The save writes a record once there is progress to
    write, so absence means unasked rather than unearned, and counting it as zero would
    hand back an exact capacity built on a fact nobody read.
    """
    grants = {
        entry.id: entry.grants_runic_power
        for entry in catalog.entries_of_kind("achievement")
        if entry.grants_runic_power
    }
    total = sum(grants.values())
    if total > MAX_FROM_ACHIEVEMENTS:
        # Two independent claims about the same ceiling, and a disagreement means one of
        # them is wrong. Continuing would pick whichever the arithmetic happened to use.
        raise BudgetError(
            f"the catalog grants {total} runic power across {len(grants)} "
            f"achievements, more than the {MAX_FROM_ACHIEVEMENTS} the game awards"
        )

    completion = {a.achievement_id: a.completed for a in achievements}
    earned = sum(points for i, points in grants.items() if completion.get(i))
    unread = tuple(sorted(i for i in grants if i not in completion))
    return AchievementCapacity(
        at_least=earned,
        at_most=earned + sum(grants[i] for i in unread),
        unread=unread,
    )


def check_runic_power(
    catalog: Catalog,
    rune_ids: list[str],
    nodes: list[SkillTreeNode],
    achievements: list[Achievement] | None = None,
) -> BudgetVerdict:
    """Whether these runes fit, or which fact is missing to say.

    Achievements are optional so a caller that has not read that domain still gets the
    bounded answer rather than a wrong one. Passing them turns the range into a number.
    """
    duplicates = sorted({r for r in rune_ids if rune_ids.count(r) > 1})
    if duplicates:
        # A preset holds each rune once, so a repeat is a malformed build rather than a
        # composition to price. Summing it anyway would be quietly wrong in the
        # direction of fitting, since the one rune worth repeating has a negative cost.
        raise BudgetError(f"these runes appear more than once: {', '.join(duplicates)}")
    entries = [catalog.entry(rune_id) for rune_id in rune_ids]
    cost = sum(e.runic_power_cost for e in entries)

    reasons = []
    for slot, limit in SLOTS.items():
        used = sum(1 for e in entries if e.slot == slot)
        if used > limit:
            reasons.append(f"{used} {slot} runes where the game allows {limit}")

    from_tree = read_capacity(nodes)
    if achievements is None:
        at_least, at_most = from_tree, from_tree + MAX_FROM_ACHIEVEMENTS
        unsettled = "the achievement domain of the save has not been read"
    else:
        granted = read_achievement_capacity(catalog, achievements)
        at_least = from_tree + granted.at_least
        at_most = from_tree + granted.at_most
        unsettled = (
            "this save holds no record of "
            f"{', '.join(granted.unread)}, so whether they are earned is unknown"
        )

    if cost > at_most:
        reasons.append(f"costs {cost} against a ceiling of {at_most}")
        verdict = "does not fit"
    elif cost > at_least:
        reasons.append(
            f"costs {cost}, which fits only if {cost - at_least} more runic power has "
            f"been granted than this can account for: {unsettled}"
        )
        verdict = "undecidable"
    else:
        verdict = "fits"

    # A slot overflow is decidable whatever the capacity turns out to be, so it settles
    # the verdict rather than being reported alongside an undecidable one.
    if any("where the game allows" in r for r in reasons):
        verdict = "does not fit"

    return BudgetVerdict(cost, at_least, at_most, verdict, tuple(reasons))
