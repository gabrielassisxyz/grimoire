"""Read the save files Soulstone Survivors writes, without guessing.

The player's progression is split across one gzip file per concern, named
``playerProfile-<profile>-<domain>.savgs``, alongside ``-1`` through ``-9``.
Each decompresses to a little-endian stream in the shape .NET's BinaryWriter emits:
int32 written raw, strings written as a 7-bit-encoded byte length followed by UTF-8.

Those ten names are a rotation, not a file and its backups: see ``newest_per_domain``.

Only the primitives are implemented here. The per-domain record layouts are not, and
inventing them from a partial reading would produce a parser that is confidently wrong
about the one thing this project exists to avoid being wrong about. What each domain
means is settled by decoding a real file and checking it against a screen that shows the
same numbers, one domain at a time.

Reading the player's own save from disk is deliberate and bounded: it is unprotected
local data, and nothing here writes to it. See AGENTS.md, "Data and provenance".
"""

from __future__ import annotations

import gzip
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SAVE_SUFFIX = ".savgs"

# Byte 0 of every payload is a format tag rather than data. Reading it as data shifts
# every following int32 by one byte, which does not fail: it yields plausible-looking
# integers that are all wrong. The first probe of this format did exactly that.
_TAG_LENGTH = 1


class SaveFormatError(Exception):
    """A save payload did not match the format described in this module."""


@dataclass(frozen=True)
class SaveFile:
    """One save file on disk, identified by the parts of its name."""

    path: Path
    profile: int
    domain: str
    rotation: int  # 0 for the unsuffixed name, 1..9 for the numbered ones


def parse_name(path: Path) -> SaveFile | None:
    """Split ``playerProfile-0-currencies-3.savgs`` into its parts, or return None."""
    if path.suffix != SAVE_SUFFIX:
        return None
    parts = path.stem.split("-")
    if len(parts) < 3 or parts[0] != "playerProfile" or not parts[1].isdigit():
        return None
    numbered = parts[-1].isdigit()
    rotation = int(parts[-1]) if numbered else 0
    domain = "-".join(parts[2 : len(parts) - 1 if numbered else len(parts)])
    if not domain:
        return None
    return SaveFile(path=path, profile=int(parts[1]), domain=domain, rotation=rotation)


def discover(directory: Path) -> list[SaveFile]:
    """Every save file in a directory, grouped by domain and ordered by rotation."""
    found = [
        f
        for f in (parse_name(p) for p in sorted(directory.glob("*" + SAVE_SUFFIX)))
        if f
    ]
    return sorted(found, key=lambda f: (f.domain, f.rotation))


def newest_per_domain(
    files: Iterable[SaveFile], *, profile: int
) -> dict[str, SaveFile]:
    """The latest written file for each domain of one profile, by write counter.

    The ten names a domain has are a ring the game writes round, not a current file
    with nine backups, and the unsuffixed name is simply position zero in that ring.
    So it is routinely stale: one real profile had 31 unlocked weapons under the
    unsuffixed name and 37 under ``-7``, with the six intermediate states sitting in
    the other slots in the order they were written. Treating the unsuffixed file as
    current reports a player's progression as it stood at some arbitrary earlier
    moment, and nothing about the result looks wrong.

    Ordering is by the counter each payload carries, not by modification time. See
    ``read_write_counter`` for what makes that counter trustworthy; the point here is
    that it is written by the game inside the file, so it survives being copied,
    restored from a backup, or moved between machines, all of which destroy timestamps
    without destroying the save.

    The profile is required rather than defaulted because one directory can hold
    several, and a resolution that silently merged them would return one player's
    progression under another player's name.
    """
    newest: dict[str, SaveFile] = {}
    for save in files:
        if save.profile != profile:
            continue
        current = newest.get(save.domain)
        if current is None or _write_order(save) > _write_order(current):
            newest[save.domain] = save
    return newest


def _write_order(save: SaveFile) -> tuple[int, int]:
    # Rotation breaks a tie only so the choice is deterministic. Two slots sharing a
    # counter has not been observed, and it would mean the same generation was written
    # twice, so neither of them is newer than the other in any meaningful sense.
    return (read_write_counter(decompress(save.path)), save.rotation)


