"""Conservative signature carving from EXT4 blocks marked unallocated.

The carver does not read allocated blocks and labels output as derived data.
It can recover contiguous PDF, JPEG, and PNG content when their header and
terminator remain in the same unallocated run.  It deliberately does not
attribute a filename, owner, or provenance to carved data.
"""

from __future__ import annotations

import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from .ext4 import inspect_superblock
from .hashing import sha256_bytes


@dataclass
class CarvedFile:
    offset: int
    size: int
    signature: str
    sha256: str
    path: str
    confidence: str = "CONTIGUOUS_UNALLOCATED_SIGNATURE"

    def json(self) -> dict:
        return asdict(self)


SIGNATURES = ((b"%PDF-", "PDF", "pdf"), (b"\x89PNG\r\n\x1a\n", "PNG", "png"), (b"\xff\xd8\xff", "JPEG", "jpg"))


def _layout(image: Path, offset: int) -> tuple[int, int, int, int, int]:
    """Return block size, total blocks, blocks/group, descriptor size, GDT block."""
    report = inspect_superblock(image, offset)
    block_size = int(report["block_size"])
    with image.open("rb") as stream:
        stream.seek(offset + 1024)
        superblock = stream.read(1024)
    total_blocks = struct.unpack_from("<I", superblock, 4)[0]
    blocks_per_group = struct.unpack_from("<I", superblock, 32)[0]
    descriptor_size = struct.unpack_from("<H", superblock, 254)[0] or 32
    if blocks_per_group == 0 or descriptor_size < 32:
        raise ValueError("Invalid EXT4 group-descriptor layout.")
    # With 1 KiB blocks, the superblock is block 1 and the table begins at 2.
    return block_size, total_blocks, blocks_per_group, descriptor_size, 2 if block_size == 1024 else 1


def _unallocated_runs(image: Path, offset: int):
    block_size, total, per_group, descriptor_size, gdt_block = _layout(image, offset)
    groups = (total + per_group - 1) // per_group
    pending_start: int | None = None
    pending_count = 0
    with image.open("rb") as stream:
        for group in range(groups):
            stream.seek(offset + gdt_block * block_size + group * descriptor_size)
            descriptor = stream.read(descriptor_size)
            if len(descriptor) < 32:
                raise ValueError("Truncated EXT4 group descriptor table.")
            bitmap_block = struct.unpack_from("<I", descriptor, 0)[0]
            if descriptor_size >= 64:
                bitmap_block |= struct.unpack_from("<I", descriptor, 32)[0] << 32
            stream.seek(offset + bitmap_block * block_size)
            bitmap = stream.read(block_size)
            group_blocks = min(per_group, total - group * per_group)
            for index in range(group_blocks):
                block = group * per_group + index
                is_allocated = bitmap[index // 8] & (1 << (index % 8))
                if not is_allocated:
                    if pending_start is None:
                        pending_start = block
                    pending_count += 1
                elif pending_start is not None:
                    yield pending_start, pending_count, block_size
                    pending_start, pending_count = None, 0
    if pending_start is not None:
        yield pending_start, pending_count, block_size


def _content(data: bytes, kind: str) -> bytes | None:
    if kind == "PDF":
        end = data.find(b"%%EOF")
        return data[:end + 5] if end >= 0 else None
    if kind == "PNG":
        end = data.find(b"IEND\xaeB`\x82")
        return data[:end + 8] if end >= 0 else None
    if kind == "JPEG":
        end = data.find(b"\xff\xd9", 3)
        return data[:end + 2] if end >= 0 else None
    return None


def carve_unallocated(
    image: str | Path, offset: int, output: Path, limit: int = 25, max_size: int = 32 * 1024 * 1024
) -> list[CarvedFile]:
    """Carve supported contiguous files from blocks the EXT4 bitmap marks free."""
    image = Path(image)
    carved_dir = output / "carved"
    carved_dir.mkdir(parents=True, exist_ok=True)
    results: list[CarvedFile] = []
    seen: set[int] = set()
    with image.open("rb") as stream:
        for first_block, count, block_size in _unallocated_runs(image, offset):
            run_offset = offset + first_block * block_size
            run_size = count * block_size
            position = 0
            tail = b""
            while position < run_size and len(results) < limit:
                stream.seek(run_offset + position)
                chunk = stream.read(min(1024 * 1024, run_size - position))
                searchable = tail + chunk
                for magic, name, extension in SIGNATURES:
                    start = searchable.find(magic)
                    if start < 0:
                        continue
                    absolute = run_offset + position - len(tail) + start
                    if absolute in seen:
                        continue
                    available = min(max_size, run_offset + run_size - absolute)
                    stream.seek(absolute)
                    content = _content(stream.read(available), name)
                    if content is None:
                        continue
                    seen.add(absolute)
                    target = carved_dir / f"carved-{len(results) + 1:04d}-offset-{absolute}.{extension}"
                    target.write_bytes(content)
                    results.append(CarvedFile(absolute, len(content), name, sha256_bytes(content), str(target)))
                    if len(results) >= limit:
                        break
                tail = searchable[-8:]
                position += len(chunk)
    return results
