"""Local PDF export of the interview report using PyMuPDF's HTML Story renderer (no external service)."""

from __future__ import annotations

import io
from html import escape

CSS = """
* { font-family: sans-serif; }
body { font-size: 10pt; color: #1f2937; line-height: 1.4; }
h1 { font-size: 18pt; margin: 0 0 4pt 0; color: #111827; }
h2 { font-size: 12.5pt; margin: 14pt 0 6pt 0; color: #111827; border-bottom: 1px solid #d1d5db; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 8pt 0 2pt 0; color: #111827; }
p { margin: 2pt 0 4pt 0; }
.muted { color: #6b7280; font-size: 8.5pt; }
table { width: 100%; border-collapse: collapse; margin: 4pt 0; }
td, th { border: 1px solid #e5e7eb; padding: 3pt 5pt; text-align: left; vertical-align: top; font-size: 9pt; }
th { background-color: #f3f4f6; }
.score { font-weight: bold; }
.box { background-color: #f9fafb; border: 1px solid #e5e7eb; padding: 6pt; margin: 4pt 0; }
"""


def _e(v) -> str:
    return escape("" if v is None else str(v))


def _score(v) -> str:
    return "—" if v is None else f"{float(v):.0f}"


def render_report_html(report: dict) -> str:
    cfg = report.get("config", {})
    s = report.get("scores", {})
    parts: list[str] = []
    parts.append("<h1>InterviewForge Interview Report</h1>")
    parts.append(
        f"<p class='muted'>{_e(report.get('candidate_name') or 'Candidate')} · {_e(cfg.get('experience_level'))} "
        f"{_e(cfg.get('target_role'))} · {_e(cfg.get('interview_type'))} · {_e(cfg.get('difficulty'))} · "
        f"generated {_e(str(report.get('generated_at', ''))[:16].replace('T', ' '))} UTC · AI mode: {_e(report.get('ai_mode'))}</p>"
    )
    parts.append("<h2>1. Executive summary</h2>")
    parts.append(f"<p>{_e(report.get('executive_summary'))}</p>")
    parts.append(
        "<h2>2. Overall scores</h2><table><tr><th>ATS-style score</th><th>JD match</th>"
        "<th>Interview</th><th>Readiness</th></tr>"
    )
    parts.append(
        f"<tr><td class='score'>{_score(s.get('ats'))}</td><td class='score'>{_score(s.get('jd_match'))}</td>"
        f"<td class='score'>{_score(s.get('interview'))}</td><td class='score'>{_score(s.get('readiness'))}</td></tr></table>"
    )
    parts.append("<table><tr><th>Category</th><th>Score</th><th>Weight</th></tr>")
    for c in report.get("category_scores", []):
        parts.append(
            f"<tr><td>{_e(c['label'])}</td><td>{_score(c['score'])}</td><td>{c['weight'] * 100:.0f}%</td></tr>"
        )
    parts.append("</table>")
    parts.append("<h2>3. Skill evaluation</h2>")
    if report.get("skills"):
        parts.append("<table><tr><th>Skill</th><th>Score</th><th>Evidence</th><th>Recommendation</th></tr>")
        for sk in report["skills"]:
            parts.append(
                f"<tr><td>{_e(sk['skill'])}</td><td>{_score(sk['score'])}</td><td>{_e(sk['evidence'])}</td>"
                f"<td>{_e(sk['recommendation'])}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append("<p class='muted'>No skill-specific questions were answered.</p>")
    parts.append("<h2>4. Question-by-question review</h2>")
    for q in report.get("questions", []):
        label = "Follow-up" if q.get("is_follow_up") else f"Q{q.get('number')}"
        parts.append(
            f"<h3>{label} · {_e(q['category'].replace('_', ' '))} · {_score(q['score'])}/100 ({_e(q['classification'])})</h3>"
        )
        parts.append(f"<p><b>Question:</b> {_e(q['question'])}</p>")
        parts.append(f"<p><b>Your answer:</b> {_e(q['answer'] or '(skipped)')}</p>")
        if q.get("strengths"):
            parts.append(f"<p><b>What was good:</b> {_e(' '.join(q['strengths']))}</p>")
        if q.get("missing"):
            parts.append(f"<p><b>What was missing:</b> {_e(', '.join(q['missing']))}</p>")
        parts.append(f"<p><b>How to improve:</b> {_e(q.get('improvement'))}</p>")
        if q.get("ideal_answer"):
            parts.append(f"<div class='box'><b>Ideal answer structure:</b> {_e(q['ideal_answer'])}</div>")

    def bullets(title: str, items: list[str]) -> None:
        parts.append(f"<h2>{title}</h2>")
        if items:
            parts.append("<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>")
        else:
            parts.append("<p class='muted'>None.</p>")

    bullets("5. Strongest areas", [f"{a['area']} — {a['detail']}" for a in report.get("strongest_areas", [])])
    bullets("6. Weakest areas", [f"{a['area']} — {a['detail']}" for a in report.get("weakest_areas", [])])
    bullets(
        "7. Resume claims that need stronger evidence",
        [f"“{c['claim']}” — {c['confidence']} confidence. {c['note']}" for c in report.get("claims", [])],
    )
    parts.append("<h2>8. Communication feedback</h2>")
    parts.append(f"<p>{_e(report.get('communication_feedback'))}</p>")
    bullets("9. Technical gaps", report.get("technical_gaps", []))
    bullets(
        "10. Recommended study topics",
        [f"{t['topic']} ({t['priority']}) — {t['reason']}" for t in report.get("study_topics", [])],
    )
    bullets("Action plan", report.get("action_plan", []))
    parts.append("<h2>11. Interviewer verdict</h2>")
    parts.append(f"<p>{_e(report.get('verdict'))}</p>")
    parts.append("<p class='muted'>" + " ".join(_e(d) for d in report.get("disclaimers", [])) + "</p>")
    return "<body>" + "".join(parts) + "</body>"


def render_report_pdf(report: dict) -> bytes:
    import pymupdf as fitz

    buf = io.BytesIO()
    story = fitz.Story(html=render_report_html(report), user_css=CSS)
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (40, 40, -40, -40)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buf.getvalue()
