"""The extractor's record writer, tested without a game install.

Only the writer. Everything else in tools/extract_runes.py reads a licensed copy of the
game, which no test may touch, so what is checkable here is that whatever the three
joins produce comes out as a record this project can read back. That is the failure
worth catching cheaply: the loader gained a required field, two of the three emitters
were updated, and a whole extraction printed records the same program then refused.
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
