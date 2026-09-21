"""Command line interface for read-only EXT4 evidence analysis."""

import argparse
from pathlib import Path

from .audit import record
from .carving import carve_unallocated
from .evidence import EvidenceError, open_evidence
from .ext4 import inspect_superblock
from .hashing import sha256_file
from .recovery import recover_inode
from .report import limitations, write_report
from .tsk import deleted_candidates, deleted_directory_entries, open_fs


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="ext4recover")
    app.add_argument("command", choices=("inspect", "scan", "recover", "recover-all", "carve"))
    app.add_argument("image", type=Path)
    app.add_argument("inode", type=int, nargs="?")
    app.add_argument("--offset", type=int, default=0)
    app.add_argument("--stream", type=Path, help="Read-only raw byte stream exposed from a supported container")
    app.add_argument("--output", type=Path, default=Path("ext4-recovery-output"))
    app.add_argument("--limit", type=int, default=100)
    app.add_argument("--max-carve-size", type=int, default=32 * 1024 * 1024,
                     help="Maximum bytes per carved file (default: 32 MiB)")
    return app


def base(args, evidence) -> dict:
    stream = evidence.analysis_path if not evidence.direct_ewf else args.image
    return {
        "image": str(args.image), "image_sha256": sha256_file(args.image),
        "format": evidence.format, "analysis_stream": str(stream), "offset": args.offset,
        "superblock": inspect_superblock(stream, args.offset) if not evidence.direct_ewf else None,
    }


def main() -> None:
    args = parser().parse_args()
    try:
        evidence = open_evidence(args.image, args.stream)
        report = base(args, evidence)
    except EvidenceError as error:
        parser().error(str(error))
    stream = evidence.analysis_path if not evidence.direct_ewf else args.image
    fs = open_fs(stream, args.offset, ewf=evidence.direct_ewf)
    if report["superblock"] is None:
        info = fs.info
        report["superblock"] = {
            "filesystem": "EXT4", "block_size": getattr(info, "block_size", None),
            "inodes": getattr(info, "last_inum", None), "blocks": getattr(info, "block_count", None),
            "journal_inode": None,
        }
    record(args.output, args.command, image_sha256=report["image_sha256"], offset=args.offset)
    if args.command == "inspect":
        name = "inspection.json"
    elif args.command == "scan":
        inode_candidates = deleted_candidates(fs, args.limit)
        named_candidates = deleted_directory_entries(fs, args.limit)
        known = {item.inode for item in named_candidates}
        merged = named_candidates + [item for item in inode_candidates if item.inode not in known]
        report["candidates"] = [item.json() for item in merged[:args.limit]]
        report["candidate_sources"] = {
            "deleted_directory_entries": len(named_candidates),
            "unallocated_inode_metadata": len(inode_candidates),
        }
        report["limitations"] = limitations()
        name = "candidates.json"
    elif args.command == "carve":
        if evidence.direct_ewf:
            parser().error("Carving E01 directly requires pyewf stream support; use ewfmount and pass --stream /path/to/ewf1.")
        report["carved_files"] = [item.json() for item in carve_unallocated(
            evidence.analysis_path, args.offset, args.output, args.limit, args.max_carve_size
        )]
        report["limitations"] = limitations() + [
            "Carving uses only EXT4 bitmap-unallocated blocks.",
            "Carved files require a supported header and terminator in one contiguous unallocated run.",
            "Carved file names, paths, timestamps, and ownership cannot be inferred from content alone.",
        ]
        name = "carving.json"
    elif args.command == "recover":
        if args.inode is None:
            parser().error("recover requires an inode number")
        target, validation = recover_inode(fs, args.inode, args.output)
        report.update({"inode": args.inode, "derived_file": str(target), "validation": validation.json(), "limitations": limitations()})
        name = f"recovery-inode-{args.inode}.json"
    else:
        named_candidates = deleted_directory_entries(fs, args.limit)
        inode_candidates = deleted_candidates(fs, args.limit)
        candidates = named_candidates + [item for item in inode_candidates if item.inode not in {named.inode for named in named_candidates}]
        recovered, failures = [], []
        for candidate in candidates[:args.limit]:
            try:
                target, validation = recover_inode(fs, candidate.inode, args.output)
                recovered.append({"candidate": candidate.json(), "derived_file": str(target), "validation": validation.json()})
            except (IOError, ValueError) as error:
                failures.append({"inode": candidate.inode, "error": str(error)})
        report.update({"recovered_files": recovered, "failures": failures, "limitations": limitations()})
        name = "bulk-recovery.json"
    path = write_report(args.output, name, report)
    print(path)
