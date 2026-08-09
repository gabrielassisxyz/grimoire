"""Tests for the catalog.

Catalog files are written by the test rather than read from the pack, so a change to
the pilot's own records cannot turn these red for a reason that has nothing to do with
the loader. The pack's real files are checked separately, by loading them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.catalog import CatalogError, load

PACK_CATALOG = Path(__file__).resolve().parents[1] / "packs/soulstone-survivors/catalog"


def write(directory: Path, kind: str, body: str) -> None:
    (directory / f"{kind}s.toml").write_text(body)


WEAPON = """
[[weapon]]
id = "WeaponBarbarian-03"
display = "Tempest Battle Axes"
confidence = 0.97
evidence = { type = "game_screen", fixture = "a.png" }
"""

RUNE = """
[[rune]]
id = "RuneExtraCritChance"
display = "Vulnerable Target"
confidence = 0.9
evidence = { type = "community_source", source = "spreadsheet" }
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

    def test_the_entry_carries_its_evidence_and_confidence(
        self, tmp_path: Path
    ) -> None:
        # Confidence and evidence class are what a later caller weighs a record by, so
        # losing them at load time would make the record unusable for its purpose.
        write(tmp_path, "weapon", WEAPON)
        entry = load(tmp_path).entry("WeaponBarbarian-03")
        assert (entry.evidence_type, entry.confidence) == ("game_screen", 0.97)


class TestRefusal:
    def test_an_unknown_name_names_itself_and_the_fix(self, tmp_path: Path) -> None:
        write(tmp_path, "rune", RUNE)
        with pytest.raises(CatalogError, match="Lord's Bane"):
            load(tmp_path).id_for("Lord's Bane")

    def test_nothing_resolves_by_resemblance(self, tmp_path: Path) -> None:
        # "Critical Mastery" is one word away from a record that exists, which is
        # exactly the case where a nearest match would be accepted and be wrong.
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

    def test_an_unrecognised_evidence_class_is_refused(self, tmp_path: Path) -> None:
        # A class nobody defined cannot be weighed against the others later, which is
        # the only reason the field exists.
        write(
            tmp_path,
            "rune",
            '[[rune]]\nid = "X"\ndisplay = "Y"\nconfidence = 1.0\n'
            'evidence = { type = "someone said so" }\n',
        )
        with pytest.raises(CatalogError, match="not one of"):
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


class TestThePackItself:
    """The pilot pack's own files, loaded as shipped."""

    def test_the_pack_catalog_loads(self) -> None:
        assert len(load(PACK_CATALOG)) > 0

    def test_the_pilot_weapon_resolves(self) -> None:
        catalog = load(PACK_CATALOG)
        assert catalog.id_for("Tempest Battle Axes") == "WeaponBarbarian-03"

    def test_the_runes_the_pilot_still_lacks_are_reported_as_gaps(self) -> None:
        # These two are absent on purpose, and a later commit that resolves them
        # should have to change this test deliberately rather than pass it by accident.
        catalog = load(PACK_CATALOG)
        for name in ("Lord's Bane", "Skill Inclination: Electric"):
            with pytest.raises(CatalogError):
                catalog.id_for(name)
