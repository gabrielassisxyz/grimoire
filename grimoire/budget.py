"""Whether a set of runes fits the runic power the player actually has.

Two limits, and they are separate. Runic power is spent across every rune equipped, and
each section has its own count of slots, so a build can fail either by costing more than
the player can pay or by asking for a fifth tenacity rune that costs nothing at all.

The capacity is the part the save only half answers. Five points come from a skill tree
node this reads directly; the rest come from achievements, and that domain has not been
decoded. So capacity is a range rather than a number, and the verdict says "fits",
"does not fit" or "undecidable" accordingly. The middle answer is the one worth having:
a build costing nine is not a build that fits, it is a build whose fit depends on a fact
this tool cannot yet read, and reporting that names the capture that would settle it.

Cost is summed as a signed total on purpose. One rune raises the ceiling instead of
spending from it and the wiki writes it as a cost of -2, so a check that summed
magnitudes would reject the one build most likely to need it.
"""

from __future__ import annotations

from dataclasses import dataclass

from grimoire.catalog import Catalog
from grimoire.skilltree import SkillTreeNode

# The node that carries the skill tree's contribution, and the ceiling the game puts on
# it. Named here rather than inlined because the reading below is only as good as the
# node still being spelled this way after a patch.
RUNIC_POWER_NODE = "SkillTreeRunicPower"

# Achievements contribute up to five more. The exact figure needs the achievement
# domain, which is not decoded, so it bounds the answer instead of settling it.
MAX_FROM_ACHIEVEMENTS = 5

SLOTS = {"tenacity": 4, "versatility": 3}


@dataclass(frozen=True)
class BudgetVerdict:
    cost: int
    capacity_at_least: int
    capacity_at_most: int
    verdict: str
    reasons: tuple[str, ...]


def read_capacity(nodes: list[SkillTreeNode]) -> int:
    """The runic power the skill tree grants, which is the half the save states."""
    for node in nodes:
        if node.node_id == RUNIC_POWER_NODE:
            return node.level
    return 0


def check_runic_power(
    catalog: Catalog, rune_ids: list[str], nodes: list[SkillTreeNode]
) -> BudgetVerdict:
    """Whether these runes fit, or which fact is missing to say."""
    entries = [catalog.entry(rune_id) for rune_id in rune_ids]
    cost = sum(e.runic_power_cost for e in entries)

    reasons = []
    for slot, limit in SLOTS.items():
        used = sum(1 for e in entries if e.slot == slot)
        if used > limit:
            reasons.append(f"{used} {slot} runes where the game allows {limit}")

    at_least = read_capacity(nodes)
    at_most = at_least + MAX_FROM_ACHIEVEMENTS

    if cost > at_most:
        reasons.append(f"costs {cost} against a ceiling of {at_most}")
        verdict = "does not fit"
    elif cost > at_least:
        reasons.append(
            f"costs {cost}, which fits only if achievements have granted "
            f"{cost - at_least} of the {MAX_FROM_ACHIEVEMENTS} available; the "
            "achievement domain is not decoded, so the save cannot say"
        )
        verdict = "undecidable"
    else:
        verdict = "fits"

    # A slot overflow is decidable whatever the capacity turns out to be, so it settles
    # the verdict rather than being reported alongside an undecidable one.
    if any("where the game allows" in r for r in reasons):
        verdict = "does not fit"

    return BudgetVerdict(cost, at_least, at_most, verdict, tuple(reasons))
