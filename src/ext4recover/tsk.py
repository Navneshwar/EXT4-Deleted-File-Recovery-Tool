"""The Sleuth Kit adapter; isolates optional forensic-library details."""

from pathlib import Path

from .models import Candidate


def _ewf_img_info(image: Path):
    """Expose an EWF container to TSK without extracting or modifying it."""
    try:
        import pyewf
        import pytsk3
    except ImportError as error:
        raise RuntimeError(
            "E01/EWF support requires pyewf (libewf Python bindings), or mount the E01 read-only "
            "with ewfmount and pass the exposed ewf1 file using --stream."
        ) from error

    handle = pyewf.file()
    handle.open(pyewf.glob(str(image)))

    class EwfImgInfo(pytsk3.Img_Info):
        def __init__(self):
            self._handle = handle
            super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)

        def close(self):
            self._handle.close()

        def get_size(self):
            return self._handle.get_media_size()

        def read(self, offset, size):
            self._handle.seek(offset)
            return self._handle.read(size)

    return EwfImgInfo()


def open_fs(image: str | Path, offset: int = 0, ewf: bool = False):
    try:
        import pytsk3
    except ImportError as error:
        raise RuntimeError("pytsk3 is required: pip install pytsk3") from error
    info = _ewf_img_info(Path(image)) if ewf else pytsk3.Img_Info(str(image))
    return pytsk3.FS_Info(info, offset=offset)


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


def deleted_directory_entries(fs, limit: int | None = None) -> list[Candidate]:
    """Find deleted directory entries whose names still survive in EXT4 metadata.

    Only allocated directories are traversed: deleted directories do not have a
    reliable path, and recursing through them risks inventing provenance.
    """
    import pytsk3

    results: list[Candidate] = []
    visited: set[int] = set()

    def walk(path: str, depth: int = 0) -> None:
        if depth > 64 or (limit and len(results) >= limit):
            return
        try:
            directory = fs.open_dir(path=path)
        except IOError:
            return
        for entry in directory:
            name_info = entry.info.name
            meta = entry.info.meta
            if not name_info or not name_info.name:
                continue
            name = name_info.name.decode("utf-8", errors="replace")
            if name in (".", ".."):
                continue
            child_path = f"{path.rstrip('/')}/{name}"
            name_deleted = bool(name_info.flags & pytsk3.TSK_FS_NAME_FLAG_UNALLOC)
            meta_deleted = bool(meta and meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)
            if (name_deleted or meta_deleted) and meta and meta.size:
                results.append(Candidate(meta.addr, meta.size, False, str(meta.type), name, child_path))
                if limit and len(results) >= limit:
                    return
            if (
                meta
                and name_info.type == pytsk3.TSK_FS_NAME_TYPE_DIR
                and not name_deleted
                and not meta_deleted
                and meta.addr not in visited
            ):
                visited.add(meta.addr)
                walk(child_path, depth + 1)

    walk("/")
    return results


def read_inode(fs, inode: int) -> tuple[bytes, int]:
    entry = fs.open_meta(inode)
    meta = entry.info.meta
    if not meta:
        raise ValueError(f"Inode {inode} has no metadata.")
    return entry.read_random(0, meta.size), meta.size
