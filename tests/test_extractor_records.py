"""The extractor's pure functions, tested without a game install.

Everything in tools/extract_runes.py that opens the install reads a licensed copy of the
game, which no test may touch. What is left is checkable and worth checking: that
whatever the three joins produce comes out as a record this project can read back, and
that the install-to-save identifier translation says what it is meant to say.

Both have failed before. The loader gained a required field, two of the three emitters
were updated, and a whole extraction printed records the same program then refused. The
translation is the quieter of the two: it writes an identifier that is looked up in a
save, so a wrong rule produces a plausible string that simply never matches, and the
rune it belongs to reads as undecidable rather than as an error.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

from grimoire.catalog import load

ROOT = Path(__file__).resolve().parents[1]


def load_extractor():
    spec = importlib.util.spec_from_file_location(
        "extract_runes", ROOT / "tools/extract_runes.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def extractor():
    return load_extractor()


def written(extractor, capsys, **kwargs) -> str:
    defaults = {
        "identifier": "RuneX",
        "display": "Some Rune",
        "slot": "tenacity",
        "cost": 3,
        "values": [50.0],
        "evidence": [
            {"type": "game_asset", "asset_path": "a/b.assets", "build_id": "1.5d2"}
        ],
    }
    extractor.print_record(**{**defaults, **kwargs})
    return capsys.readouterr().out


def test_a_written_record_loads_back_through_the_catalog(
    extractor, capsys, tmp_path: Path
) -> None:
    # The round trip, which is the whole point. A record this program writes and then
    # cannot read is the defect this file exists for.
    (tmp_path / "runes.toml").write_text(written(extractor, capsys))
    catalog = load(tmp_path)
    assert catalog.entry("RuneX").display == "Some Rune"
    assert catalog.entry("RuneX").runic_power_cost == 3


def test_the_cost_is_written_even_when_it_is_zero(extractor, capsys) -> None:
    # A falsy value is exactly what an emitter drops by accident, and zero is the cost
    # of every versatility rune, so it is the common case rather than an edge one.
    assert "runic_power_cost = 0" in written(extractor, capsys, cost=0)


def test_a_record_with_no_parameters_omits_the_key_rather_than_writing_an_empty_list(
    extractor, capsys
) -> None:
    text = written(extractor, capsys, values=[])
    assert "parameters" not in text
    assert tomllib.loads(text)["rune"][0]["runic_power_cost"] == 3


def test_extra_fields_are_written_as_the_record_owns_them(extractor, capsys) -> None:
    text = written(extractor, capsys, extra={"unlocked_by": "Necromancer_T02S01"})
    assert tomllib.loads(text)["rune"][0]["unlocked_by"] == "Necromancer_T02S01"


# Install name against save name, every pair taken from the profile the join was
# falsified against rather than invented here. A rule that stops reproducing these is
# writing identifiers no save will ever match.
TRANSLATIONS = [
    (
        "Achievement-ReachPrestigeLevelWithCharacter-Elementalist-30",
        "PrestigeElementalist30",
    ),
    (
        "Achievement-CompleteMatchInLessThanTimeWithCharacter-12-Rogue",
        "CompleteMatchInLessThanTime12Rogue",
    ),
    (
        "Achievement-ReachAffixTierProgressionPerMap-Desert-6",
        "CompleteAffixTierSurvivorsDesert6",
    ),
    ("Achievement-ReachTotalEnemiesKilled-500000", "ReachTotalEnemiesKilled500000"),
    ("Achievement-CompleteEndlessCycle-3", "CompleteEndlessCycle3"),
]


@pytest.mark.parametrize(("install", "save"), TRANSLATIONS)
def test_an_install_achievement_translates_to_the_id_the_save_writes(
    extractor, install: str, save: str
) -> None:
    assert extractor.save_achievement_id(install) == save


def test_the_timed_match_rule_puts_the_time_before_the_character(extractor) -> None:
    # The two groups of that rule are interchangeable as far as the pattern is
    # concerned, and swapping them yields CompleteMatchInLessThanTimeRogue12, which is
    # a string no save contains. Nothing else in the suite would notice.
    translated = extractor.save_achievement_id(
        "Achievement-CompleteMatchInLessThanTimeWithCharacter-12-Rogue"
    )
    assert translated.index("12") < translated.index("Rogue")


class TestWhichAchievementGrantsARune:
    def test_a_single_claim_resolves_to_the_translated_id(self, extractor) -> None:
        resolved = extractor.resolve_claimants(
            {"RuneX": {"Achievement-CompleteEndlessCycle-3"}}
        )
        assert resolved == {"RuneX": "CompleteEndlessCycle3"}

    def test_a_superseded_twin_does_not_win_by_being_read_first(
        self, extractor
    ) -> None:
        # RuneSynergiesChance's case. Both objects are in the install, the save only
        # ever writes the live id, and taking whichever UnityPy yielded first left the
        # rune permanently undecidable for a player who has it equipped.
        resolved = extractor.resolve_claimants(
            {
                "RuneSynergiesChance": {
                    "Achievement-CompleteEndlessCycle-3-old",
                    "Achievement-CompleteEndlessCycle-3",
                }
            }
        )
        assert resolved == {"RuneSynergiesChance": "CompleteEndlessCycle3"}

    def test_two_live_claims_stop_the_extraction_and_name_both(self, extractor) -> None:
        with pytest.raises(SystemExit, match="RuneX is granted by"):
            extractor.resolve_claimants(
                {"RuneX": {"Achievement-CompleteEndlessCycle-3", "Achievement-Other"}}
            )

    def test_a_rune_only_a_superseded_achievement_grants_is_reported(
        self, extractor
    ) -> None:
        # Silently dropping it would leave the rune with no unlock route at all, which
        # reads as a catalog gap rather than as a patch having moved something.
        with pytest.raises(SystemExit, match="CompleteEndlessCycle-3-old"):
            extractor.resolve_claimants(
                {"RuneX": {"Achievement-CompleteEndlessCycle-3-old"}}
            )


def test_every_evidence_entry_keeps_all_of_its_fields(extractor, capsys) -> None:
    # A community source that lost its url or its retrieval date would be refused by the
    # loader, which is the guard; this checks the writer does not reach that point.
    text = written(
        extractor,
        capsys,
        evidence=[
            {"type": "game_asset", "asset_path": "a", "build_id": "1.5d2"},
            {
                "type": "community_source",
                "url": "https://example.invalid/page",
                "retrieved": "2026-08-08",
                "game_version": "unstated",
            },
        ],
    )
    entries = tomllib.loads(text)["rune"][0]["evidence"]
    assert [e["type"] for e in entries] == ["game_asset", "community_source"]
    assert entries[1]["url"] == "https://example.invalid/page"
