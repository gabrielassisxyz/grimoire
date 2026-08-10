"""Read skill records out of an installed game and pair them with display names.

Run offline, never from the advisor: it needs UnityPy and a licensed install, and it
writes catalog records that are reviewed before they are committed. Nothing it reads is
ever tracked; only the normalized records it prints are.

    uv run --group extract python tools/extract_skills.py \
        <install-dir> <wiki-dir> <wiki-retrieved-date>

The install stores a skill as a power-up: the object named Power-Up-Skill-LightningBeam
is what the level-up screen offers, and its identifier suffix is the id the save writes
into a match record. So the id needs no parsing, which is the one thing about this join
that is free.

The display name is not free and is not derived. Splitting LightningBeam into "Lightning
Beam" works for 229 of the 258 skills the wiki also names and is wrong for 29 of them,
in three ways the identifier cannot express: a lowercase joiner (Aura of Chaos), a
possessive (Camor's Arrow), and a compound the install writes closed against a wiki that
writes it open (Firebolt against Fire Bolt). A rule that is right 89% of the time is
worse than no rule, because the 11% are plausible. So the display name is the wiki page
title, taken verbatim, and a skill the wiki does not name gets no record at all. That
gap is 209 skills and it closes by capturing more wiki pages, not by guessing.

What joins the two is a normalized key rather than a rule about names: case, spaces,
apostrophes and hyphens dropped. It is injective on both sides of the current data,
which the script re-checks on every run, and it is anchored on six pairs established
before it existed.
"""

from __future__ import annotations

import pathlib
import re
import struct
import sys

NAME_PREFIX = "Power-Up-Skill-"

# The artifact power variants, which are a different thing wearing the same prefix:
# Power-Up-Skill-AP-ArrowBarrage-Ice is one type-variant of an artifact power, and the
# save writes no such identifier. They are counted and reported, never emitted.
ARTIFACT_POWER_PREFIX = "AP-"

# Same reference header the rune extraction reads, and the same reason for matching the
# whole serialized structure rather than a keyword: an unrelated marker cannot drift
# into range, and a layout change fails loudly by finding nothing.
PARAMETER_HEADER = re.compile(
    rb"PowerUpParameterFloat\x00{7}\x0f\x00\x00\x00Assembly-CSharp\x00"
)

# Every typed parameter a record carries, in order. Only the float ones hold a number
# this reads; the rest are tooltip references. They are logged rather than emitted so
# that a partial reading is visible as partial instead of looking like the whole record.
PARAMETER_KIND = re.compile(rb"PowerUpParameter([A-Za-z]+)\x00")

PARAMETER_DECIMALS = 4

# A weapon identifier inside a skill record. That the record names the weapon which
# grants the skill is the install's claim; the wiki confirms it independently for the
# two anchored pairs, saying "The Elementalist, 1st weapon" where the install says
# WeaponElementalist-01, and "The Barbarian, 3rd Weapon" against WeaponBarbarian-03.
WEAPON_ID = re.compile(rb"Weapon[A-Za-z]+-\d\d")

# Pairs settled before this script existed, from the pilot build and its guide. They are
# the test: a join that stops reproducing them is wrong, whatever else it produces.
DISPLAY_ANCHORS = {
    "ThunderingSlash": "Thundering Slash",
    "ThunderClap": "Thunder Clap",
    "LightningBeam": "Lightning Beam",
    "PowerConductor": "Power Conductor",
    "OverchargedBlast": "Overcharged Blast",
    "OnGuard": "On Guard",
}

# The two the wiki states in prose, so they are a second reading rather than a
# consequence of the first.
WEAPON_ANCHORS = {
    "ThunderingSlash": "WeaponBarbarian-03",
    "LightningBeam": "WeaponElementalist-01",
}

TITLE = re.compile(r'^title: "(.+)"$', re.M)
SOURCE_URL = re.compile(r'^source_url: "(.+)"$', re.M)


def join_key(text: str) -> str:
    """What two spellings of one name have in common once styling is dropped."""
    return re.sub(r"[ '\-]", "", text).lower()


def read_build_id(install: pathlib.Path) -> str:
    """The build this describes, so that a later patch is a detectable difference."""
    info = (install / "build_info.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Version\s+(\S+)", info)
    if not match:
        raise SystemExit(f"no version line in {install / 'build_info.txt'}")
    return match.group(1)


