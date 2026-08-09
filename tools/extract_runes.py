"""Read rune identifiers out of an installed game and pair them with display names.

Run offline, never from the advisor: it needs UnityPy and a licensed install, and it
writes catalog records that are reviewed before they are committed. Nothing it reads is
ever tracked; only the normalized pairs it prints are.

    uv run --group extract python tools/extract_runes.py <install-dir> <wiki-dir>

The join is the whole point, so it is worth stating. The install knows identifiers and
knows which skill tree node grants each one; it does not store display names anywhere a
reader can reach, because the interface resolves them through a localisation key that no
rune record carries. The wiki knows display names and the soulstone threshold that
unlocks each. The two meet at the node: tier 2, 3 and 4 of a character's tree grant one
rune each, and the wiki lists the same three against thresholds of 30,000, 60,000 and a
third. That correspondence is a hypothesis, so the script refuses to emit anything
unless it still reproduces the pairs that were established independently.
"""

from __future__ import annotations

import pathlib
import re
import sys

NODE_NAME = re.compile(r"([A-Za-z]+)_T(\d\d)S\d\d")
IDENTIFIER = re.compile(rb"[A-Za-z][A-Za-z0-9_\-]{5,60}")
# The cost is signed. Demonic Pact is written -2 because it raises the runic power
# ceiling instead of spending from it, so a pattern that only accepts digits drops the
# one rune the budget arithmetic most needs to know about.
WIKI_ROW = re.compile(
    r"\|\s*\|?\s*([A-Z][^|]*?)RUNIC POWER COST:\s*(-?\d+)UNLOCK:\s*([\d,]+)"
)

# Tier of the granting node against the threshold the wiki prints for the same rune.
# The third tier's threshold is rendered inconsistently across pages, so it is matched
# by elimination rather than by its value.
TIER_THRESHOLD = {2: "30000", 3: "60000"}

# Pairs settled by tooltip or by experiment before this script existed. They are the
# test: a join that stops reproducing them is wrong, whatever else it produces.
ANCHORS = {
    "RuneExtraCritChance": "Vulnerable Target",
    "RuneExtraDamageWhileBossIsAlive": "Lord's Bane",
    "RuneExtraCritDamageAgainstDazed": "Vulnerable Exploit",
    # Not a tooltip, but an identity: an identifier that says the health is set to one
    # against the only rune whose text says the maximum health is set to 1. It pins the
    # tier correspondence at the one tier the three above leave untested.
    "RuneSetHealthToOne": "All or Nothing",
}

# The wiki names a character in prose; the install names the same one in an identifier,
# and four of them disagree outright. Each was settled by reading the effect rather than
# the position, so each is a second confirmation of the tier correspondence rather than
# a consequence of it:
#
#   Pirate       is Cursed Captain  RuneDrunkenEffect / Pirate's Rum, "makes you drunk"
#   Rogue        is Assassin        RuneSetHealthToOne / All or Nothing
#   Bloodmage    is Chaoswalker     RuneIncreaseDamageButSkillAreRandom / Gambler
#   Spellbreaker is Spellblade      RuneBanishEpicLegendary / Commoner
#
# All three of each pair's runes line up this way, not just the one quoted.
WIKI_TO_INSTALL = {
    "the-arcane-weaver": "ArcaneWeaver",
    "the-assassin": "Rogue",
    "the-barbarian": "Barbarian",
    "the-beastmaster": "Beastmaster",
    "the-chaoswalker": "Bloodmage",
    "the-cursed-captain": "Pirate",
    "the-death-knight": "DeathKnight",
    "the-demon-hunter": "DemonHunter",
    "the-elementalist": "Elementalist",
    "the-engineer": "Engineer",
    "the-hound-master": "Houndmaster",
    "the-legionnaire": "Legionnaire",
    "the-machinist": "Machinist",
    "the-monkey-king": "MonkeyKing",
    "the-myrmidon": "Myrmidon",
    "the-necromancer": "Necromancer",
    "the-paladin": "Paladin",
    "the-pyromancer": "Pyromancer",
    "the-samurai": "Samurai",
    "the-sentinel": "Sentinel",
    "the-shaman": "Shaman",
    "the-spellblade": "Spellbreaker",
}


def read_build_id(install: pathlib.Path) -> str:
    """The build this describes, so that a later patch is a detectable difference."""
    info = (install / "build_info.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Version\s+(\S+)", info)
    if not match:
        raise SystemExit(f"no version line in {install / 'build_info.txt'}")
    return match.group(1)


def read_grants(assets: pathlib.Path) -> dict[str, tuple[str, int]]:
    """Map each rune identifier to the character and tier of the node that grants it."""
    import UnityPy

    env = UnityPy.load(str(assets))
    grants: dict[str, tuple[str, int]] = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            name = obj.read(check_read=False).m_Name
        except Exception:  # noqa: BLE001 - an unreadable object is simply not a node
            continue
        node = NODE_NAME.fullmatch(name or "")
        if not node:
            continue
        for token in IDENTIFIER.findall(obj.get_raw_data()):
            identifier = token.decode()
            if identifier.startswith("Rune"):
                grants[identifier] = (node.group(1), int(node.group(2)))
    return grants


