# EXT4 Deleted File Recovery Tool

`ext4recover` analyzes raw EXT4 forensic images without modifying them. It
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
```

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