class PayloadReader:
    """Sequential reader over a decompressed payload."""

    def __init__(self, data: bytes, *, skip_tag: bool = True) -> None:
        self._data = data
        self._pos = _TAG_LENGTH if skip_tag else 0

    @property
    def remaining(self) -> int:
        return len(self._data) - self._pos

    def read_byte(self) -> int:
        if self.remaining < 1:
            raise SaveFormatError(f"byte needed at {self._pos}, none left")
        value = self._data[self._pos]
        self._pos += 1
        return value

    def skip(self, count: int) -> None:
        """Step over bytes whose meaning is not established.

        Named apart from a read so a decoded field and an unread gap never look alike
        in a caller: a gap that is silently given a name is a guess with a test around
        it, which is the failure this project is built to avoid.
        """
        if count < 0:
            # A bare bounds check passes for a negative count and rewinds instead,
            # which reads the same bytes twice and looks like a plausible record.
            raise SaveFormatError(f"cannot skip backwards, asked for {count}")
        if self.remaining < count:
            raise SaveFormatError(
                f"cannot skip {count} bytes, {self.remaining} left at {self._pos}"
            )
        self._pos += count

    def read_int32(self) -> int:
        if self.remaining < 4:
            raise SaveFormatError(
                f"int32 needs 4 bytes, {self.remaining} left at {self._pos}"
            )
        (value,) = struct.unpack_from("<i", self._data, self._pos)
        self._pos += 4
        return value

    def read_length(self) -> int:
        """A 7-bit encoded length: low seven bits are value, high bit continues."""
        value = shift = 0
        while True:
            if self.remaining < 1:
                raise SaveFormatError(f"length prefix truncated at {self._pos}")
            byte = self._data[self._pos]
            self._pos += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7
            if shift > 28:
                raise SaveFormatError(f"length prefix over 5 bytes at {self._pos}")

    def read_string(self) -> str:
        length = self.read_length()
        if self.remaining < length:
            raise SaveFormatError(
                f"string of {length} needs more than {self.remaining} bytes"
            )
        raw = self._data[self._pos : self._pos + length]
        self._pos += length
        return raw.decode("utf-8")


def decompress(path: Path) -> bytes:
    """The gzip envelope, with a failure that names the file rather than the offset."""
    try:
        with gzip.open(path, "rb") as fh:
            return fh.read()
    except (OSError, EOFError) as err:
        raise SaveFormatError(f"{path.name} is not readable as gzip: {err}") from err


def read_write_counter(data: bytes) -> int:
    """How many times the game has written this domain, from the payload's own header.

    It is not part of the record stream: a currencies payload decodes to this integer
    followed by exactly the six counts the game shows in its header bar, so taking it
    for the first currency shifts the whole row by one and still reads as plausible.

    That it counts writes is measured rather than assumed. Read one domain across all
    ten rotation slots and the values are ten consecutive integers, on every domain
    tried: 20 to 29 for unlocked weapons, 504 to 513 for the skill tree. And on all
    twenty-three domains of one profile, the slot holding the highest counter is the
    same slot as the one with the latest modification time, so two orderings that
    share no mechanism agree everywhere they can be compared.

    This is what makes a stale file detectable from its contents rather than from its
    metadata, which is the difference between a save that has been copied and a save
    that has been changed.
    """
    return PayloadReader(data).read_int32()


def read_identifiers(data: bytes) -> list[str]:
    """Every catalog identifier in a payload, in the order it appears.

    A deliberately partial reading. It skips whatever header precedes the first record
    and does not interpret the numbers between identifiers, because the identifiers are
    the part whose meaning is unambiguous: they are plain UTF-8 and they match the ids
    the game's own content catalog uses, so they can be joined against the catalog
    before a single record layout is understood.

    That partiality is also the failure mode worth having. If a patch changes the
    format, an identifier scan returns nothing instead of returning numbers that are
    silently misaligned, and nothing is a result the caller can act on.
    """
    found: list[str] = []
    position = _TAG_LENGTH
    while position < len(data):
        reader = PayloadReader(data[position:], skip_tag=False)
        try:
            text = reader.read_string()
        except (SaveFormatError, UnicodeDecodeError):
            position += 1
            continue
        if _looks_like_identifier(text):
            found.append(text)
            position += len(data[position:]) - reader.remaining
        else:
            position += 1
    return found


def _looks_like_identifier(text: str) -> bool:
    """Catalog ids are short printable ASCII words, which random bytes rarely are."""
    return (
        2 <= len(text) <= 64
        and text.isascii()
        and text.isprintable()
        and text[0].isalpha()
        and all(c.isalnum() or c in "-_." for c in text)
    )