def read_wiki(wiki: pathlib.Path) -> dict[str, tuple[dict[str, tuple[str, int]], str]]:
    """Per character, the rows against each threshold and the page they were read from.

    The URL travels with the rows rather than being rebuilt from the character
    later: the install and the wiki disagree on four names, so a URL assembled from
    the install's name would cite a page that does not exist.
    """
    pages: dict[str, tuple[dict[str, tuple[str, int]], str]] = {}
    for path in sorted(wiki.glob("the-*.md")):
        stem = path.stem.rsplit("--", 1)[0]
        character = WIKI_TO_INSTALL.get(stem)
        if not character:
            continue
        text = path.read_text(encoding="utf-8")
        section = re.search(r"## Runes Unlock(.*?)(?=\n#|\Z)", text, re.S)
        if not section:
            continue
        source = re.search(r'^source_url:\s*"([^"]+)"', text, re.M)
        if not source:
            raise SystemExit(f"{path.name} has no source_url to cite")
        rows = {
            unlock.replace(",", ""): (display.strip(), int(cost))
            for display, cost, unlock in WIKI_ROW.findall(section.group(1))
        }
        pages[character] = (rows, source.group(1))
    return pages


def join(
    grants: dict[str, tuple[str, int]],
    pages: dict[str, tuple[dict[str, tuple[str, int]], str]],
) -> tuple[dict[str, tuple[str, int, str, str]], list[str]]:
    """Pair identifiers with display names, and report every pair that did not form."""
    paired: dict[str, tuple[str, int, str, str]] = {}
    gaps: list[str] = []
    for identifier, (character, tier) in sorted(grants.items()):
        page = pages.get(character)
        if not page:
            gaps.append(f"{identifier}: no wiki page for {character}")
            continue
        rows, url = page
        if tier in TIER_THRESHOLD:
            threshold = TIER_THRESHOLD[tier]
        else:
            remaining = set(rows) - set(TIER_THRESHOLD.values())
            if len(remaining) != 1:
                gaps.append(
                    f"{identifier}: {character} tier {tier} matches "
                    f"{len(remaining)} rows, not one"
                )
                continue
            threshold = remaining.pop()
        if threshold not in rows:
            gaps.append(f"{identifier}: {character} has no row at {threshold}")
            continue
        display, cost = rows[threshold]
        paired[identifier] = (display, cost, character, url)
    return paired, gaps


def check_anchors(paired: dict[str, tuple[str, int, str, str]]) -> None:
    """Refuse to emit anything if the join stops reproducing what was already proven."""
    wrong = [
        f"{identifier}: joined {paired[identifier][0]!r}, established {expected!r}"
        for identifier, expected in ANCHORS.items()
        if identifier in paired and paired[identifier][0] != expected
    ]
    missing = [i for i in ANCHORS if i not in paired]
    if wrong or missing:
        for line in wrong:
            print(f"ANCHOR FAILED {line}", file=sys.stderr)
        for identifier in missing:
            print(f"ANCHOR MISSING {identifier}", file=sys.stderr)
        raise SystemExit("the join no longer reproduces the established pairs")


def emit(
    paired: dict[str, tuple[str, int, str, str]], asset_path: str, build_id: str
) -> None:
    for identifier, (display, cost, character, url) in sorted(paired.items()):
        print("\n[[rune]]")
        print(f'id = "{identifier}"')
        print(f'display = "{display}"')
        print('slot = "tenacity"')
        print(f"runic_power_cost = {cost}")
        print(f"# Granted by {character}'s skill tree.")
        # The identifier is read from the install and the name from the wiki, so the
        # pair is only as strong as the correspondence joining them.
        print("confidence = 0.9")
        print("\n[[rune.evidence]]")
        print('type = "game_asset"')
        print(f'asset_path = "{asset_path}"')
        print(f'build_id = "{build_id}"')
        print("\n[[rune.evidence]]")
        print('type = "community_source"')
        print(f'url = "{url}"')
        print('retrieved = "2026-08-08"')
        print(f'game_version = "{build_id}"')


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    install = pathlib.Path(sys.argv[1])
    wiki = pathlib.Path(sys.argv[2])
    data = install / "Soulstone Survivors_Data"
    assets = data / "resources.assets"
    if not assets.exists():
        raise SystemExit(f"no resources.assets under {data}")

    build_id = read_build_id(install)
    grants = read_grants(assets)
    pages = read_wiki(wiki)
    paired, gaps = join(grants, pages)
    check_anchors(paired)

    print(f"# {len(paired)} runes, extracted from build {build_id}.", file=sys.stderr)
    for gap in gaps:
        print(f"# GAP {gap}", file=sys.stderr)
    emit(paired, "Soulstone Survivors_Data/resources.assets", build_id)


if __name__ == "__main__":
    main()
