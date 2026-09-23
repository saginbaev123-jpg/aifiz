from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


def _register_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("KZFont", str(path)))
            return "KZFont"
    return "Helvetica"


def build_student_pdf(user: dict[str, Any], mastery: list[dict[str, Any]], mistakes: list[dict[str, Any]]) -> bytes:
    font = _register_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    for s in styles.byName.values():
        s.fontName = font
    story = [
        Paragraph("AI Physics KZ — оқушы есебі", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Оқушы: {user.get('full_name','')} | Сынып: {user.get('grade','')}", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Тақырыптық меңгеру", styles["Heading2"]),
    ]
    data = [["Тақырып", "Меңгеру", "Әрекет"]]
    for r in mastery:
        data.append([str(r["topic"]), f"{float(r.get('score',0)):.0f}%", str(r.get("attempts",0))])
    tbl = Table(data, colWidths=[260, 80, 70])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), font),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Қайталанатын қателер", styles["Heading2"]))
    if mistakes:
        for m in mistakes[:10]:
            story.append(Paragraph(f"• {m['topic']}: {m['mistake_type']} ({m['frequency']} рет)", styles["BodyText"]))
    else:
        story.append(Paragraph("Қайталанатын қате тіркелмеген.", styles["BodyText"]))
    doc.build(story)
    return buf.getvalue()
