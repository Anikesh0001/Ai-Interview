"""Resume text extraction and parsing."""

from __future__ import annotations

import pytest
from helpers import FIXTURES_DIR

from app.services.extract import ResumeParseError, extract_text, file_extension, normalize_text, sanitize_filename
from app.services.profile import build_profile

MAX = 10 * 1024 * 1024


def _extract(name: str, max_bytes: int = MAX):
    return extract_text(name, (FIXTURES_DIR / name).read_bytes(), max_bytes)


@pytest.mark.parametrize("name", ["sample_resume.txt", "sample_resume.pdf", "sample_resume.docx"])
def test_all_formats_parse_to_the_same_profile(name):
    doc = _extract(name)
    assert doc.file_type == name.rsplit(".", 1)[1]
    profile = build_profile(doc.text)
    assert profile.name == "Aarav Sharma"
    assert profile.email == "aarav.sharma.dev@example.com"
    assert [p.name for p in profile.projects] == ["Hospital Management System", "AI Sales Chatbot", "Resume Analyzer"]
    assert len(profile.experience) == 1
    assert profile.experience[0].title == "Software Engineering Intern"
    assert profile.experience[0].company.startswith("BrightCart")
    assert len(profile.education) == 1
    assert "Computer Science" in profile.education[0].degree
    assert {"Python", "Flask", "React", "PostgreSQL"} <= set(profile.skills)


def test_formats_agree_on_skills_and_claims():
    profiles = [
        build_profile(_extract(n).text) for n in ("sample_resume.txt", "sample_resume.pdf", "sample_resume.docx")
    ]
    assert all(set(p.skills) == set(profiles[0].skills) for p in profiles)
    assert all([c.text for c in p.claims] == [c.text for c in profiles[0].claims] for p in profiles)


def test_pdf_reports_page_count():
    doc = _extract("sample_resume.pdf")
    assert doc.page_count == 1


def test_scanned_pdf_is_rejected_with_helpful_message():
    with pytest.raises(ResumeParseError) as exc:
        _extract("scanned_resume.pdf")
    assert "scanned/image-based" in exc.value.user_message
    assert exc.value.status_code == 422


def test_corrupt_pdf_is_rejected():
    with pytest.raises(ResumeParseError) as exc:
        _extract("corrupt_resume.pdf")
    assert "corrupt" in exc.value.user_message.lower()
    assert exc.value.status_code == 422


def test_non_pdf_bytes_with_pdf_extension_rejected():
    with pytest.raises(ResumeParseError) as exc:
        extract_text("resume.pdf", b"hello world, definitely not a pdf", MAX)
    assert "valid PDF" in exc.value.user_message


def test_non_docx_bytes_with_docx_extension_rejected():
    with pytest.raises(ResumeParseError) as exc:
        extract_text("resume.docx", b"plain text pretending to be docx", MAX)
    assert "DOCX" in exc.value.user_message


def test_empty_file_rejected():
    with pytest.raises(ResumeParseError) as exc:
        _extract("empty_resume.txt")
    assert "empty" in exc.value.user_message.lower()


def test_whitespace_only_text_is_reported_as_empty():
    with pytest.raises(ResumeParseError) as exc:
        extract_text("resume.txt", b"   \n\n  hello  \n", MAX)
    assert "empty" in exc.value.user_message.lower()


def test_binary_txt_rejected():
    with pytest.raises(ResumeParseError) as exc:
        extract_text("resume.txt", b"abc\x00\x01\x02" * 50, MAX)
    assert "binary" in exc.value.user_message


@pytest.mark.parametrize("name", ["resume.exe", "resume.png", "resume", "resume.pdf.sh"])
def test_unsupported_extension_is_415(name):
    with pytest.raises(ResumeParseError) as exc:
        extract_text(name, b"some content", MAX)
    assert exc.value.status_code == 415
    assert "Unsupported file type" in exc.value.user_message


def test_legacy_doc_is_415():
    with pytest.raises(ResumeParseError) as exc:
        extract_text("resume.doc", b"\xd0\xcf\x11\xe0 legacy", MAX)
    assert exc.value.status_code == 415


def test_oversize_file_is_413():
    data = (FIXTURES_DIR / "sample_resume.txt").read_bytes()
    with pytest.raises(ResumeParseError) as exc:
        extract_text("sample_resume.txt", data, max_bytes=len(data) - 1)
    assert exc.value.status_code == 413
    assert "too large" in exc.value.user_message


def test_utf16_and_cp1252_text_decoding(sample_text):
    for encoded in (sample_text.encode("utf-16"), sample_text.replace("•", "-").encode("cp1252")):
        doc = extract_text("resume.txt", encoded, MAX)
        assert "Aarav Sharma" in doc.text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\evil.pdf", "evil.pdf"),
        ("/abs/path/to/My Resume.pdf", "My Resume.pdf"),
        ("résumé.pdf", "resume.pdf"),
        ('cv<b>:*?|"name".pdf', "cv_b_name_.pdf"),
        ("cv<script>alert(1)</script>.pdf", "script_.pdf"),
        ("..", "resume"),
        ("", "resume"),
        ("a..b...pdf", "a.b.pdf"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_output_is_safe():
    for raw in ("../../etc/passwd", "x/../../../y.txt", "C:\\a\\..\\b.docx", "\x00evil\n.pdf", "  ..pdf  "):
        out = sanitize_filename(raw)
        assert "/" not in out and "\\" not in out and ".." not in out
        assert out and len(out) <= 120
        assert all(c.isalnum() or c in "._ -" for c in out)


def test_sanitize_filename_truncates():
    assert len(sanitize_filename("a" * 500 + ".pdf")) == 120


def test_file_extension():
    assert file_extension("Resume.PDF") == "pdf"
    assert file_extension("../../x.docx") == "docx"
    assert file_extension("noext") == ""


def test_normalize_text_handles_ligatures_bullets_and_whitespace():
    raw = "ﬁnance\r\n●  Built   things\t\there\n\n\n\nEnd"
    assert normalize_text(raw) == "finance\n• Built things here\n\nEnd"
