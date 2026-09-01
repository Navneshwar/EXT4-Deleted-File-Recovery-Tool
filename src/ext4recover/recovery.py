"""Recover one inode and express validation evidence without overclaiming."""

from pathlib import Path

from .hashing import sha256_bytes
from .models import Validation
from .signatures import identify
from .tsk import read_inode


def recover_inode(fs, inode: int, output: Path) -> tuple[Path, Validation]:
    data, expected = read_inode(fs, inode)
    recovered = output / "recovered"
    recovered.mkdir(parents=True, exist_ok=True)
    target = recovered / f"inode-{inode}.bin"
    target.write_bytes(data)
    signature, valid = identify(data[:32])
    status = "FULL" if len(data) == expected else "PARTIAL"
    return target, Validation(expected, len(data), sha256_bytes(data), signature, valid, status)
