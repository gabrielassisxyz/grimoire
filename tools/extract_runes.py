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
import struct
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

# The only tier whose threshold is matched by elimination. Naming it stops a tier this
# has never seen from silently inheriting that treatment and taking the leftover row.
REMAINDER_TIER = 4

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


# The achievement runes, which no skill tree grants and no naming rule reaches. The
# install names the achievement that unlocks each, and the achievement name encodes its
# own condition, which is the same condition the wiki prints in prose. So the two are
# joined on the condition rather than on the rune: "ReachTotalElitesKilled-3000" against
# "Eliminate a total of 3000 elite enemies" is a match nothing about either rune's name
# or effect had to supply.
TYPE_DESCRIPTOR = b"PowerUpParameterFloat"

PARAMETER_DECIMALS = 4

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

# The maps are named one way inside the game and another on the wiki. Forest is anchored
# rather than assumed: its achievement grants Critical Mastery, whose pair was already
# established, and the wiki puts that rune on the Whispering Grove.
MAPS = {
    "Forest": "Whispering Grove",
    "Snow": "Frozen Wastelands",
    "Dungeon": "Dungeon of Despair",
    "Cavern": "Caves of Dhal Zhog",
}

CONDITION_FROM_ACHIEVEMENT = (
    ("characters", r"UnlockCharacterCount-(\d+)"),
    ("runic_power", r"UnlockRunicPower-(\d+)"),
    ("enemies", r"ReachTotalEnemiesKilled-(\d+)"),
    ("elites", r"ReachTotalElitesKilled-(\d+)"),
    ("bosses", r"ReachTotalBossesKilled-(\d+)"),
    ("level", r"ReachExperienceLevel-(\d+)"),
    ("endless", r"CompleteEndlessCycle-(\d+)"),
)

CONDITION_FROM_WIKI = (
    ("characters", r"Unlock a total of ([\d,]+) characters"),
    ("runic_power", r"Unlock a total of ([\d,]+) Runic Power"),
    ("enemies", r"a total of ([\d,]+) enemies"),
    ("elites", r"a total of ([\d,]+) elite"),
    ("bosses", r"a total of ([\d,]+) Lords of the Void"),
    ("level", r"experience level ([\d,]+)"),
    ("endless", r"Endless Mode cycle ([\d,]+)"),
)

# Joined on the effect instead, because its condition is the one place the two sources
# disagree: the game calls it boss rush cycle 1 and the wiki calls it Overlord Mode
# cycle 3. The effect leaves no room, "damage will be rolled twice and the highest roll
# will be chosen" against an identifier that says it rerolls damage rolls.
EFFECT_JOINED = {"RuneRerollDamageRolls": "ControlledChaos"}

ACHIEVEMENT_ANCHORS = {
    "RuneCriticalMastery": "Critical Mastery",
    "RuneRerollMastery": "Reroll Mastery",
    "RuneStartWeaponSkill": "Weapon Expert",
}


def achievement_condition(name: str) -> tuple | None:
    body = name.removeprefix("Achievement-")
    for kind, pattern in CONDITION_FROM_ACHIEVEMENT:
        match = re.fullmatch(pattern, body)
        if match:
            return (kind, int(match.group(1)))
    match = re.fullmatch(r"ReachAffixTierProgressionPerMap-(\w+)-(\d+)", body)
    if match and match.group(1) in MAPS:
        return ("curse", MAPS[match.group(1)], int(match.group(2)))
    return None


def wiki_condition(text: str) -> tuple | None:
    plain = re.sub(r"\[|\]\(.*?\)", "", text)
    for kind, pattern in CONDITION_FROM_WIKI:
        match = re.search(pattern, plain)
        if match:
            return (kind, int(match.group(1).replace(",", "")))
    match = re.search(r"curse tiers up to ([IVX]+) enabled on The ([\w\' ]+?)\.", plain)
    if match:
        return ("curse", match.group(2).strip(), ROMAN[match.group(1)])
    return None


