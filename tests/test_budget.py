"""The runic power budget, and the band where the save cannot answer.

Hermetic: the capacity comes from a node list built here rather than from a real save,
and the costs from a small catalog written per test, so nothing depends on the player's
own files or on the pack staying the shape it is today. The one test that does read the
pack is about the pack.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from grimoire.budget import check_runic_power
from grimoire.catalog import load
from grimoire.skilltree import SkillTreeNode

PACK = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors"


def record(rune_id: str, slot: str, cost: int) -> str:
    return (
        f'[[rune]]\nid = "{rune_id}"\ndisplay = "{rune_id} shown"\n'
        f'slot = "{slot}"\nrunic_power_cost = {cost}\nconfidence = 0.9\n'
        '[[rune.evidence]]\ntype = "game_asset"\n'
        'asset_path = "a"\nbuild_id = "1.5d2"\n'
    )


@pytest.fixture
def catalog(tmp_path: Path):
    (tmp_path / "runes.toml").write_text(
        record("Cheap", "tenacity", 1)
        + record("Dear", "tenacity", 4)
        + record("Free", "versatility", 0)
        + record("AlsoFree", "versatility", 0)
        + record("StillFree", "versatility", 0)
        + record("Spare", "versatility", 0)
        + record("Pact", "tenacity", -2)
        + record("A", "tenacity", 1)
        + record("B", "tenacity", 1)
        + record("C", "tenacity", 1)
        + record("D", "tenacity", 1)
        + record("E", "tenacity", 1)
    )
    return load(tmp_path)


def tree(points: int) -> list[SkillTreeNode]:
    return [SkillTreeNode(node_id="SkillTreeRunicPower", level=points)]


class TestTheThreeAnswers:
    def test_a_build_inside_the_proven_capacity_fits(self, catalog) -> None:
        verdict = check_runic_power(catalog, ["Cheap", "Free"], tree(5))
        assert verdict.verdict == "fits"
        assert verdict.cost == 1

    def test_a_build_above_the_ceiling_does_not_fit(self, catalog) -> None:
        # Four at four is sixteen against a ceiling of ten, so no achievement total
        # could rescue it and the answer needs nothing the save has not got.
        verdict = check_runic_power(catalog, ["Dear"] * 4, tree(5))
        assert verdict.verdict == "does not fit"

    def test_a_build_between_the_two_is_undecidable_rather_than_assumed(
        self, catalog
    ) -> None:
        # The answer the module exists for. Seven fits if achievements have granted at
        # least two, and the save cannot say, so neither can this.
        verdict = check_runic_power(catalog, ["Dear", "Cheap", "Dear"], tree(5))
        assert verdict.cost == 9
        assert verdict.verdict == "undecidable"
        assert "achievement domain is not decoded" in " ".join(verdict.reasons)


class TestWhatSettlesRegardlessOfCapacity:
    def test_too_many_tenacity_runes_does_not_fit_however_cheap(self, catalog) -> None:
        # Five runes costing five in total, well inside any capacity, and still refused:
        # the section holds four. A check that only summed cost would pass this.
        verdict = check_runic_power(catalog, ["A", "B", "C", "D", "E"], tree(5))
        assert verdict.cost == 5
        assert verdict.verdict == "does not fit"
        assert "4" in " ".join(verdict.reasons)

    def test_a_slot_overflow_outranks_an_undecidable_capacity(self, catalog) -> None:
        # Both problems at once. The slot count is decidable and the capacity is not,
        # so the decidable failure has to win rather than being softened into a maybe.
        verdict = check_runic_power(
            catalog, ["Dear", "Dear", "Cheap", "A", "B"], tree(5)
        )
        assert verdict.verdict == "does not fit"

    def test_too_many_versatility_runes_does_not_fit(self, catalog) -> None:
        runes = ["Free", "AlsoFree", "StillFree", "Spare"]
        assert check_runic_power(catalog, runes, tree(5)).verdict == "does not fit"


def test_a_rune_that_raises_the_ceiling_is_subtracted_not_added(catalog) -> None:
    # Demonic Pact's shape. It is written as a cost of -2 because it grants runic power,
    # so summing magnitudes would reject the build it exists to make possible.
    without = check_runic_power(catalog, ["Dear", "Cheap"], tree(5))
    with_pact = check_runic_power(catalog, ["Dear", "Cheap", "Pact"], tree(5))
    assert without.cost == 5
    assert with_pact.cost == 3
    assert with_pact.verdict == "fits"


def test_the_pilot_build_sits_exactly_on_the_ceiling() -> None:
    # Worth pinning because it is the first thing the advisor will have to tell this
    # player: the build costs ten, and ten is the most the game allows anyone, so it
    # fits only for someone who has every achievement point. This save proves five.
    catalog = load(PACK / "catalog")
    build = tomllib.loads((PACK / "builds/barbarian-electric.toml").read_text())
    verdict = check_runic_power(catalog, [r["id"] for r in build["runes"]], tree(5))
    assert verdict.cost == 10
    assert verdict.capacity_at_most == 10
    assert verdict.verdict == "undecidable"
