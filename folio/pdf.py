"""Professional PDF invoices for guest folios and company AR."""

from io import BytesIO
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND = colors.HexColor("#c04a00")
INK = colors.HexColor("#1a1410")
MUTED = colors.HexColor("#7a7168")
LINE = colors.HexColor("#ddd4c8")
SOFT = colors.HexColor("#fff5eb")


def _money(amount, currency: str = "UZS") -> str:
    value = Decimal(amount or 0)
    return f"{value:,.2f} {currency}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "InvBrand",
            parent=base["Normal"],
            fontSize=20,
            leading=24,
            textColor=BRAND,
            fontName="Helvetica-Bold",
            spaceAfter=2,
        ),
        "h2": ParagraphStyle(
            "InvH2",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            textColor=INK,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "InvBody",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=INK,
        ),
        "muted": ParagraphStyle(
            "InvMuted",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
        ),
        "right": ParagraphStyle(
            "InvRight",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
        "title": ParagraphStyle(
            "InvTitle",
            parent=base["Normal"],
            fontSize=14,
            leading=18,
            textColor=INK,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "cell": ParagraphStyle(
            "InvCell",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "cell_r": ParagraphStyle(
            "InvCellR",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
    }


def _doc(buf: BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Invoice",
    )


def _header_table(left_lines, right_lines, styles):
    left = [Paragraph(line, styles["body"] if i == 0 else styles["muted"]) for i, line in enumerate(left_lines)]
    right = [Paragraph(line, styles["right"]) for line in right_lines]
    # Pad to equal length
    while len(left) < len(right):
        left.append(Paragraph("&nbsp;", styles["muted"]))
    while len(right) < len(left):
        right.append(Paragraph("&nbsp;", styles["right"]))
    data = [[left[i], right[i]] for i in range(len(left))]
    t = Table(data, colWidths=[105 * mm, 70 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _lines_table(header, rows, styles, currency: str):
    """rows: (desc, qty, amount) yoki (desc, qty, amount, line_currency)."""
    data = [
        [
            Paragraph(header[0], styles["cell"]),
            Paragraph(header[1], styles["cell_r"]),
            Paragraph(header[2], styles["cell_r"]),
        ]
    ]
    for row in rows:
        if len(row) >= 4:
            desc, qty, amount, line_cur = row[0], row[1], row[2], row[3]
        else:
            desc, qty, amount = row[0], row[1], row[2]
            line_cur = currency
        data.append(
            [
                Paragraph(str(desc), styles["cell"]),
                Paragraph(str(qty), styles["cell_r"]),
                Paragraph(_money(amount, line_cur or currency), styles["cell_r"]),
            ]
        )
    table = Table(data, colWidths=[105 * mm, 25 * mm, 45 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
    ]
    table.setStyle(TableStyle(style_cmds))
    # Force header text white via Paragraph recreation — brand bg is enough
    return table


def _totals_table(pairs, styles, currency: str, emphasize_last=True):
    data = []
    for label, amount in pairs:
        data.append(
            [
                Paragraph(str(label), styles["body"]),
                Paragraph(_money(amount, currency), styles["right"]),
            ]
        )
    t = Table(data, colWidths=[130 * mm, 45 * mm])
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND),
    ]
    if emphasize_last and data:
        cmds.append(("BACKGROUND", (0, -1), (-1, -1), SOFT))
        cmds.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
    t.setStyle(TableStyle(cmds))
    return t


def build_folio_pdf(folio) -> bytes:
    reservation = folio.reservation
    hotel = reservation.hotel
    guest = reservation.guest
    tenant = getattr(folio, "tenant", None)
    currency = getattr(tenant, "currency", None) or "UZS"
    styles = _styles()
    buf = BytesIO()
    doc = _doc(buf)
    doc.title = f"Invoice {reservation.code}"

    brand = tenant.name if tenant else hotel.name
    issued = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")

    left = [f"<b>{brand}</b>", hotel.name]
    if hotel.address:
        addr = hotel.address
        if hotel.city:
            addr = f"{addr}, {hotel.city}"
        left.append(addr)
    if hotel.phone:
        left.append(hotel.phone)
    if hotel.email:
        left.append(hotel.email)

    right = [
        f"<b>{_('Hisob-faktura')}</b>",
        f"№ {reservation.code}",
        f"{_('Sana')}: {issued}",
        f"{_('Holat')}: {_('Ochiq') if folio.is_open else _('Yopilgan')}",
    ]

    story = [
        Paragraph(brand, styles["brand"]),
        _header_table(left[1:], right, styles),
        HRFlowable(width="100%", thickness=1.2, color=BRAND, spaceBefore=8, spaceAfter=8),
        Paragraph(_("Mehmon hisobi"), styles["title"]),
    ]

    guest_bits = [f"<b>{guest.full_name}</b>"]
    if guest.phone:
        guest_bits.append(guest.phone)
    if guest.email:
        guest_bits.append(guest.email)
    stay = f"{reservation.check_in.strftime('%d.%m.%Y')} → {reservation.check_out.strftime('%d.%m.%Y')}"
    if reservation.room_id:
        stay += f" · {_('Xona')} {reservation.room.number}"
    story.append(Paragraph("<br/>".join(guest_bits), styles["body"]))
    story.append(Paragraph(stay, styles["muted"]))
    story.append(Spacer(1, 10))

    line_rows = []
    for c in folio.charges.all():
        if getattr(c, "is_void", False):
            continue
        line_rows.append(
            (
                c.description,
                f"{c.quantity:g}",
                c.amount,
                getattr(c, "currency", None) or currency,
            )
        )
    story.append(
        _lines_table(
            [_("Tavsif"), _("Miqdor"), _("Summa")],
            line_rows,
            styles,
            currency,
        )
    )
    story.append(Spacer(1, 8))

    totals = [(_("Subtotal"), folio.charges_total)]
    if folio.tax_percent and folio.tax_percent > 0:
        totals.append((f"{_('QQS')} ({folio.tax_percent:g}%)", folio.tax_amount))
    totals.append((_("Jami"), folio.grand_total))
    story.append(_totals_table(totals, styles, currency))

    payments = [p for p in folio.payments.all() if not getattr(p, "is_void", False)]
    if payments:
        story.append(Paragraph(_("To‘lovlar"), styles["h2"]))
        pay_rows = []
        for p in payments:
            label = p.get_method_display()
            if p.note:
                label = f"{label} · {p.note}"
            pay_rows.append(
                (
                    label,
                    "",
                    p.amount,
                    getattr(p, "currency", None) or currency,
                )
            )
        story.append(
            _lines_table(
                [_("Usul"), "", _("Summa")],
                pay_rows,
                styles,
                currency,
            )
        )
        story.append(Spacer(1, 6))
        story.append(
            _totals_table(
                [
                    (_("To‘langan jami"), folio.payments_total),
                    (_("Qoldiq"), folio.balance),
                ],
                styles,
                currency,
            )
        )
    else:
        story.append(Spacer(1, 6))
        story.append(_totals_table([(_("Qoldiq"), folio.balance)], styles, currency))

    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            f"{_('Rahmat!')} · {currency} · {_('Hujjat')}: {reservation.code}",
            styles["muted"],
        )
    )
    doc.build(story)
    return buf.getvalue()


def build_company_invoice_pdf(invoice) -> bytes:
    company = invoice.company
    hotel = invoice.hotel
    tenant = getattr(invoice, "tenant", None)
    currency = getattr(tenant, "currency", None) or "UZS"
    styles = _styles()
    buf = BytesIO()
    doc = _doc(buf)
    doc.title = f"Invoice {invoice.code}"

    brand = tenant.name if tenant else (hotel.name if hotel else company.name)
    issued = timezone.localtime(invoice.issued_at).strftime("%d.%m.%Y %H:%M")

    left = [f"<b>{brand}</b>"]
    if hotel:
        left.append(hotel.name)
        if hotel.address:
            addr = hotel.address
            if hotel.city:
                addr = f"{addr}, {hotel.city}"
            left.append(addr)
        if hotel.phone:
            left.append(hotel.phone)
    right = [
        f"<b>{_('Kompaniya hisob-fakturasi')}</b>",
        f"№ {invoice.code}",
        f"{_('Sana')}: {issued}",
        f"{_('Holat')}: {invoice.get_status_display()}",
    ]
    if invoice.due_date:
        right.append(f"{_('Muddat')}: {invoice.due_date.strftime('%d.%m.%Y')}")

    story = [
        Paragraph(brand, styles["brand"]),
        _header_table(left[1:] or [company.name], right, styles),
        HRFlowable(width="100%", thickness=1.2, color=BRAND, spaceBefore=8, spaceAfter=8),
        Paragraph(_("Kompaniya hisobi"), styles["title"]),
        Paragraph(f"<b>{company.name}</b>", styles["body"]),
    ]
    if company.inn:
        story.append(Paragraph(f"{_('INN')}: {company.inn}", styles["muted"]))
    if company.phone or company.email:
        story.append(
            Paragraph(
                " · ".join(x for x in [company.phone, company.email] if x),
                styles["muted"],
            )
        )
    story.append(Spacer(1, 10))

    line_rows = []
    for line in invoice.lines.all():
        desc = line.description
        if line.source_reservation_id:
            desc = f"{desc} · {line.source_reservation.code}"
        line_rows.append(
            (
                desc,
                "1",
                line.amount,
                getattr(line, "currency", None) or currency,
            )
        )
    story.append(
        _lines_table(
            [_("Tavsif"), _("Miqdor"), _("Summa")],
            line_rows,
            styles,
            currency,
        )
    )
    story.append(Spacer(1, 8))
    story.append(_totals_table([(_("Jami"), invoice.lines_total)], styles, currency))

    payments = [p for p in invoice.payments.all() if not getattr(p, "is_void", False)]
    if payments:
        story.append(Paragraph(_("To‘lovlar"), styles["h2"]))
        pay_rows = []
        for p in payments:
            label = p.get_method_display()
            if p.note:
                label = f"{label} · {p.note}"
            pay_rows.append(
                (
                    label,
                    "",
                    p.amount,
                    getattr(p, "currency", None) or currency,
                )
            )
        story.append(
            _lines_table([_("Usul"), "", _("Summa")], pay_rows, styles, currency)
        )
        story.append(Spacer(1, 6))
        story.append(
            _totals_table(
                [
                    (_("To‘langan jami"), invoice.payments_total),
                    (_("Qoldiq"), invoice.balance),
                ],
                styles,
                currency,
            )
        )
    else:
        story.append(Spacer(1, 6))
        story.append(_totals_table([(_("Qoldiq"), invoice.balance)], styles, currency))

    if invoice.notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"{_('Izoh')}: {invoice.notes}", styles["muted"]))

    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            f"{_('Rahmat!')} · {currency} · {_('Hujjat')}: {invoice.code}",
            styles["muted"],
        )
    )
    doc.build(story)
    return buf.getvalue()
