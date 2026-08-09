"""Rune ownership derived from the skill tree nodes a save records.

Hermetic by construction: the real save is the player's own data and is never tracked,
so these build the node list rather than read one. That is not a compromise, because
what is under test is the rule joining nodes to records, not the save parser, which has
its own tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.catalog import CatalogError, load
from grimoire.ownership import read_rune_ownership
from grimoire.skilltree import SkillTreeNode

PACK_CATALOG = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors/catalog"

RUNES_WITH_A_NODE = """
[[rune]]
id = "RuneExtraCritChance"
display = "Vulnerable Target"
unlocked_by = "Houndmaster_T03S01"
confidence = 0.9
[[rune.evidence]]
type = "game_asset"
asset_path = "Soulstone Survivors_Data/resources.assets"
build_id = "1.5d2"

[[rune]]
id = "RuneExtraDamageWhileBossIsAlive"
display = "Lord's Bane"
unlocked_by = "Necromancer_T02S01"
confidence = 0.9
[[rune.evidence]]
type = "game_asset"
asset_path = "Soulstone Survivors_Data/resources.assets"
build_id = "1.5d2"

[[rune]]
id = "RuneMasteryFire"
display = "Skill Mastery: Fire"
confidence = 0.9
[[rune.evidence]]
type = "community_source"
url = "https://soulstone-survivors.fandom.com/wiki/Runes"
retrieved = "2026-08-08"
game_version = "1.5d2"
"""


@pytest.fixture
def catalog(tmp_path: Path):
    (tmp_path / "runes.toml").write_text(RUNES_WITH_A_NODE)
    return load(tmp_path)


def bought(*node_ids: str) -> list[SkillTreeNode]:
    return [SkillTreeNode(node_id=n, level=1) for n in node_ids]


class TestWhatTheSaveProves:
    def test_a_rune_whose_node_was_bought_is_owned(self, catalog) -> None:
        ownership = read_rune_ownership(catalog, bought("Houndmaster_T03S01"))
        assert ownership.describe("RuneExtraCritChance") == "owned"

    def test_a_rune_whose_node_is_absent_is_not_owned(self, catalog) -> None:
        # Absent means not bought, which the save does settle: it lists every node the
        # player has invested in, so a missing node is an answer and not a silence.
        ownership = read_rune_ownership(catalog, bought("Houndmaster_T03S01"))
        assert ownership.describe("RuneExtraDamageWhileBossIsAlive") == "not owned"

    def test_a_rune_with_no_node_is_undecidable_rather_than_missing(
        self, catalog
    ) -> None:
        # The distinction the module exists for. This rune unlocks through an
        # achievement, so the trees say nothing about it, and reporting it as not owned
        # would be a claim the save never made.
        ownership = read_rune_ownership(catalog, bought("Houndmaster_T03S01"))
        assert ownership.describe("RuneMasteryFire") == "undecidable"
        assert "RuneMasteryFire" not in ownership.not_owned

    def test_a_node_at_level_zero_does_not_count_as_bought(self, catalog) -> None:
        # No real profile has written one, so this pins the reading rather than
        # describing observed behaviour: if the game ever writes a zero it must not
        # silently become ownership.
        nodes = [SkillTreeNode(node_id="Houndmaster_T03S01", level=0)]
        assert read_rune_ownership(catalog, nodes).describe("RuneExtraCritChance") == (
            "not owned"
        )

    def test_every_rune_is_accounted_for_exactly_once(self, catalog) -> None:
        ownership = read_rune_ownership(catalog, bought("Necromancer_T02S01"))
        total = ownership.owned + ownership.not_owned + ownership.undecidable
        assert sorted(total) == [
            "RuneExtraCritChance",
            "RuneExtraDamageWhileBossIsAlive",
            "RuneMasteryFire",
        ]
        assert len(set(total)) == len(total)


class TestAgainstTheRealPack:
    def test_the_pack_splits_into_decidable_and_not(self) -> None:
        # Sixty-six runes name a node and six do not, which is the shape the advisor
        # will have to report: most of the catalog is answerable from the save alone.
        ownership = read_rune_ownership(load(PACK_CATALOG), [])
        assert len(ownership.not_owned) == 66
        assert len(ownership.undecidable) == 6

    def test_a_node_the_pack_names_is_spelled_the_way_the_save_spells_it(self) -> None:
        # The join is a string match against save data, so a node written in the
        # catalog's own style rather than the game's would fail silently and report
        # everything as unowned.
        entry = load(PACK_CATALOG).entry("RuneExtraDamageWhileBossIsAlive")
        assert entry.unlocked_by == "Necromancer_T02S01"


def test_an_unlocked_by_that_is_not_text_is_refused(tmp_path: Path) -> None:
    (tmp_path / "runes.toml").write_text(
        '[[rune]]\nid = "R"\ndisplay = "D"\nunlocked_by = 7\nconfidence = 0.9\n'
        '[[rune.evidence]]\ntype = "game_asset"\n'
        'asset_path = "a"\nbuild_id = "1.5d2"\n'
    )
    with pytest.raises(CatalogError, match="unlocked_by must be a non-empty string"):
        load(tmp_path)