def join_achievements(
    granted: dict[str, list[str]], catalogue: dict[str, tuple[str, int, str]]
) -> dict[str, str]:
    """Rune identifiers against display names, joined on the unlock condition."""
    by_condition: dict[tuple, set[str]] = {}
    for achievement, runes in granted.items():
        condition = achievement_condition(achievement)
        if condition:
            by_condition.setdefault(condition, set()).update(runes)
    wiki_by_condition: dict[tuple, set[str]] = {}
    for display, (_, _, unlock) in catalogue.items():
        condition = wiki_condition(unlock)
        if condition:
            wiki_by_condition.setdefault(condition, set()).add(display)

    granted_runes = {rune for runes in granted.values() for rune in runes}
    # Seeded, not asserted: a rune this build no longer has must not be emitted with
    # game_asset evidence for a build it is absent from.
    pairs = {i: n for i, n in EFFECT_JOINED.items() if i in granted_runes}
    for condition, runes in by_condition.items():
        names = wiki_by_condition.get(condition, set())
        # Only a one-to-one condition settles a pair. Anything else is reported by its
        # absence rather than resolved by picking, which is what a nearest match is.
        # No condition in the current build is claimed twice, so relaxing this changes
        # nothing today: it is a guard against a patch adding a second rune behind an
        # existing achievement, not a rule this data exercises.
        if len(runes) == 1 and len(names) == 1:
            pairs[next(iter(runes))] = next(iter(names))

    wrong = {
        i: pairs.get(i)
        for i, name in ACHIEVEMENT_ANCHORS.items()
        if pairs.get(i) != name
    }
    if wrong:
        raise SystemExit(f"the achievement join lost its anchors: {wrong}")
    return pairs


def read_build_id(install: pathlib.Path) -> str:
    """The build this describes, so that a later patch is a detectable difference."""
    info = (install / "build_info.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Version\s+(\S+)", info)
    if not match:
        raise SystemExit(f"no version line in {install / 'build_info.txt'}")
    return match.group(1)


def read_parameters(blob: bytes) -> list[float]:
    """The numeric parameters a rune record carries, in the order it stores them.

    Each is a serialized reference whose type descriptor ends in the assembly name, so
    the value sits at the next four-byte boundary after it. Reading them by that marker
    rather than by a fixed offset is what makes the rule survive records that hold two
    parameters, or none.
    """
    values = []
    for match in re.finditer(rb"Assembly-CSharp\x00", blob):
        # The assembly name ends several kinds of serialized reference, and only one of
        # them is followed by a float. Requiring the type descriptor is what separates a
        # parameter from four bytes of the next field read as one: without it the reader
        # returned denormals for a third of the catalog, and two spurious zeros inside a
        # record whose real parameters are 0.5 and 25.
        if TYPE_DESCRIPTOR not in blob[max(0, match.start() - 48) : match.start()]:
            continue
        end = match.end()
        end += (-end) % 4
        if end + 4 <= len(blob):
            exact = struct.unpack_from("<f", blob, end)[0]
            shown = round(exact, PARAMETER_DECIMALS)
            # Rounding is for a readable record, never for a value. Every parameter in
            # the current build survives it exactly; one that would not is a number the
            # game stores more precisely than this can write, and approximating it
            # silently is the failure the effect engine rules forbid.
            if struct.unpack("<f", struct.pack("<f", shown))[0] != exact:
                raise SystemExit(
                    f"parameter {exact!r} does not survive rounding to "
                    f"{PARAMETER_DECIMALS} places"
                )
            values.append(shown)
    return values


def read_grants(
    assets: pathlib.Path,
) -> tuple[
    dict[str, tuple[str, str, int, list[float]]],
    dict[str, bytes],
    dict[str, list[str]],
]:
    """Each rune granted by a node, plus every rune record the install holds."""
    import UnityPy

    env = UnityPy.load(str(assets))
    rune_records: dict[str, bytes] = {}
    grants: dict[str, tuple[str, str, int, list[float]]] = {}
    nodes = []
    achievements: dict[str, list[str]] = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            name = obj.read(check_read=False).m_Name
        except Exception:  # noqa: BLE001
            continue
        if name and name.startswith("Rune"):
            rune_records[name] = obj.get_raw_data()
        elif NODE_NAME.fullmatch(name or ""):
            nodes.append((name, obj.get_raw_data()))
        elif name and name.startswith("Achievement-"):
            granted = sorted(
                {
                    i.decode()
                    for i in re.findall(rb"Rune[A-Za-z0-9]{3,60}", obj.get_raw_data())
                }
            )
            if granted:
                achievements[name] = granted
    for name, raw in nodes:
        node = NODE_NAME.fullmatch(name)
        for token in IDENTIFIER.findall(raw):
            identifier = token.decode()
            if identifier.startswith("Rune"):
                grants[identifier] = (
                    name,
                    node.group(1),
                    int(node.group(2)),
                    read_parameters(rune_records.get(identifier, b"")),
                )
    return grants, rune_records, achievements


