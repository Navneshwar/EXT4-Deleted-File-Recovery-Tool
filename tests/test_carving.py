from ext4recover.carving import _content


def test_carves_complete_pdf_content():
    data = b"%PDF-1.4\nbody\n%%EOF\ntrailing-block-data"
    assert _content(data, "PDF") == b"%PDF-1.4\nbody\n%%EOF"


def test_rejects_signature_without_terminator():
    assert _content(b"%PDF-1.4\npartial", "PDF") is None
