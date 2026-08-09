"""Tests for the catalog.

Catalog files are written by the test rather than read from the pack, so a change to
the pilot's own records cannot turn these red for a reason that has nothing to do with
the loader. The pack's real files are checked separately, by loading them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from grimoire.catalog import CatalogError, load

PACK = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors"
PACK_CATALOG = PACK / "catalog"
PILOT_BUILD = PACK / "builds/barbarian-electric.toml"


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
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n',
        )
        with pytest.raises(CatalogError, match="has no evidence"):
            load(tmp_path)

    def test_an_empty_evidence_list_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\nevidence = []\n',
        )
        with pytest.raises(CatalogError, match="non-empty array"):
            load(tmp_path)

    def test_an_unrecognised_evidence_class_is_refused(self, tmp_path: Path) -> None:
        # A class nobody defined cannot be weighed against the others later, which is
        # the only reason the field exists.
        write(
            tmp_path,
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[rune.evidence]]\ntype = "someone said so"\n',
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
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[rune.evidence]]\ntype = "community_source"\ngame_version = "1.5d"\n',
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
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            '[[rune.evidence]]\ntype = "save_file"\n'
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
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            'evidence = { type = "measured" }\n',
        )
        with pytest.raises(CatalogError, match="array of tables"):
            load(tmp_path)

    def test_a_confidence_that_is_not_a_number_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = "high"\n'
            '[[rune.evidence]]\ntype = "game_asset"\n'
            'asset_path = "a"\nbuild_id = "b"\n',
        )
        with pytest.raises(CatalogError, match="confidence must be a number"):
            load(tmp_path)

    def test_a_confidence_outside_the_scale_is_refused(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 4\n'
            '[[rune.evidence]]\ntype = "game_asset"\n'
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
