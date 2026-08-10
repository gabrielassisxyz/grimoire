"""Tests for the catalog.

Catalog files are written by the test rather than read from the pack, so a change to
the pilot's own records cannot turn these red for a reason that has nothing to do with
the loader. The pack's real files are checked separately, by loading them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from grimoire.catalog import KINDS, CatalogError, load

PACK = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors"
PACK_CATALOG = PACK / "catalog"
PILOT_BUILD = PACK / "builds/barbarian-electric.toml"

# Every rune identifier this player's save has ever written, across runespresets and
# game stats. It is the advisor's real input, so it is what the catalog is measured
# against rather than a sample chosen to pass.
SAVED_RUNES = [
    "RuneAffinityElectric",
    "RuneAffinityNature",
    "RuneChanceToKill",
    "RuneCriticalMastery",
    "RuneDashMastery",
    "RuneExtraCastFrequencyBleed",
    "RuneExtraCastFrequencyHealthMissing",
    "RuneExtraCritChance",
    "RuneExtraCritDamageAgainstDazed",
    "RuneExtraDamageHealthLessThan",
    "RuneExtraDamageHealthMissing",
    "RuneExtraDamagePerDuplicatedTag",
    "RuneExtraDamagePerEffect",
    "RuneExtraDamageWhileBossIsAlive",
    "RuneInclinationElectric",
    "RuneMasteryArcane",
    "RuneMasteryElectric",
    "RuneMasteryFire",
    "RuneMasterySwing",
    "RuneMaterialCollector",
    "RuneNegativeEffectsDealDamageFaster",
    "RuneRerollMastery",
    "RuneStartWeaponSkill",
    "RuneStunImmune",
    "RuneSynergiesChance",
]


def write(directory: Path, kind: str, body: str) -> None:
    (directory / f"{kind}s.toml").write_text(body)


WEAPON = """
[[weapon]]
id = "WeaponBarbarian-03"
display = "Tempest Battle Axes"
confidence = 0.97

[[weapon.evidence]]
type = "game_screen"
fixture = "a.png"
window = "1896x2097"
build_id = "1.5d2"
"""

RUNE = """
[[rune]]
id = "RuneExtraCritChance"
display = "Vulnerable Target"
slot = "tenacity"
runic_power_cost = 2
confidence = 0.9

[[rune.evidence]]
type = "community_source"
url = "https://example.invalid/sheet"
retrieved = "2026-08-08"
game_version = "1.5d"
"""


class TestResolution:
    def test_a_name_resolves_to_the_identifier_it_has_no_resemblance_to(
        self, tmp_path: Path
    ) -> None:
        # The pair this whole module exists for: nothing about the displayed name
        # could produce the identifier, or the other way round.
        write(tmp_path, "rune", RUNE)
        assert load(tmp_path).id_for("Vulnerable Target") == "RuneExtraCritChance"

    def test_resolution_runs_in_both_directions(self, tmp_path: Path) -> None:
        write(tmp_path, "weapon", WEAPON)
        catalog = load(tmp_path)
        assert catalog.display_for("WeaponBarbarian-03") == "Tempest Battle Axes"
        assert catalog.id_for("Tempest Battle Axes") == "WeaponBarbarian-03"

    def test_the_matching_kind_resolves_rather_than_being_merely_accepted(
        self, tmp_path: Path
    ) -> None:
        # Without this, a resolver that raised whenever a kind was supplied at all
        # would still pass every other test in this class.
        write(tmp_path, "weapon", WEAPON)
        catalog = load(tmp_path)
        assert catalog.id_for("Tempest Battle Axes", kind="weapon") == (
            "WeaponBarbarian-03"
        )

    def test_files_of_different_kinds_load_into_one_catalog(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "weapon", WEAPON)
        write(tmp_path, "rune", RUNE)
        assert len(load(tmp_path)) == 2

    def test_a_missing_file_is_an_empty_kind_rather_than_a_failure(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "rune", RUNE)
        assert len(load(tmp_path)) == 1


class TestEvidenceSurvivesLoading:
    """What a later caller weighs a record by has to reach it intact."""

    def test_the_entry_carries_its_confidence_and_evidence_class(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "weapon", WEAPON)
        entry = load(tmp_path).entry("WeaponBarbarian-03")
        assert (entry.evidence[0].type, entry.confidence) == ("game_screen", 0.97)

    def test_the_detail_of_the_evidence_is_not_discarded(self, tmp_path: Path) -> None:
        # Staleness is decided against the build a record was verified on, so dropping
        # the build id at load time would make the check impossible rather than merely
        # inconvenient. The fixture name has the same problem: a record nobody can
        # trace back to the frame it came from cannot be re-checked.
        write(tmp_path, "weapon", WEAPON)
        detail = load(tmp_path).entry("WeaponBarbarian-03").evidence[0].detail
        assert detail["build_id"] == "1.5d2"
        assert detail["fixture"] == "a.png"

    def test_a_record_can_rest_on_two_independent_readings(
        self, tmp_path: Path
    ) -> None:
        # The reason evidence is a list. A pair that a screen and an experiment both
        # state is stronger than either alone, and a schema holding one class can only
        # record that in prose, where nothing can weigh it.
        write(
            tmp_path,
            "rune",
            RUNE
            + """
