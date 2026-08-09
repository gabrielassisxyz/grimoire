"""Read the save files Soulstone Survivors writes, without guessing.

The player's progression is split across one gzip file per concern, named
``playerProfile-<slot>-<domain>.savgs``, plus rotating backups ``-1`` through ``-9``.
Each decompresses to a little-endian stream in the shape .NET's BinaryWriter emits:
int32 written raw, strings written as a 7-bit-encoded byte length followed by UTF-8.

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
    slot: int
    domain: str
    backup: int | None  # None for the live file, 1..9 for a rotating backup

    @property
    def is_live(self) -> bool:
        return self.backup is None


def parse_name(path: Path) -> SaveFile | None:
    """Split ``playerProfile-0-currencies-3.savgs`` into its parts, or return None."""
    if path.suffix != SAVE_SUFFIX:
        return None
    parts = path.stem.split("-")
    if len(parts) < 3 or parts[0] != "playerProfile" or not parts[1].isdigit():
        return None
    backup = int(parts[-1]) if parts[-1].isdigit() else None
    domain_end = len(parts) - 1 if backup is not None else len(parts)
    domain = "-".join(parts[2:domain_end])
    if not domain:
        return None
    return SaveFile(path=path, slot=int(parts[1]), domain=domain, backup=backup)


def discover(directory: Path) -> list[SaveFile]:
    """Every save file in a directory, live files first, then backups, sorted."""
    found = [
        f
        for f in (parse_name(p) for p in sorted(directory.glob("*" + SAVE_SUFFIX)))
        if f
    ]
    return sorted(
        found, key=lambda f: (f.domain, f.backup if f.backup is not None else -1)
    )


class PayloadReader:
    """Sequential reader over a decompressed payload."""

    def __init__(self, data: bytes, *, skip_tag: bool = True) -> None:
        self._data = data
        self._pos = _TAG_LENGTH if skip_tag else 0

    @property
    def remaining(self) -> int:
        return len(self._data) - self._pos

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