# The day the wiki dump under local/ was taken. It travels with the dump rather than
# with a run of this script, so re-extracting against a newer game build does not
# silently re-date evidence that was never re-fetched.
WIKI_RETRIEVED = "2026-08-08"

SKILL_TYPE_FAMILIES = ("RuneAffinity", "RuneInclination", "RuneMastery")

# Pairs established before this rule existed, two of them by equipping the rune and
# reading the save back. They are what makes the transformation below a tested rule
# rather than a resemblance, which this catalog refuses everywhere else.
FAMILY_ANCHORS = {
    "RuneAffinityElectric": "Skill Affinity: Electric",
    "RuneInclinationElectric": "Skill Inclination: Electric",
    "RuneMasteryElectric": "Skill Mastery: Electric",
}


def read_skill_types(identifiers: set[str]) -> set[str]:
    """The skill types, taken as the suffixes all three families share.

    Deriving the set instead of listing it is what keeps a stray identifier out. Only a
    real type appears once per family, so anything present in fewer than three is not
    one, and the three bare family names fall out the same way.
    """
    per_family = [
        {i[len(f) :] for i in identifiers if i.startswith(f) and i != f}
        for f in SKILL_TYPE_FAMILIES
    ]
    return set.intersection(*per_family)


def family_pairs(identifiers: set[str]) -> dict[str, str]:
    """Every Rune<Family><Type> against the name the interface gives it."""
    types = read_skill_types(identifiers)
    pairs = {}
    for family in SKILL_TYPE_FAMILIES:
        label = family.removeprefix("Rune")
        for skill_type in sorted(types):
            pairs[family + skill_type] = f"Skill {label}: {skill_type}"
    wrong = {i: pairs[i] for i, name in FAMILY_ANCHORS.items() if pairs.get(i) != name}
    if wrong or set(FAMILY_ANCHORS) - set(pairs):
        raise SystemExit(f"the family rule no longer reproduces its anchors: {wrong}")
    return pairs


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
    grants: dict[str, tuple[str, str, int, list[float]]],
    pages: dict[str, tuple[dict[str, tuple[str, int]], str]],
) -> tuple[dict[str, tuple[str, int, str, str, list[float]]], list[str]]:
    """Pair identifiers with display names, and report every pair that did not form."""
    paired: dict[str, tuple[str, int, str, str, list[float]]] = {}
    gaps: list[str] = []
    for identifier, (node, character, tier, values) in sorted(grants.items()):
        page = pages.get(character)
        if not page:
            gaps.append(f"{identifier}: no wiki page for {character}")
            continue
        rows, url = page
        if tier in TIER_THRESHOLD:
            threshold = TIER_THRESHOLD[tier]
        elif tier != REMAINDER_TIER:
            gaps.append(f"{identifier}: {character} tier {tier} has no known threshold")
            continue
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
        paired[identifier] = (display, cost, node, url, values)
    return paired, gaps


def check_anchors(paired: dict[str, tuple[str, int, str, str, list[float]]]) -> None:
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


def read_rune_table(wiki: pathlib.Path) -> dict[str, tuple[str, int, str]]:
    """Every rune the wiki tabulates: its section, its cost and how it unlocks."""
    page = wiki / "runes--443.md"
    text = page.read_text(encoding="utf-8")
    source = re.search(r'^source_url:\s*"([^"]+)"', text, re.M)
    if not source:
        raise SystemExit(f"{page.name} has no source_url to cite")
    table: dict[str, tuple[str, int, str]] = {}
    slot = "versatility"
    for line in text.splitlines():
        if line.startswith("# Tenacity"):
            slot = "tenacity"
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[1] or cells[1] in ("Name", "---"):
            continue
        # Only the tenacity table has a cost column; versatility runes are all zero,
        # which the page states in its own prose and a tooltip already confirmed.
        if slot != "tenacity":
            # The versatility table has no cost column and the page states in prose
            # that every rune in it is free, which a tooltip also confirmed.
            cost = 0
        elif cells[3].lstrip("-").isdigit():
            cost = int(cells[3])
        else:
            raise SystemExit(
                f"{page.name}: {cells[1]!r} has cost cell {cells[3]!r}, not a number"
            )
        table[cells[1]] = (slot, cost, cells[-2])
    return table, source.group(1)


