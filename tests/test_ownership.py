"""Rune ownership derived from the skill tree nodes a save records.

Hermetic by construction: the real save is the player's own data and is never tracked,
so these build the node list rather than read one. That is not a compromise, because
what is under test is the rule joining nodes to records, not the save parser, which has
its own tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.achievements import Achievement
from grimoire.catalog import CatalogError, load
from grimoire.ownership import OwnershipError, read_rune_ownership
from grimoire.skilltree import SkillTreeNode

PACK_CATALOG = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors/catalog"

RUNES_WITH_A_NODE = """
[[rune]]
id = "RuneExtraCritChance"
display = "Vulnerable Target"
slot = "tenacity"
runic_power_cost = 2
unlocked_by = "Houndmaster_T03S01"
confidence = 0.9
[[rune.evidence]]
type = "game_asset"
asset_path = "Soulstone Survivors_Data/resources.assets"
build_id = "1.5d2"

[[rune]]
id = "RuneExtraDamageWhileBossIsAlive"
display = "Lord's Bane"
slot = "tenacity"
runic_power_cost = 3
unlocked_by = "Necromancer_T02S01"
confidence = 0.9
[[rune.evidence]]
type = "game_asset"
asset_path = "Soulstone Survivors_Data/resources.assets"
build_id = "1.5d2"

[[rune]]
id = "RuneMasteryFire"
display = "Skill Mastery: Fire"
slot = "versatility"
runic_power_cost = 0
unlocked_by_achievement = "CompleteMatchInLessThanTime12Pyromancer"
confidence = 0.9
[[rune.evidence]]
type = "community_source"
url = "https://soulstone-survivors.fandom.com/wiki/Runes"
retrieved = "2026-08-08"
game_version = "unstated"

[[rune]]
id = "RuneNamesNothing"
display = "Names nothing"
slot = "versatility"
runic_power_cost = 0
confidence = 0.9
[[rune.evidence]]
type = "game_asset"
asset_path = "a"
build_id = "1.5d2"
"""


@pytest.fixture
def catalog(tmp_path: Path):
    (tmp_path / "runes.toml").write_text(RUNES_WITH_A_NODE)
    return load(tmp_path)


def bought(*node_ids: str) -> list[SkillTreeNode]:
    return [SkillTreeNode(node_id=n, level=1) for n in node_ids]


def recorded(**completion: bool) -> list[Achievement]:
    """Achievements the save knows about, each done or not."""
    return [
        Achievement(achievement_id=k, progress=1.0 if v else 0.4, completed=v)
        for k, v in completion.items()
    ]


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
            "RuneNamesNothing",
        ]
        assert len(set(total)) == len(total)


class TestAgainstTheRealPack:
    def test_the_pack_splits_into_decidable_and_not(self) -> None:
        # Sixty-six runes name a node and sixty-two do not, which is the shape the
        # advisor has to report. Having a record and being answerable from the save are
        # separate things, and the gap between them grew as the catalog filled: every
        # rune is catalogued now, and the ones no tree grants are exactly the ones this
        # still cannot decide.
        ownership = read_rune_ownership(load(PACK_CATALOG), [])
        assert len(ownership.not_owned) == 66
        assert len(ownership.undecidable) == 62

    def test_a_node_the_pack_names_is_spelled_the_way_the_save_spells_it(self) -> None:
        # The join is a string match against save data, so a node written in the
        # catalog's own style rather than the game's would fail silently and report
        # everything as unowned.
        entry = load(PACK_CATALOG).entry("RuneExtraDamageWhileBossIsAlive")
        assert entry.unlocked_by == "Necromancer_T02S01"


def test_an_unlocked_by_that_is_not_text_is_refused(tmp_path: Path) -> None:
    (tmp_path / "runes.toml").write_text(
        '[[rune]]\nid = "R"\ndisplay = "D"\nslot = "tenacity"\n'
        "runic_power_cost = 0\nunlocked_by = 7\nconfidence = 0.9\n"
        '[[rune.evidence]]\ntype = "game_asset"\n'
        'asset_path = "a"\nbuild_id = "1.5d2"\n'
    )
    with pytest.raises(CatalogError, match="unlocked_by must be a non-empty string"):
        load(tmp_path)


def test_a_rune_naming_both_unlock_routes_is_refused(tmp_path: Path) -> None:
    # Ownership decides on the node and never reaches the achievement, so a record
    # carrying both would report the rune as not owned while the achievement that
    # granted it sits completed in the save. Refusing it at load keeps that reading
    # from being made by whichever branch happened to run first.
    (tmp_path / "runes.toml").write_text(
        '[[rune]]\nid = "R"\ndisplay = "D"\nslot = "tenacity"\n'
        "runic_power_cost = 0\n"
        'unlocked_by = "Necromancer_T02S01"\nunlocked_by_achievement = "Something"\n'
        "confidence = 0.9\n"
        '[[rune.evidence]]\ntype = "game_asset"\n'
        'asset_path = "a"\nbuild_id = "1.5d2"\n'
    )
    with pytest.raises(CatalogError, match="names both unlocked_by"):
        load(tmp_path)


def test_asking_about_a_rune_the_catalog_never_had_is_loud(catalog) -> None:
    # A misspelled identifier used to answer "undecidable", which is a real state for a
    # rune no tree grants. So a typo in a build read as a rune the save merely cannot
    # see, and the two are the opposite of each other: one is a gap in the catalog and
    # the other is a limit of the save.
    ownership = read_rune_ownership(catalog, bought("Houndmaster_T03S01"))
    with pytest.raises(OwnershipError, match="RuneMasteryElectirc"):
        ownership.describe("RuneMasteryElectirc")


class TestWhatTheAchievementsProve:
    def test_a_rune_whose_achievement_is_complete_is_owned(self, catalog) -> None:
        ownership = read_rune_ownership(
            catalog,
            bought(),
            recorded(CompleteMatchInLessThanTime12Pyromancer=True),
        )
        assert ownership.describe("RuneMasteryFire") == "owned"

    def test_a_rune_whose_achievement_is_unfinished_is_not_owned(self, catalog) -> None:
        ownership = read_rune_ownership(
            catalog,
            bought(),
            recorded(CompleteMatchInLessThanTime12Pyromancer=False),
        )
        assert ownership.describe("RuneMasteryFire") == "not owned"

    def test_an_achievement_the_save_never_mentions_is_undecidable(
        self, catalog
    ) -> None:
        # Absence is not incompletion, and reading it as one reported three runes this
        # player has equipped as runes they do not own. The install names achievements
        # the save has no record of at all, so this is the common case rather than a
        # defensive one.
        ownership = read_rune_ownership(catalog, bought(), recorded(SomethingElse=True))
        assert ownership.describe("RuneMasteryFire") == "undecidable"

    def test_without_the_achievement_domain_those_runes_stay_undecidable(
        self, catalog
    ) -> None:
        # A caller that has not opened that file gets an honest unknown, not sixty-two
        # runes reported as missing on the strength of evidence nobody read.
        ownership = read_rune_ownership(catalog, bought())
        assert ownership.describe("RuneMasteryFire") == "undecidable"

    def test_a_rune_naming_neither_is_a_gap_in_the_catalog(self, catalog) -> None:
        ownership = read_rune_ownership(catalog, bought(), recorded(Anything=True))
        assert ownership.describe("RuneNamesNothing") == "undecidable"
