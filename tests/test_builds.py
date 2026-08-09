"""Tests for build loading, plus one check that runs against the shipped pack.

The synthetic cases build their own TOML. The last class loads the real pilot file,
which is tracked project data rather than someone's private save, so depending on it
is legitimate and it is the only way to notice that the shipped build stopped being
loadable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.builds import Build, BuildError, load

PACK = Path(__file__).parent.parent / "packs" / "soulstone-survivors" / "builds"

MINIMAL = """
[meta]
build_id = "x"
character = "C"
weapon = "W"
verified_against = "1.0"
confidence = 0.5

[[skills]]
id = "Alpha"
evidence = { type = "community_source" }
"""


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "b.toml"
    path.write_text(body)
    return path


class TestLoad:
    def test_minimal_build_loads(self, tmp_path: Path) -> None:
        build = load(write(tmp_path, MINIMAL))
        assert isinstance(build, Build)
        assert build.skill_ids == ("Alpha",)
        assert build.rune_ids == ()

    def test_invalid_toml_names_the_file(self, tmp_path: Path) -> None:
        with pytest.raises(BuildError, match="not valid TOML"):
            load(write(tmp_path, "[meta"))

    def test_missing_meta_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(BuildError, match=r"missing \[meta\]"):
            load(write(tmp_path, '[[skills]]\nid = "A"\n'))

    @pytest.mark.parametrize(
        "key", ["build_id", "character", "weapon", "verified_against", "confidence"]
    )
    def test_each_meta_field_is_required(self, tmp_path: Path, key: str) -> None:
        body = "\n".join(ln for ln in MINIMAL.splitlines() if not ln.startswith(key))
        with pytest.raises(BuildError, match=key):
            load(write(tmp_path, body))

    def test_a_build_with_no_skills_is_refused(self, tmp_path: Path) -> None:
        body = MINIMAL.split("[[skills]]")[0]
        with pytest.raises(BuildError, match="no skills"):
            load(write(tmp_path, body))

    def test_an_entry_without_evidence_is_refused(self, tmp_path: Path) -> None:
        # The rule that matters most: a record with no evidence cannot be aged, and a
        # record that cannot be aged quietly turns into a guess as the game moves.
        body = MINIMAL.replace('evidence = { type = "community_source" }', "")
        with pytest.raises(BuildError, match="no evidence"):
            load(write(tmp_path, body))

    def test_an_entry_without_an_id_is_refused(self, tmp_path: Path) -> None:
        body = MINIMAL.replace('id = "Alpha"', "")
        with pytest.raises(BuildError, match="has no id"):
            load(write(tmp_path, body))


class TestInternalReferences:
    def test_a_focus_skill_the_build_does_not_have_is_refused(
        self, tmp_path: Path
    ) -> None:
        # The failure this exists for: a typo in a priority rule silently downgrades
        # the build's main damage source and nothing downstream would ever notice.
        body = MINIMAL + '\n[priorities]\nfocus_skill = "Alfa"\n'
        with pytest.raises(BuildError, match="is not one of this build's skills"):
            load(write(tmp_path, body))

    def test_a_focus_skill_the_build_has_is_accepted(self, tmp_path: Path) -> None:
        body = MINIMAL + '\n[priorities]\nfocus_skill = "Alpha"\n'
        assert load(write(tmp_path, body)).skill_ids == ("Alpha",)


class TestShippedPilot:
    @pytest.fixture
    def pilot(self) -> Build:
        return load(PACK / "barbarian-electric.toml")

    def test_it_loads(self, pilot: Build) -> None:
        assert pilot.build_id == "barbarian-electric"
        assert pilot.character == "Barbarian"

    def test_it_records_the_game_build_it_was_verified_against(
        self, pilot: Build
    ) -> None:
        assert pilot.verified_against

    def test_known_disagreements_are_carried_rather_than_resolved_silently(
        self, pilot: Build
    ) -> None:
        # Three sources disagree with the guide on the installed version. Losing that
        # would be worse than never recording it, since the file would then look
        # settled while resting on numbers known to be wrong.
        assert len(pilot.disagreements) >= 3

    def test_confidence_stays_below_one_while_references_are_unresolved(
        self, pilot: Build
    ) -> None:
        if pilot.has_unresolved_references:
            assert pilot.confidence < 1.0
