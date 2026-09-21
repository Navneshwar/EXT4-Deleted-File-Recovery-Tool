# EXT4 Deleted File Recovery Tool

`ext4recover` analyzes EXT4 forensic evidence without modifying it. It
records image integrity, inspects filesystem metadata, identifies unallocated
inode candidates, reconstructs readable data, validates signatures, and writes
an explainable JSON report plus an audit log.

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## Use

```powershell
ext4recover inspect evidence.img --output case
ext4recover scan evidence.img --output case
ext4recover recover evidence.img 15482 --output case
ext4recover recover-all evidence.img --output case
ext4recover carve evidence.img --output case
```

Raw images (`.img`, `.dd`, `.raw`, `.bin`) work directly. E01/EWF (`.E01`,
`.E02`, etc.) works directly when the optional `pyewf` bindings are installed.
For logical, AFF/AFF4, virtual-disk, and compressed-raw containers (`.L01`,
`.aff4`, `.qcow2`, `.vmdk`, `.vhdx`, `.gz`, `.xz`, `.zst`), expose a read-only
raw byte stream using the appropriate forensic reader and pass it explicitly:

```bash
# Kali: ewfmount evidence.E01 /mnt/ewf
ext4recover scan evidence.E01 --stream /mnt/ewf/ewf1 --output case
```

Use a physical image (raw, E01, AFF4) for deleted-file recovery. L01 is a
logical container and normally does not retain unallocated space or journal data.

## Kali acquisition and demo

Copy `acquire_e01.sh` and `demo_ext4_e01_recovery.sh` to the Kali VM (they
must stay in the same directory), then run:

```bash
chmod +x *.sh
sudo apt update && sudo apt install -y ewf-tools sleuthkit e2fsprogs
sudo ./demo_ext4_e01_recovery.sh
```

The demo creates a disposable 1 GiB loop-backed EXT4 image, writes and deletes
representative files, calls `acquire_e01.sh` to capture a compressed E01, and
examines the E01 read-only with `ewfmount`, `fls`, and `tsk_recover`. Its output
includes evidence hashes, E01 verification, a deleted-file listing, and
recovered content. `create_forensic_image.sh` is now a compatible wrapper for
`acquire_e01.sh`; it no longer makes an uncompressed raw `dd` image.

All commands open the image read-only. `scan` needs `pytsk3` and looks for
unallocated inode metadata; it does not claim that every candidate is a deleted
file. `recover` writes derived data under `case/recovered/`, never beside the
evidence image.

## Outputs

- `case/audit.jsonl`: timestamps, commands, and image hashes.
- `case/*.json`: machine-readable reports with evidence and limitations.
- `case/recovered/`: recovered bytes and a corresponding report.

Recovery status is `FULL` when recovered length equals inode size, otherwise
`PARTIAL`. A valid signature is supporting evidence, not proof of provenance.
`carve` reads only blocks marked unallocated by the EXT4 block bitmap and can
recover contiguous PDF, JPEG, and PNG files whose header and terminator remain.
Carved content is derived evidence: it has no trustworthy original filename or
path and may be partial, overwritten, or a false positive.

`scan` combines two evidence sources: surviving deleted directory entries
(which may retain a filename/path) and unallocated inode metadata. `recover-all`
writes a derived copy for every candidate found by that scan and records failures
separately, rather than treating failed recovery as proof that no file existed.