[[rune.evidence]]
type = "measured"
procedure = "equip the rune and re-read runespresets"
before = "24 identifiers"
after = "25 identifiers, the new one being RuneExtraCritChance"
""",
        )
        entry = load(tmp_path).entry("RuneExtraCritChance")
        assert [e.type for e in entry.evidence] == ["community_source", "measured"]


class TestRefusal:
    def test_an_unknown_name_names_itself_and_the_fix(self, tmp_path: Path) -> None:
        write(tmp_path, "rune", RUNE)
        with pytest.raises(CatalogError, match="Lord's Bane"):
            load(tmp_path).id_for("Lord's Bane")

    def test_nothing_resolves_by_resemblance(self, tmp_path: Path) -> None:
        # "Vulnerable Targets" is one character away from a record that exists, which
        # is exactly the case where a nearest match would be accepted and be wrong.
        write(tmp_path, "rune", RUNE)
        with pytest.raises(CatalogError):
            load(tmp_path).id_for("Vulnerable Targets")

    def test_asking_for_a_name_as_the_wrong_kind_is_reported(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "weapon", WEAPON)
        with pytest.raises(CatalogError, match="is a weapon in the catalog"):
            load(tmp_path).id_for("Tempest Battle Axes", kind="rune")

    def test_missing_reports_every_gap_in_one_pass(self, tmp_path: Path) -> None:
        write(tmp_path, "rune", RUNE)
        catalog = load(tmp_path)
        wanted = ["RuneExtraCritChance", "RuneLordsBane", "RuneInclinationElectric"]
        assert catalog.missing(wanted) == ["RuneLordsBane", "RuneInclinationElectric"]

    def test_a_record_without_evidence_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n',
        )
        with pytest.raises(CatalogError, match="has no evidence"):
            load(tmp_path)

    def test_an_empty_evidence_list_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\nevidence = []\n',
        )
        with pytest.raises(CatalogError, match="non-empty array"):
            load(tmp_path)

    def test_an_unrecognised_evidence_class_is_refused(self, tmp_path: Path) -> None:
        # A class nobody defined cannot be weighed against the others later, which is
        # the only reason the field exists.
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[weapon.evidence]]\ntype = "someone said so"\n',
        )
        with pytest.raises(CatalogError, match="not one of"):
            load(tmp_path)

    def test_a_class_missing_the_fields_it_owes_is_refused(
        self, tmp_path: Path
    ) -> None:
        # A community source without its URL and retrieval date cannot be checked by
        # anyone, and an unverifiable citation is what a provenance rule exists to
        # prevent. Enforcing it here rather than in a document is the point.
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[weapon.evidence]]\ntype = "community_source"\ngame_version = "1.5d"\n',
        )
        with pytest.raises(CatalogError, match="states no url, no retrieved"):
            load(tmp_path)

    def test_a_save_reading_without_the_write_it_came_from_is_refused(
        self, tmp_path: Path
    ) -> None:
        # A domain has ten slots that the game writes round, so naming the domain
        # without the write counter cites a position rather than a payload, and the
        # payload is what a later reader would be trying to compare against.
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[weapon.evidence]]\ntype = "save_file"\n'
            'domain = "runespresets"\nbuild_id = "1.5d2"\n',
        )
        with pytest.raises(CatalogError, match="states no slot, no write_counter"):
            load(tmp_path)

    def test_evidence_written_as_a_single_table_is_refused(
        self, tmp_path: Path
    ) -> None:
        # The shape a writer reaches for first, and the loader has to say so rather
        # than fail somewhere deeper with a Python type error.
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            'evidence = { type = "measured" }\n',
        )
        with pytest.raises(CatalogError, match="array of tables"):
            load(tmp_path)

    def test_a_confidence_that_is_not_a_number_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = "high"\n'
            '[[weapon.evidence]]\ntype = "game_asset"\n'
            'asset_path = "a"\nbuild_id = "b"\n',
        )
        with pytest.raises(CatalogError, match="confidence must be a number"):
            load(tmp_path)

    def test_a_confidence_outside_the_scale_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "weapon",
            '[[weapon]]\nid = "X"\ndisplay = "Y"\nconfidence = 4\n'
            '[[weapon.evidence]]\ntype = "game_asset"\n'
            'asset_path = "a"\nbuild_id = "b"\n',
        )
        with pytest.raises(CatalogError, match="outside 0.0 to 1.0"):
            load(tmp_path)

    def test_two_records_claiming_one_identifier_stop_the_load(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "rune", RUNE + RUNE.replace("Vulnerable Target", "Other Name"))
        with pytest.raises(CatalogError, match="RuneExtraCritChance"):
            load(tmp_path)

    def test_two_records_claiming_one_name_stop_the_load(self, tmp_path: Path) -> None:
        write(tmp_path, "rune", RUNE + RUNE.replace("RuneExtraCritChance", "RuneOther"))
        with pytest.raises(CatalogError, match="Vulnerable Target"):
            load(tmp_path)

    def test_one_name_claimed_by_two_kinds_stops_the_load(self, tmp_path: Path) -> None:
        # A displayed name is the key a build and a screen reading both arrive with,
        # so letting two kinds hold it would make that key ambiguous everywhere.
        write(tmp_path, "weapon", WEAPON)
        write(
            tmp_path, "rune", RUNE.replace("Vulnerable Target", "Tempest Battle Axes")
        )
        with pytest.raises(CatalogError, match="claimed by both"):
            load(tmp_path)


class TestThePackItself:
    """The pilot pack's own files, loaded as shipped."""

    def test_the_pack_catalog_loads(self) -> None:
        assert len(load(PACK_CATALOG)) > 0

    def test_the_pilot_weapon_resolves(self) -> None:
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Tempest Battle Axes") == "WeaponBarbarian-03"

    def test_the_boss_damage_rune_resolves(self) -> None:
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Lord's Bane") == "RuneExtraDamageWhileBossIsAlive"

    def test_the_neighbouring_rune_of_the_pair_resolves(self) -> None:
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Skill Affinity: Electric") == "RuneAffinityElectric"

    def test_the_experiment_is_recorded_on_the_record_it_settled(self) -> None:
        # The pair rests on an experiment, and a record claiming 1.0 without the
        # reading that earns it is the failure the evidence list was added to stop.
        entry = load(PACK_CATALOG).entry("RuneAffinityElectric")
        assert "measured" in {e.type for e in entry.evidence}
        assert entry.confidence == 1.0

    def test_the_two_runes_of_the_pair_resolve_to_different_identifiers(self) -> None:
        # The pair the pack exists to keep apart. A resolver that ever collapsed them
        # would answer plausibly and send the advisor after the wrong rune.
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Skill Affinity: Electric") == "RuneAffinityElectric"
        assert catalog.id_for("Skill Inclination: Electric") == (
            "RuneInclinationElectric"
        )

    def test_every_reference_the_pilot_build_makes_resolves(self) -> None:
        # The whole point of the catalog, asserted against the build as shipped: if a
        # reference stops resolving, this says so before anything downstream does.
        catalog = load(PACK_CATALOG)
        build = tomllib.loads(PILOT_BUILD.read_text())
        wanted = [r["id"] for r in build["runes"]] + [build["meta"]["weapon"]]
        assert catalog.missing(wanted) == []

    def test_every_rune_this_save_has_ever_recorded_resolves(self) -> None:
        # The identifiers this save carries are the advisor's real input, so they are
        # what the catalog is measured against rather than a sample chosen to pass. Ten
        # of the twenty-five resolved when this was first written, and the shortfall was
        # asserted as a named boundary through two rounds of narrowing it. There is no
        # boundary left to name.
        catalog = load(PACK_CATALOG)
        assert catalog.missing(SAVED_RUNES) == []

    def test_a_pair_that_only_the_install_could_produce(self) -> None:
        # Neither source reaches this on its own: the identifier exists only in the
        # install and the name only on the wiki, and nothing about one suggests the
        # other. It is here so the join is pinned by a case that cannot be guessed.
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("All or Nothing") == "RuneSetHealthToOne"

    def test_the_extracted_records_cite_the_install_they_were_read_from(self) -> None:
        catalog = load(PACK_CATALOG)
        entry = catalog.entry("RuneSetHealthToOne")
        asset = next(e for e in entry.evidence if e.type == "game_asset")
        assert asset.detail["build_id"] == "1.5d2"

    def test_the_two_contested_magnitudes_are_the_ones_the_game_stores(self) -> None:
        # Two community sources gave 25% for both of these and the spreadsheet gave 50
        # and 30. The installed game stores 50 and 30, so the pair of sources is stale
        # together. Pinned here because it is the one place a later re-extraction could
        # quietly revert to the wiki's numbers.
        catalog = load(PACK_CATALOG)
        assert catalog.entry("RuneExtraCritChance").parameters == (50.0,)
        assert catalog.entry("RuneExtraDamageWhileBossIsAlive").parameters == (30.0,)

    def test_a_record_whose_parameters_reproduce_its_own_prose(self) -> None:
        # The control for the reading above. This record's effect was written from the
        # spreadsheet, before any extraction existed, and reads "0.5% per stack, caps at
        # 25%". The install stores exactly those two numbers in that order. Asserted as
        # a sequence rather than as membership, because a field that landed on both
        # values in the wrong order would not be the field this claims to have found.
        entry = load(PACK_CATALOG).entry("RuneExtraCritDamageAgainstDazed")
        assert entry.parameters == (0.5, 25.0)

    def test_the_family_rule_still_produces_what_experiment_established(self) -> None:
        # The three pairs the rule was checked against, two of them settled by equipping
        # the rune and reading the save back. They are asserted here as well as in the
        # extractor so that hand-editing the file cannot drift from the rule either.
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Skill Affinity: Electric") == "RuneAffinityElectric"
        assert catalog.id_for("Skill Inclination: Electric") == (
            "RuneInclinationElectric"
        )
        assert catalog.id_for("Skill Mastery: Electric") == "RuneMasteryElectric"

    def test_runes_that_merely_contain_a_family_word_are_not_named_by_the_rule(
        self,
    ) -> None:
        # The boundary the rule would cross if the prefix were not anchored and the
        # suffix not restricted to a known type. Each of these ends in a family word and
        # belongs to none of them, so a looser rule would rename them into nonsense.
        catalog = load(PACK_CATALOG)
        assert catalog.display_for("RuneCriticalMastery") == "Critical Mastery"
        assert catalog.display_for("RuneRerollMastery") == "Reroll Mastery"

    def test_all_three_families_carry_the_same_skill_types(self) -> None:
        # The set of types was derived rather than written down, as the suffixes the
        # three families share. If one family gained an identifier the others lack, it
        # was never a skill type and this is what says so.
        catalog = load(PACK_CATALOG)
        families = {}
        for family in ("Affinity", "Inclination", "Mastery"):
            prefix = f"Rune{family}"
            families[family] = {
                e.id.removeprefix(prefix)
                for e in catalog.entries_of_kind("rune")
                if e.id.startswith(prefix) and e.display.startswith("Skill ")
            }
        assert len(set(map(frozenset, families.values()))) == 1
        assert len(families["Mastery"]) == 15

    def test_an_achievement_rune_joined_on_its_unlock_condition(self) -> None:
        # Neither side suggests the other: the identifier says the rune grants immunity
        # to stuns and the name is Surefooted. What joined them is the condition, an
        # achievement called ReachExperienceLevel-65 against a wiki row reading "Reach
        # experience level 65 in a single match".
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Surefooted") == "RuneStunImmune"

    def test_the_one_achievement_rune_joined_on_its_effect_instead(self) -> None:
        # Its condition is the single place the sources contradict each other, boss rush
        # cycle 1 against Overlord Mode cycle 3, so the condition rule cannot reach it.
        # The effect can: rolling damage twice and keeping the highest, against an
        # identifier that says it rerolls damage rolls.
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("ControlledChaos") == "RuneRerollDamageRolls"

    def test_no_record_is_less_certain_than_the_pack_already_is(self) -> None:
        # Nothing reads confidence yet. The advisor will, once it has a ranking to
        # refuse, and until then the field is written and never checked, which is how a
        # record arrives at 0.5 with nobody noticing. This is not that threshold and is
        # not a policy about how certain a record must be: it pins where the pack
        # actually sits, so dropping below it is a line someone changes on purpose.
        # The floor is the one achievement resting on a save reading and a wiki row
        # with no confirmation from the install.
        catalog = load(PACK_CATALOG)
        records = [e for kind in KINDS for e in catalog.entries_of_kind(kind)]
        assert len(records) == len(catalog)
        assert min(e.confidence for e in records) == 0.8

    def test_every_rune_record_carries_a_cost_and_a_slot(self) -> None:
        # The budget check reads both off every record it is handed, and a rune missing
        # either would be silently counted as free or as belonging to no section.
        runes = load(PACK_CATALOG).entries_of_kind("rune")
        assert len(runes) == 128
        assert all(e.slot in ("tenacity", "versatility") for e in runes)

    def test_a_rune_without_a_cost_is_refused(self, tmp_path: Path) -> None:
        # It would otherwise load as free. The budget check reads the field off every
        # record it is handed, so a missing one is not a gap it can report, it is a
        # wrong total that looks like a right one.
        write(tmp_path, "rune", RUNE.replace("runic_power_cost = 2\n", ""))
        with pytest.raises(CatalogError, match="has no runic_power_cost"):
            load(tmp_path)

    def test_a_rune_without_a_slot_is_refused(self, tmp_path: Path) -> None:
        write(tmp_path, "rune", RUNE.replace('slot = "tenacity"\n', ""))
        with pytest.raises(CatalogError, match="has no slot"):
            load(tmp_path)

    def test_a_slot_that_is_not_a_section_of_the_game_is_refused(
        self, tmp_path: Path
    ) -> None:
        # A misspelling would leave the rune counted against no section at all, so a
        # build could hold five tenacity runes and pass the slot limit.
        write(tmp_path, "rune", RUNE.replace('"tenacity"', '"tenacoty"'))
        with pytest.raises(CatalogError, match="tenacoty"):
            load(tmp_path)

    def test_a_parameter_that_is_not_finite_is_refused(self, tmp_path: Path) -> None:
        # TOML has nan and inf and both are floats, so a type check alone admits them.
        # A non-finite magnitude is a number-shaped hole that would travel through the
        # effect engine without ever looking wrong.
        write(
            tmp_path,
            "rune",
            RUNE.replace("confidence", "parameters = [nan]\nconfidence"),
        )
        with pytest.raises(CatalogError, match="not a finite number"):
            load(tmp_path)