def read_wiki(wiki: pathlib.Path) -> dict[str, tuple[str, str]]:
    """Every wiki page, keyed by its normalized title, holding the title and its URL."""
    pages: dict[str, tuple[str, str]] = {}
    collisions = []
    for path in sorted(wiki.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = TITLE.search(text)
        url = SOURCE_URL.search(text)
        if not title or not url:
            continue
        key = join_key(title.group(1))
        if key in pages:
            collisions.append(title.group(1))
            continue
        pages[key] = (title.group(1), url.group(1))
    if collisions:
        # Two pages the key cannot tell apart would make the join pick by file order,
        # which is the failure the rune extraction already paid for once.
        raise SystemExit(f"wiki titles collide under the join key: {collisions}")
    return pages


def read_parameters(blob: bytes) -> list[float]:
    """The float parameters a record carries, in the order it stores them."""
    values = []
    for match in PARAMETER_HEADER.finditer(blob):
        end = match.end()
        end += (-end) % 4
        if end + 4 <= len(blob):
            values.append(struct.unpack_from("<f", blob, end)[0])
    return values


def format_parameter(value: float) -> str:
    """The shortest spelling that is still the same number.

    The rune extraction rounds every parameter to four places and refuses anything that
    does not survive it, which held there because every rune parameter was a round
    number. It does not hold here: one skill stores 19.999998092651367, the nearest
    float32 to a value the interface prints as 20, and rounding it would write a number
    the game does not hold while looking tidier for it. So rounding applies only where
    it is exact, and everything else is written out in full. Neither branch
    approximates.
    """
    shown = round(value, PARAMETER_DECIMALS)
    if struct.unpack("<f", struct.pack("<f", shown))[0] == value:
        return repr(shown)
    return repr(value)


def read_skills(
    assets: pathlib.Path,
) -> tuple[dict[str, tuple[str | None, list[float], list[str]]], int]:
    """Every skill power-up the install holds, and how many were artifact variants."""
    import UnityPy

    env = UnityPy.load(str(assets))
    skills: dict[str, tuple[str | None, list[float], list[str]]] = {}
    variants = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            name = obj.read(check_read=False).m_Name
        except Exception:  # noqa: BLE001
            continue
        if not name or not name.startswith(NAME_PREFIX):
            continue
        identifier = name.removeprefix(NAME_PREFIX)
        if identifier.startswith(ARTIFACT_POWER_PREFIX):
            variants += 1
            continue
        raw = obj.get_raw_data()
        weapons = sorted({w.decode() for w in WEAPON_ID.findall(raw)})
        if len(weapons) > 1:
            # One skill claimed by two weapons. Picking either would be a guess about
            # which grants it, and the field exists to be joined against a build.
            raise SystemExit(f"{identifier} names more than one weapon: {weapons}")
        kinds = [k.decode() for k in PARAMETER_KIND.findall(raw)]
        skills[identifier] = (
            weapons[0] if weapons else None,
            read_parameters(raw),
            kinds,
        )
    return skills, variants


def check_anchors(paired: dict[str, tuple[str, str, str | None, list[float]]]) -> None:
    """Refuse to emit anything if a pair established independently stopped holding."""
    for identifier, expected in DISPLAY_ANCHORS.items():
        found = paired.get(identifier)
        if found is None or found[0] != expected:
            raise SystemExit(
                f"anchor failed: {identifier} should be named {expected!r}, "
                f"the join produced {found[0] if found else 'nothing'!r}"
            )
    for identifier, expected in WEAPON_ANCHORS.items():
        found = paired.get(identifier)
        if found is None or found[2] != expected:
            raise SystemExit(
                f"anchor failed: {identifier} should be granted by {expected!r}, "
                f"the join produced {found[2] if found else 'nothing'!r}"
            )


def print_record(
    identifier: str,
    display: str,
    url: str,
    weapon: str | None,
    parameters: list[float],
    build_id: str,
    retrieved: str,
) -> None:
    print("[[skill]]")
    print(f'id = "{identifier}"')
    print(f'display = "{display}"')
    if weapon:
        print(f'granted_by_weapon = "{weapon}"')
    if parameters:
        print(f"parameters = [{', '.join(format_parameter(p) for p in parameters)}]")
    print("confidence = 0.9")
    print("[[skill.evidence]]")
    print('type = "game_asset"')
    print('asset_path = "Soulstone Survivors_Data/resources.assets"')
    print(f'build_id = "{build_id}"')
    print("[[skill.evidence]]")
    print('type = "community_source"')
    print(f'url = "{url}"')
    print(f'retrieved = "{retrieved}"')
    print('game_version = "unstated"')
    print()


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    install = pathlib.Path(sys.argv[1])
    wiki = pathlib.Path(sys.argv[2])
    retrieved = sys.argv[3]

    assets = install / "Soulstone Survivors_Data" / "resources.assets"
    if not assets.exists():
        raise SystemExit(f"no resources.assets under {assets.parent}")
    build_id = read_build_id(install)

    pages = read_wiki(wiki)
    skills, variants = read_skills(assets)

    keys = [join_key(i) for i in skills]
    if len(set(keys)) != len(keys):
        raise SystemExit("two skill identifiers collide under the join key")

    paired: dict[str, tuple[str, str, str | None, list[float]]] = {}
    unnamed = []
    for identifier, (weapon, parameters, _) in sorted(skills.items()):
        page = pages.get(join_key(identifier))
        if page is None:
            unnamed.append(identifier)
            continue
        paired[identifier] = (page[0], page[1], weapon, parameters)

    check_anchors(paired)

    print(f"# {len(paired)} skills, read from {assets.name} at build {build_id}")
    print(f"# and named from the wiki dump retrieved {retrieved}.")
    print("#")
    print("# parameters are the float parameters the record stores, in its own order.")
    print("# What each position means is NOT established here; a record also carries")
    print("# typed tooltip parameters this does not read, so the list is partial by")
    print("# construction and is a reading rather than an interpretation.")
    print()
    for identifier, (display, url, weapon, parameters) in sorted(paired.items()):
        print_record(identifier, display, url, weapon, parameters, build_id, retrieved)

    print(f"# {variants} artifact power variants skipped", file=sys.stderr)
    print(f"# {len(unnamed)} skills the wiki dump does not name:", file=sys.stderr)
    for identifier in unnamed:
        print(f"#   {identifier}", file=sys.stderr)
    for identifier, (_, _, kinds) in sorted(skills.items()):
        if identifier in paired:
            print(f"# {identifier} parameter kinds: {kinds}", file=sys.stderr)


if __name__ == "__main__":
    main()
