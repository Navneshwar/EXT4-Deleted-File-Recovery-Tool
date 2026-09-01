"""Minimal EXT4 superblock parser used to verify image assumptions."""

import struct
from pathlib import Path

EXT4_MAGIC = 0xEF53


class Ext4Error(ValueError):
    """The supplied image does not expose a valid EXT4 superblock."""


def inspect_superblock(image: str | Path, offset: int = 0) -> dict[str, int | str]:
    with Path(image).open("rb") as stream:
        stream.seek(offset + 1024)
        raw = stream.read(1024)
    if len(raw) != 1024:
        raise Ext4Error("Image is too small for an EXT4 superblock.")
    magic = struct.unpack_from("<H", raw, 56)[0]
    if magic != EXT4_MAGIC:
        raise Ext4Error(f"EXT4 magic not found at offset {offset + 1080}.")
    log_block = struct.unpack_from("<I", raw, 24)[0]
    block_size = 1024 << log_block
    return {
        "filesystem": "EXT4", "block_size": block_size,
        "inode_size": struct.unpack_from("<H", raw, 88)[0],
        "inodes": struct.unpack_from("<I", raw, 0)[0],
        "blocks": struct.unpack_from("<I", raw, 4)[0],
        "journal_inode": struct.unpack_from("<I", raw, 224)[0],
    }
