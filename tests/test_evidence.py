import pytest

from ext4recover.evidence import EvidenceError, detect_format, open_evidence


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("disk.img", "raw"), ("disk.dd", "raw"), ("case.E01", "E01/EWF"),
        ("case.E12", "E01/EWF"), ("case.L01", "FTK logical image"),
        ("case.aff4", "AFF4 image"), ("vm.vhdx", "VHDX virtual disk"),
        ("disk.raw.zst", "zstd-compressed raw image"),
    ],
)
def test_detects_supported_evidence_formats(name, expected):
    assert detect_format(name) == expected


def test_raw_evidence_opens_directly(tmp_path):
    image = tmp_path / "disk.img"
    image.write_bytes(b"evidence")
    evidence = open_evidence(image)
    assert evidence.analysis_path == image


def test_container_requires_explicit_read_only_stream(tmp_path):
    image = tmp_path / "case.aff4"
    image.write_bytes(b"container")
    with pytest.raises(EvidenceError, match="requires --stream"):
        open_evidence(image)
