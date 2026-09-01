"""The Sleuth Kit adapter; isolates optional forensic-library details."""

from pathlib import Path

from .models import Candidate


def open_fs(image: str | Path, offset: int = 0):
    try:
        import pytsk3
    except ImportError as error:
        raise RuntimeError("pytsk3 is required: pip install pytsk3") from error
    return pytsk3.FS_Info(pytsk3.Img_Info(str(image)), offset=offset)


def deleted_candidates(fs, limit: int | None = None) -> list[Candidate]:
    import pytsk3

    results: list[Candidate] = []
    for inode in range(fs.info.first_inum, fs.info.last_inum + 1):
        try:
            entry = fs.open_meta(inode)
            meta = entry.info.meta
        except IOError:
            continue
        if not meta or not meta.size or meta.flags & pytsk3.TSK_FS_META_FLAG_ALLOC:
            continue
        results.append(Candidate(inode, meta.size, False, str(meta.type)))
        if limit and len(results) >= limit:
            break
    return results


def read_inode(fs, inode: int) -> tuple[bytes, int]:
    entry = fs.open_meta(inode)
    meta = entry.info.meta
    if not meta:
        raise ValueError(f"Inode {inode} has no metadata.")
    return entry.read_random(0, meta.size), meta.size
