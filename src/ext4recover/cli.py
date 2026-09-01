"""Command line interface for read-only EXT4 evidence analysis."""

import argparse
from pathlib import Path

from .audit import record
from .ext4 import inspect_superblock
from .hashing import sha256_file
from .recovery import recover_inode
from .report import limitations, write_report
from .tsk import deleted_candidates, open_fs


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="ext4recover")
    app.add_argument("command", choices=("inspect", "scan", "recover"))
    app.add_argument("image", type=Path)
    app.add_argument("inode", type=int, nargs="?")
    app.add_argument("--offset", type=int, default=0)
    app.add_argument("--output", type=Path, default=Path("ext4-recovery-output"))
    app.add_argument("--limit", type=int, default=100)
    return app


def base(args) -> dict:
    return {"image": str(args.image), "image_sha256": sha256_file(args.image),
            "offset": args.offset, "superblock": inspect_superblock(args.image, args.offset)}


def main() -> None:
    args = parser().parse_args()
    report = base(args)
    record(args.output, args.command, image_sha256=report["image_sha256"], offset=args.offset)
    if args.command == "inspect":
        name = "inspection.json"
    elif args.command == "scan":
        report["candidates"] = [item.json() for item in deleted_candidates(open_fs(args.image, args.offset), args.limit)]
        report["limitations"] = limitations()
        name = "candidates.json"
    else:
        if args.inode is None:
            parser().error("recover requires an inode number")
        target, validation = recover_inode(open_fs(args.image, args.offset), args.inode, args.output)
        report.update({"inode": args.inode, "derived_file": str(target), "validation": validation.json(), "limitations": limitations()})
        name = f"recovery-inode-{args.inode}.json"
    path = write_report(args.output, name, report)
    print(path)