def emit_achievements(
    pairs: dict[str, str],
    table: dict[str, tuple[str, int, str]],
    rune_records: dict[str, bytes],
    url: str,
    asset_path: str,
    build_id: str,
) -> None:
    for identifier, display in sorted(pairs.items()):
        if display not in table:
            continue
        slot, cost, _ = table[display]
        print("\n[[rune]]")
        print(f'id = "{identifier}"')
        print(f'display = "{display}"')
        print(f'slot = "{slot}"')
        print(f"runic_power_cost = {cost}")
        values = read_parameters(rune_records.get(identifier, b""))
        if values:
            print(f"parameters = {values}")
        print("confidence = 0.9")
        print("\n[[rune.evidence]]")
        print('type = "game_asset"')
        print(f'asset_path = "{asset_path}"')
        print(f'build_id = "{build_id}"')
        print("\n[[rune.evidence]]")
        print('type = "community_source"')
        print(f'url = "{url}"')
        print(f'retrieved = "{WIKI_RETRIEVED}"')
        print('game_version = "unstated"')


def emit_family(
    pairs: dict[str, str],
    rune_records: dict[str, bytes],
    asset_path: str,
    build_id: str,
) -> None:
    """The skill type families, which no wiki table lists and no tree node grants."""
    for identifier, display in sorted(pairs.items()):
        print("\n[[rune]]")
        print(f'id = "{identifier}"')
        print(f'display = "{display}"')
        print('slot = "versatility"')
        values = read_parameters(rune_records.get(identifier, b""))
        if values:
            print(f"parameters = {values}")
        # The identifier is read from the install and the name follows a rule the
        # install's own regularity supports, so this is weaker than a record whose name
        # was read somewhere. A tooltip for any of them would still upgrade it.
        print("confidence = 0.9")
        print("\n[[rune.evidence]]")
        print('type = "game_asset"')
        print(f'asset_path = "{asset_path}"')
        print(f'build_id = "{build_id}"')


def emit(
    paired: dict[str, tuple[str, int, str, str, list[float]]],
    asset_path: str,
    build_id: str,
) -> None:
    for identifier, (display, cost, node, url, values) in sorted(paired.items()):
        print("\n[[rune]]")
        print(f'id = "{identifier}"')
        print(f'display = "{display}"')
        print('slot = "tenacity"')
        print(f"runic_power_cost = {cost}")
        # The node is what makes ownership readable: the save records a node the
        # player has bought, so a rune whose node is present is a rune they hold.
        print(f'unlocked_by = "{node}"')
        if values:
            print(f"parameters = {values}")
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
        print(f'retrieved = "{WIKI_RETRIEVED}"')
        # Not the install's build id. The wiki does not state the version it describes,
        # and copying the installed one here would make a stale page cite itself as
        # current on every future extraction.
        print('game_version = "unstated"')


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
    grants, rune_records, achievements = read_grants(assets)
    pages = read_wiki(wiki)
    paired, gaps = join(grants, pages)
    check_anchors(paired)

    print(f"# {len(paired)} runes, extracted from build {build_id}.", file=sys.stderr)
    for gap in gaps:
        print(f"# GAP {gap}", file=sys.stderr)
    asset_path = "Soulstone Survivors_Data/resources.assets"
    emit(paired, asset_path, build_id)

    table, runes_url = read_rune_table(wiki)
    achievement_pairs = join_achievements(achievements, table)
    print(f"# {len(achievement_pairs)} achievement runes.", file=sys.stderr)
    emit_achievements(
        achievement_pairs, table, rune_records, runes_url, asset_path, build_id
    )

    pairs = family_pairs(set(rune_records))
    print(f"# {len(pairs)} skill type family runes.", file=sys.stderr)
    emit_family(pairs, rune_records, asset_path, build_id)


if __name__ == "__main__":
    main()
