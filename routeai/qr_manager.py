"""
qr_manager.py — ResilientChain AI
===================================
QR code generation, PDF export, scan registration, and hub inventory
management for the ResilientChain AI logistics platform.

QR String Format:
    PK{package_number}G{group_number}{origin_code}{dest_code}
    e.g.  PK1G1BENMUM  →  Package 1, Group 1, Bengaluru → Mumbai
          PK7G3HYDCOC  →  Package 7, Group 3, Hyderabad → Cochin

Libraries used:
    qrcode       — QR image generation
    Pillow       — image manipulation
    reportlab    — PDF composition
    firebase-admin — Firestore persistence

Complexity annotations follow CD343AI course units.
"""

import io
import re
import json
import time as _time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image as RLImage, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors as rl_table_colors

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def now_ts() -> str:
    """Return current IST time as YYYY-MM-DD HH:MM:SS (UTC+5:30)."""
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d %H:%M:%S')


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

VALID_CITY_CODES = {"BEN", "MUM", "HYD", "VIZ", "COC", "CHE"}

CITY_FULL_NAMES = {
    "BEN": "Bengaluru",
    "MUM": "Mumbai",
    "HYD": "Hyderabad",
    "VIZ": "Visakhapatnam",
    "COC": "Cochin",
    "CHE": "Chennai",
}

# Regex pattern for QR string validation
# PK<int>G<int><3-letter origin><3-letter dest>
_QR_PATTERN = re.compile(
    r"^PK(?P<pkg_num>\d+)G(?P<grp_num>\d+)"
    r"(?P<origin>[A-Z]{3})(?P<dest>[A-Z]{3})$"
)

# ─── Duplicate scan cooldown store (in-memory) ────────────────────────────────
# Key: "{package_id}@{hub_id}"  Value: unix timestamp of last scan
# Complexity — CD343AI Unit II — Hash Map O(1) per lookup/insert
_scan_cooldown: dict[str, float] = {}
_SCAN_COOLDOWN_S: int = 30   # seconds within which a re-scan is a DUPLICATE

# ─────────────────────────────────────────────────────────────────────────────
# FIREBASE INITIALISATION (lazy, safe)
# ─────────────────────────────────────────────────────────────────────────────

_db: Optional[object] = None          # Firestore client singleton


def _get_db():
    """
    Lazily initialise and return the Firestore client.
    Reads FIREBASE_CREDENTIALS_JSON env var only — no file fallback.
    """
    global _db
    if _db is not None:
        return _db

    if not _FIREBASE_AVAILABLE:
        logger.warning("firebase-admin not installed. Using in-memory stub.")
        _db = _InMemoryStore()
        return _db

    if not firebase_admin._apps:
        try:
            import os as _os, json as _json
            cred_json = _os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred = credentials.Certificate(_json.loads(cred_json))
            else:
                raise FileNotFoundError('No Firebase credentials — set FIREBASE_CREDENTIALS_JSON env var')
            firebase_admin.initialize_app(cred)
        except Exception as exc:
            logger.warning("Firebase init failed (%s). Using in-memory stub.", exc)
            _db = _InMemoryStore()
            return _db

    _db = firestore.client()
    return _db


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY STORE (fallback when Firestore is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

class _InMemoryStore:
    """
    Minimal dict-based Firestore stub for local development.
    Mirrors the collection/document API subset used by this module.

    Complexity — CD343AI Unit II — Hash Map:
      Time:  O(1) average per get/set
      Space: O(N) where N = total documents stored
    """

    def __init__(self):
        self._data: dict[str, dict] = {}       # collection → {doc_id → data}

    def collection(self, name: str):
        self._data.setdefault(name, {})
        return _InMemoryCollection(self._data[name])


class _InMemoryCollection:
    def __init__(self, store: dict):
        self._store = store

    def document(self, doc_id: str):
        return _InMemoryDoc(self._store, doc_id)

    def where(self, field: str, op: str, value):
        return _InMemoryQuery(self._store, field, op, value)

    def stream(self):
        for doc_id, data in self._store.items():
            yield _InMemoryDocSnap(doc_id, data)


class _InMemoryDoc:
    def __init__(self, store: dict, doc_id: str):
        self._store = store
        self._id = doc_id

    def get(self):
        data = self._store.get(self._id)
        return _InMemoryDocSnap(self._id, data)

    def set(self, data: dict, merge: bool = False):
        if merge and self._id in self._store:
            self._store[self._id].update(data)
        else:
            self._store[self._id] = dict(data)

    def update(self, data: dict):
        self._store.setdefault(self._id, {}).update(data)


class _InMemoryQuery:
    def __init__(self, store: dict, field: str, op: str, value):
        self._store = store
        self._field = field
        self._op = op
        self._value = value

    def stream(self):
        for doc_id, data in self._store.items():
            v = data.get(self._field)
            if self._op == "==" and v == self._value:
                yield _InMemoryDocSnap(doc_id, data)


class _InMemoryDocSnap:
    def __init__(self, doc_id: str, data):
        self.id = doc_id
        self._data = data or {}

    @property
    def exists(self):
        return self._data is not None and bool(self._data)

    def to_dict(self):
        return dict(self._data)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_qr_string(package_number: int, group_number: int,
                     origin: str, destination: str) -> str:
    """
    Build the canonical QR string.

    Complexity — CD343AI Unit I — String Formatting:
      Time:  O(1)
      Space: O(1)
    """
    return f"PK{package_number}G{group_number}{origin.upper()}{destination.upper()}"


def _parse_qr_string(qr_string: str) -> dict:
    """
    Parse and validate a QR string into its component fields.

    Raises ValueError if the string does not match the expected format
    or contains unknown city codes.

    Complexity — CD343AI Unit III — Regex / Pattern Matching:
      Time:  O(L) where L = length of qr_string
      Space: O(1)

    Returns:
        dict with keys: package_id, package_number, group_number,
                        origin, destination, origin_full, destination_full
    """
    m = _QR_PATTERN.match(qr_string.strip())
    if not m:
        raise ValueError(
            f"Invalid QR string '{qr_string}'. "
            f"Expected format: PK<n>G<n><ORIGIN><DEST> e.g. PK1G1BENMUM"
        )
    pkg_num  = int(m.group("pkg_num"))
    grp_num  = int(m.group("grp_num"))
    origin   = m.group("origin")
    dest     = m.group("dest")

    for code, label in [(origin, "origin"), (dest, "destination")]:
        if code not in VALID_CITY_CODES:
            raise ValueError(
                f"Unknown {label} city code '{code}'. "
                f"Valid codes: {sorted(VALID_CITY_CODES)}"
            )

    return {
        "package_id":       qr_string.strip(),
        "package_number":   pkg_num,
        "group_number":     grp_num,
        "origin":           origin,
        "destination":      dest,
        "origin_full":      CITY_FULL_NAMES.get(origin, origin),
        "destination_full": CITY_FULL_NAMES.get(dest, dest),
    }


def _render_qr_image(qr_string: str, package_type: str,
                     size_px: int = 300) -> Image.Image:
    """
    Generate a PIL Image containing the QR code with a label strip.

    Layout (top → bottom):
      ┌──────────────────────┐
      │  [FRAGILE] badge     │  ← 30px badge strip
      │  QR matrix           │  ← size_px × size_px
      │  PK1G1BENMUM         │  ← code label
      └──────────────────────┘

    Complexity — CD343AI Unit II — Image Composition O(size_px²):
      Time:  O(P²) where P = size_px (pixel fill)
      Space: O(P²)
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_string)
    qr.make(fit=True)
    qr_img: Image.Image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((size_px, size_px), Image.LANCZOS)

    badge_h = 30
    label_h = 28
    total_h = badge_h + size_px + label_h
    canvas  = Image.new("RGB", (size_px, total_h), "white")
    draw    = ImageDraw.Draw(canvas)

    # Badge strip
    badge_color = "#D85A30" if package_type == "FRAGILE" else "#0F6E56"
    draw.rectangle([(0, 0), (size_px, badge_h)], fill=badge_color)
    try:
        font_badge = ImageFont.truetype("arial.ttf", 14)
        font_label = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font_badge = ImageFont.load_default()
        font_label = ImageFont.load_default()

    badge_text = f"⚠ {package_type}" if package_type == "FRAGILE" else f"✓ {package_type}"
    draw.text((size_px // 2, badge_h // 2), badge_text,
              fill="white", font=font_badge, anchor="mm")

    # QR image
    canvas.paste(qr_img, (0, badge_h))

    # Label
    draw.rectangle([(0, badge_h + size_px), (size_px, total_h)], fill="#F5F5F5")
    draw.text((size_px // 2, badge_h + size_px + label_h // 2),
              qr_string, fill="#1A1A2E", font=font_label, anchor="mm")

    return canvas


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_group_qr_codes(
    group_number: int,
    origin: str,
    destination: str,
    total_packages: int,
    package_type: str,
) -> tuple[list[Image.Image], dict]:
    """
    Generate QR code images for every package in a group and persist
    the group + individual package records to Firestore.

    Args:
        group_number    (int):  group identifier
        origin          (str):  3-letter origin city code (e.g. "BEN")
        destination     (str):  3-letter destination city code (e.g. "MUM")
        total_packages  (int):  number of packages in the group (≥ 1)
        package_type    (str):  "FRAGILE" or "STANDARD"

    Returns:
        (images, metadata)
        images   — list of PIL Image objects, one per package
        metadata — dict with group_id, qr_strings, created_at, etc.

    Raises:
        ValueError — invalid city codes, package_type, or total_packages

    Complexity — CD343AI Unit I — Iteration + Image Generation:
      Time:  O(N * P²)  N = total_packages, P = QR image pixel size
      Space: O(N * P²)  all images held in memory
    """
    origin      = origin.upper().strip()
    destination = destination.upper().strip()
    package_type = package_type.upper().strip()

    # Validate inputs
    if origin not in VALID_CITY_CODES:
        raise ValueError(f"Invalid origin city code '{origin}'.")
    if destination not in VALID_CITY_CODES:
        raise ValueError(f"Invalid destination city code '{destination}'.")
    if package_type not in ("FRAGILE", "STANDARD"):
        raise ValueError("package_type must be 'FRAGILE' or 'STANDARD'.")
    if total_packages < 1:
        raise ValueError("total_packages must be ≥ 1.")

    db          = _get_db()
    images      = []
    qr_strings  = []
    now_iso  = now_ts()
    group_id    = f"G{group_number}"

    for pkg_num in range(1, total_packages + 1):
        qr_string = _build_qr_string(pkg_num, group_number, origin, destination)
        qr_strings.append(qr_string)

        # Render image
        img = _render_qr_image(qr_string, package_type)
        images.append(img)

        # Persist package document
        pkg_doc = {
            "package_id":   qr_string,
            "group_id":     group_id,
            "origin":       origin,
            "destination":  destination,
            "package_type": package_type,
            "current_hub":  None,
            "status":       "CREATED",
            "scan_history": [],
            "created_at":   now_iso,
        }
        db.collection("packages").document(qr_string).set(pkg_doc)

    # Persist group document
    group_doc = {
        "group_id":       group_id,
        "total_packages": total_packages,
        "origin":         origin,
        "destination":    destination,
        "package_type":   package_type,
        "created_at":     now_iso,
        "pdf_path":       None,
    }
    db.collection("groups").document(group_id).set(group_doc)

    metadata = {
        "group_id":         group_id,
        "group_number":     group_number,
        "origin":           origin,
        "origin_full":      CITY_FULL_NAMES.get(origin, origin),
        "destination":      destination,
        "destination_full": CITY_FULL_NAMES.get(destination, destination),
        "package_type":     package_type,
        "total_packages":   total_packages,
        "qr_strings":       qr_strings,
        "created_at":       now_iso,
    }
    logger.info("Generated %d QR codes for group %s (%s→%s).",
                total_packages, group_id, origin, destination)
    return images, metadata


def generate_load_pdf(
    shipments: list[dict],
    trucks: list[dict],
    metadata: dict,
) -> bytes:
    """
    Generate a load plan PDF using reportlab (no wkhtmltopdf).

    Layout:
      - Header: company name, date, document title
      - Shipment table: ID, Origin, Destination, Weight, Priority, Assigned Truck
      - Per-truck route section with waypoints
      - Footer with generation timestamp

    Args:
        shipments: list of shipment dicts with keys: id, origin, destination,
                   weight_kg, priority, assigned_truck
        trucks:    list of truck dicts with keys: id, route, distance_km, co2_kg
        metadata:  dict with keys: title, generated_at, total_shipments, total_weight

    Returns:
        bytes — raw PDF content

    Complexity — CD343AI Unit II — Table Composition:
      Time:  O(S + T) where S = shipments, T = trucks
      Space: O(1) from reportlab flowables
    """
    from datetime import datetime, timezone, timedelta
    PAGE_W, PAGE_H = A4
    MARGIN = 15 * mm
    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "LoadPlanTitle", parent=styles["Heading1"],
        alignment=TA_CENTER, textColor=rl_colors.HexColor("#1A1A2E"),
        spaceAfter=4, fontSize=18,
    )
    subtitle_style = ParagraphStyle(
        "LoadPlanSub", parent=styles["Normal"],
        alignment=TA_CENTER, fontSize=10,
        textColor=rl_colors.HexColor("#666666"), spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"],
        textColor=rl_colors.HexColor("#534AB7"), spaceAfter=6, spaceBefore=14,
    )
    cell_style = ParagraphStyle(
        "TableCell", parent=styles["Normal"], fontSize=8, leading=10,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=7, textColor=rl_colors.HexColor("#999999"), spaceBefore=10,
    )

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=metadata.get("title", "Load Plan"),
        author="ResilientChain AI",
    )
    story = []

    # ── Header ──
    story.append(Paragraph("ResilientChain AI", title_style))
    story.append(Paragraph(
        f"Load Plan &mdash; {metadata.get('title', 'Truck Assignment')}",
        subtitle_style,
    ))
    generated = metadata.get("generated_at", now_ts())
    story.append(Paragraph(
        f"Generated: {generated[:19]} &nbsp;|&nbsp; "
        f"Shipments: {metadata.get('total_shipments', 0)} &nbsp;|&nbsp; "
        f"Total Weight: {metadata.get('total_weight', 0)} kg",
        subtitle_style,
    ))
    story.append(Spacer(1, 6 * mm))

    # ── Shipment Table ──
    story.append(Paragraph("Assigned Shipments", section_style))
    header = ["ID", "Origin", "Destination", "Weight (kg)", "Priority", "Truck"]
    table_data = [header]
    for s in shipments:
        table_data.append([
            Paragraph(str(s.get("id", "")), cell_style),
            Paragraph(str(s.get("origin", "")), cell_style),
            Paragraph(str(s.get("destination", "")), cell_style),
            Paragraph(str(s.get("weight_kg", 0)), cell_style),
            Paragraph(str(s.get("priority", "Normal")), cell_style),
            Paragraph(str(s.get("assigned_truck", "")), cell_style),
        ])
    col_widths = [50, 55, 55, 55, 50, 55]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_table_colors.HexColor("#534AB7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_table_colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_table_colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_table_colors.white, rl_table_colors.HexColor("#F5F5FF")]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))

    # ── Per-Truck Route Sections ──
    for t in trucks:
        tid = t.get("id", "?")
        route = t.get("route", [])
        dist = t.get("distance_km", 0)
        co2 = t.get("co2_kg", 0)

        story.append(Paragraph(
            f"Truck {tid} &mdash; Route: {' → '.join(route)}",
            section_style,
        ))
        waypoint_str = " → ".join(route) if route else "No route assigned"
        story.append(Paragraph(
            f"<b>Waypoints:</b> {waypoint_str}<br/>"
            f"<b>Distance:</b> {dist} km &nbsp;|&nbsp; "
            f"<b>CO₂:</b> {co2} kg",
            cell_style,
        ))
        story.append(Spacer(1, 4 * mm))

    # ── Footer ──
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"ResilientChain AI &mdash; Generated {generated[:19]} IST &mdash; "
        "This is a computer-generated document.",
        footer_style,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


def generate_truck_load_pdf(
    shipments: list[dict],
    meta: dict,
) -> bytes:
    """
    Generate a per-truck load plan PDF with 2D container visualization.

    Includes: truck info, container viz with CoM, package table, physics analysis.
    """
    from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
    from reportlab.graphics import renderPDF

    PAGE_W, PAGE_H = A4
    MARGIN = 15 * mm
    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TruckTitle", parent=styles["Heading1"],
        alignment=TA_CENTER, textColor=rl_colors.HexColor("#1A1A2E"),
        spaceAfter=2, fontSize=16,
    )
    subtitle_style = ParagraphStyle(
        "TruckSub", parent=styles["Normal"],
        alignment=TA_CENTER, fontSize=9,
        textColor=rl_colors.HexColor("#666666"), spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        textColor=rl_colors.HexColor("#534AB7"), spaceAfter=4, spaceBefore=10, fontSize=12,
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"], fontSize=7.5, leading=9,
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=7, leading=9,
        textColor=rl_colors.HexColor("#555555"),
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=7, textColor=rl_colors.HexColor("#999999"), spaceBefore=8,
    )

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=meta.get("title", "Truck Load Plan"),
        author="ResilientChain AI",
    )
    story = []
    truck_color = meta.get("truck_color", "#534AB7")

    # ── Header ──
    story.append(Paragraph("ResilientChain AI", title_style))
    story.append(Paragraph(
        f"Truck {meta.get('truck_id', '?')} &mdash; {meta.get('truck_route', 'Load Plan')}",
        subtitle_style,
    ))
    ts = meta.get("generated_at", "")
    cap = meta.get("capacity_kg", 800)
    tw = meta.get("total_weight", 0)
    util = meta.get("utilization_pct", 0)
    story.append(Paragraph(
        f"Generated: {ts[:19]} &nbsp;|&nbsp; "
        f"Capacity: {cap} kg &nbsp;|&nbsp; "
        f"Load: {tw} kg ({util}%) &nbsp;|&nbsp; "
        f"Packages: {meta.get('total_shipments', 0)} &nbsp;|&nbsp; "
        f"Fragile: {meta.get('fragile_count', 0)}",
        subtitle_style,
    ))
    story.append(Spacer(1, 4 * mm))

    # ── 2D Container Visualization ──
    story.append(Paragraph("Container Load Visualization", section_style))

    viz_w, viz_h = 520, 180
    d = Drawing(viz_w, viz_h)

    # Container outline
    d.add(Rect(2, 2, viz_w - 4, viz_h - 4, fillColor=rl_colors.HexColor("#0d1117"),
               strokeColor=rl_colors.HexColor("#334155"), strokeWidth=1.5))

    # Fragile zone (top 30%)
    fragile_zone_y = viz_h * 0.7
    d.add(Rect(4, fragile_zone_y, viz_w - 8, viz_h - fragile_zone_y - 4,
               fillColor=rl_colors.HexColor("#f59e0b10"), strokeColor=rl_colors.HexColor("#f59e0b40"),
               strokeWidth=0.5, strokeDashArray=[4, 2]))
    d.add(String(viz_w - 60, fragile_zone_y + 4, "FRAGILE ZONE",
                 fillColor=rl_colors.HexColor("#f59e0b80"), fontSize=6, fontName="Helvetica-Bold"))

    # Front/rear labels
    d.add(String(8, 4, "FRONT", fillColor=rl_colors.HexColor("#475569"), fontSize=6, fontName="Helvetica-Bold"))
    d.add(String(viz_w - 40, 4, "REAR", fillColor=rl_colors.HexColor("#475569"), fontSize=6, fontName="Helvetica-Bold"))

    # Floor line
    d.add(Line(4, 18, viz_w - 4, 18, strokeColor=rl_colors.HexColor("#334155"), strokeWidth=1))

    # Sort: heavy items bottom, fragile on top
    std_items = sorted([s for s in shipments if s.get("type") != "FRAGILE"],
                       key=lambda s: s.get("weight_kg", s.get("weight", 0)), reverse=True)
    frag_items = sorted([s for s in shipments if s.get("type") == "FRAGILE"],
                        key=lambda s: s.get("weight_kg", s.get("weight", 0)), reverse=True)
    sorted_items = std_items + frag_items

    COLS_HEX = ["#7c74e8", "#10b981", "#f97316", "#38bdf8", "#f59e0b", "#e879f9", "#84cc16", "#94a3b8"]
    usable_w = viz_w - 16
    row_h = 38
    cur_x, cur_y, max_row_h = 8, 20, 0
    placements = []

    for idx, s in enumerate(sorted_items):
        vol = s.get("volume_m3", s.get("vol", 0.5))
        w = max(30, min(int(vol * 60), int(usable_w * 0.45)))
        h = row_h - 4 if s.get("type") == "FRAGILE" else row_h
        if cur_x + w > usable_w + 8:
            cur_x = 8
            cur_y += max_row_h + 3
            max_row_h = 0
        if cur_y + h > viz_h - 8:
            cur_y = 20
        pkg_id = s.get("id", f"S{idx+1}")
        weight = s.get("weight_kg", s.get("weight", 0))
        col = rl_colors.HexColor(COLS_HEX[idx % len(COLS_HEX)])

        d.add(Rect(cur_x, cur_y, w, h, fillColor=col, strokeColor=col, strokeWidth=0.5, rx=2))
        if s.get("type") == "FRAGILE":
            d.add(Rect(cur_x, cur_y, w, h, fillColor=rl_colors.HexColor("#ffffff20"),
                       strokeColor=rl_colors.HexColor("#f59e0b"), strokeWidth=1, rx=2, strokeDashArray=[2, 2]))
        if w > 28:
            d.add(String(cur_x + w / 2, cur_y + h / 2 + 2, str(pkg_id),
                         fillColor=rl_colors.white, fontSize=5.5, fontName="Helvetica-Bold",
                         textAnchor="middle"))
            d.add(String(cur_x + w / 2, cur_y + h / 2 - 7, f"{weight}kg",
                         fillColor=rl_colors.HexColor("#ffffffcc"), fontSize=5, textAnchor="middle"))

        placements.append({"x": cur_x, "y": cur_y, "w": w, "h": h, "weight": weight})
        cur_x += w + 3
        max_row_h = max(max_row_h, h)

    # Center of Mass
    if placements:
        total_w = sum(p["weight"] for p in placements) or 1
        com_x = sum((p["x"] + p["w"] / 2) * p["weight"] for p in placements) / total_w
        com_y = sum((p["y"] + p["h"] / 2) * p["weight"] for p in placements) / total_w
        d.add(Line(com_x, 20, com_x, viz_h - 4, strokeColor=rl_colors.HexColor("#ef444480"),
                   strokeWidth=0.8, strokeDashArray=[3, 2]))
        d.add(Line(4, com_y, viz_w - 4, com_y, strokeColor=rl_colors.HexColor("#ef444480"),
                   strokeWidth=0.8, strokeDashArray=[3, 2]))
        pts = [com_x, com_y - 5, com_x + 4, com_y, com_x, com_y + 5, com_x - 4, com_y]
        d.add(Polygon(pts, fillColor=rl_colors.HexColor("#ef4444"), strokeColor=rl_colors.white, strokeWidth=0.5))
        com_safe = abs(com_x / viz_w - 0.5) < 0.15
        label = "CoM SAFE" if com_safe else "CoM SHIFTED"
        lcol = rl_colors.HexColor("#10b981") if com_safe else rl_colors.HexColor("#ef4444")
        d.add(String(com_x + 7, com_y + 3, label, fillColor=lcol, fontSize=5.5, fontName="Helvetica-Bold"))
    else:
        com_safe = True

    story.append(d)
    story.append(Spacer(1, 3 * mm))

    # ── Utilization bar ──
    bar_data = [
        [Paragraph("<b>Utilization</b>", cell_style),
         Paragraph(f"<b>{util}%</b> ({tw}kg / {cap}kg)", cell_style)],
        [Paragraph("Status", cell_style),
         Paragraph(f"<b>{'OPTIMAL' if 60 <= util <= 85 else 'OVERLOADED' if util > 85 else 'UNDERLOADED'}</b>", cell_style)],
        [Paragraph("CoM Stability", cell_style),
         Paragraph(f"<b>{'STABLE' if com_safe else 'UNSTABLE - redistribute load'}</b>", cell_style)],
    ]
    bar_tbl = Table(bar_data, colWidths=[80, 200])
    bar_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), rl_colors.HexColor("#f0f0f8")),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#dddddd")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bar_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Package Table ──
    story.append(Paragraph("Package Details", section_style))
    header = ["#", "Package ID", "Weight (kg)", "Volume (m³)", "Type", "Priority", "Placement"]
    table_data = [header]
    for idx, s in enumerate(sorted_items):
        pkg_id = s.get("id", f"S{idx+1}")
        weight = s.get("weight_kg", s.get("weight", 0))
        vol = s.get("volume_m3", s.get("vol", 0))
        ptype = s.get("type", "STANDARD")
        pri = s.get("priority", s.get("pri", 3))
        row_idx = placements[idx]["y"] if idx < len(placements) else 0
        layer = "Bottom" if row_idx < viz_h * 0.4 else "Middle" if row_idx < viz_h * 0.7 else "Top"
        table_data.append([
            Paragraph(str(idx + 1), cell_style),
            Paragraph(str(pkg_id), cell_style),
            Paragraph(str(weight), cell_style),
            Paragraph(str(round(vol, 2)), cell_style),
            Paragraph(f"<b>{ptype}</b>", cell_style),
            Paragraph("★" * pri + "☆" * (5 - pri), cell_style),
            Paragraph(f"Row {layer}", cell_style),
        ])

    col_widths = [20, 70, 45, 45, 45, 55, 50]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#534AB7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F5FF")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Physics Analysis ──
    story.append(Paragraph("Physics & Placement Analysis", section_style))
    heavy_items = [s for s in shipments if s.get("type") != "FRAGILE"]
    fragile_items = [s for s in shipments if s.get("type") == "FRAGILE"]
    heavy_total = sum(s.get("weight_kg", s.get("weight", 0)) for s in heavy_items)
    frag_total = sum(s.get("weight_kg", s.get("weight", 0)) for s in fragile_items)
    physics_points = []
    physics_points.append(f"Heavy items ({len(heavy_items)} packages, {heavy_total}kg) placed at container bottom for low centre of gravity")
    if fragile_items:
        physics_points.append(f"Fragile items ({len(fragile_items)} packages, {frag_total}kg) placed above heavy items to prevent breakage")
    if com_safe:
        physics_points.append("Centre of Mass is within safe zone (&plusmn;15% of centre) - minimal topple risk")
    else:
        physics_points.append("Centre of Mass is SHIFTED - redistribute heavy items for stability")
    remaining_cap = cap - tw
    physics_points.append(f"Remaining capacity: {remaining_cap}kg ({round(remaining_cap / cap * 100, 1)}%) - {' adequate buffer' if remaining_cap > 100 else 'WARNING: low buffer'}")
    for pt in physics_points:
        story.append(Paragraph(f"&bull; {pt}", small_style))
    story.append(Spacer(1, 4 * mm))

    # ── Footer ──
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"ResilientChain AI &mdash; Truck {meta.get('truck_id', '?')} Load Plan &mdash; "
        f"Generated {ts[:19]} IST &mdash; This is a computer-generated document.",
        footer_style,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


def export_to_pdf(
    qr_images: list[Image.Image],
    metadata: dict,
    filename: str = "qr_codes.pdf",
) -> bytes:
    """
    Arrange QR code images in a 4-per-row grid across A4 pages and
    return the PDF as raw bytes.

    Layout per cell:
      • Group info header (once per page)
      • QR image (300×358 px rendered, scaled to fit cell)
      • Code string label beneath each image
      • Package type badge color on header

    Args:
        qr_images (list[PIL.Image]): images from generate_group_qr_codes()
        metadata  (dict):            metadata dict from generate_group_qr_codes()
        filename  (str):             used for the PDF title metadata field

    Returns:
        bytes — raw PDF content ready for HTTP streaming

    Complexity — CD343AI Unit II — Grid Layout Composition:
      Time:  O(N) where N = number of QR images
      Space: O(N) in-memory image buffers + O(1) per reportlab flowable
    """
    COLS        = 4
    PAGE_W, PAGE_H = A4            # 595.28 pt × 841.89 pt
    MARGIN      = 15 * mm
    CELL_W      = (PAGE_W - 2 * MARGIN) / COLS
    CELL_IMG_H  = CELL_W           # square cell
    GUTTER      = 4 * mm

    buf     = io.BytesIO()
    styles  = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "GroupHeader",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        textColor=rl_colors.HexColor("#1A1A2E"),
        spaceAfter=6,
    )
    sub_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=rl_colors.HexColor("#534AB7"),
        spaceAfter=8,
    )
    badge_color = rl_colors.HexColor("#D85A30" if metadata.get("package_type") == "FRAGILE"
                                     else "#0F6E56")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=filename,
        author="ResilientChain AI",
    )

    story = []

    # Page header
    group_id  = metadata.get("group_id", "")
    origin_f  = metadata.get("origin_full", metadata.get("origin", ""))
    dest_f    = metadata.get("destination_full", metadata.get("destination", ""))
    pkg_type  = metadata.get("package_type", "STANDARD")
    total     = metadata.get("total_packages", len(qr_images))
    created   = metadata.get("created_at", "")[:10]

    story.append(Paragraph(
        f"ResilientChain AI — Group {group_id} QR Codes", title_style
    ))
    story.append(Paragraph(
        f"Route: {origin_f} → {dest_f}  |  Type: {pkg_type}  |  "
        f"Packages: {total}  |  Generated: {created}",
        sub_style,
    ))
    story.append(Spacer(1, 4 * mm))

    # Build image buffers and rows
    def _img_buf(pil_img: Image.Image) -> io.BytesIO:
        b = io.BytesIO()
        pil_img.save(b, format="PNG")
        b.seek(0)
        return b

    lbl_style = ParagraphStyle("CellLbl", alignment=TA_CENTER, fontSize=7,
                                textColor=rl_colors.HexColor("#444444"))
    empty_cell = Paragraph("", lbl_style)   # proper flowable for padding

    rows = []
    row  = []
    for img, qr_str in zip(qr_images, metadata.get("qr_strings", [])):
        img_buf = _img_buf(img)
        rl_img  = RLImage(img_buf,
                          width=CELL_W  - GUTTER,
                          height=CELL_IMG_H - GUTTER)
        label   = Paragraph(qr_str, lbl_style)
        # Wrap image + label in a nested 1-column Table so reportlab
        # handles the multi-flowable cell correctly.
        inner = Table(
            [[rl_img], [label]],
            colWidths=[CELL_W - GUTTER],
        )
        inner.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        row.append(inner)
        if len(row) == COLS:
            rows.append(row)
            row = []

    # Pad last row with proper empty flowables (not plain strings)
    while row and len(row) < COLS:
        row.append(empty_cell)
    if row:
        rows.append(row)

    if rows:
        tbl = Table(rows, colWidths=[CELL_W] * COLS)
        tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("GRID",          (0, 0), (-1, -1), 0.25, rl_colors.lightgrey),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)

    doc.build(story)
    pdf_bytes = buf.getvalue()

    # Update Firestore pdf_path with a placeholder path
    db = _get_db()
    db.collection("groups").document(metadata.get("group_id", "")).update(
        {"pdf_path": f"/exports/{filename}"}
    )

    logger.info("PDF exported: %s (%d bytes, %d images).",
                filename, len(pdf_bytes), len(qr_images))
    return pdf_bytes


def register_scan(
    qr_string: str,
    hub_id: str,
    timestamp: Optional[str] = None,
) -> dict:
    """
    Process a QR code scan at a hub.

    Scan logic:
      • Package NOT in inventory at hub_id → INBOUND scan
          - status set to "IN_TRANSIT" if previously seen, else "INBOUND"
          - current_hub updated to hub_id
      • Package already at hub_id (current_hub == hub_id) → OUTBOUND scan
          - current_hub cleared, status set to "IN_TRANSIT"

    Each scan appended to scan_history[] in Firestore.

    Args:
        qr_string (str): scanned QR code string, e.g. "PK1G1BENMUM"
        hub_id    (str): hub node ID, e.g. "BEN_H1" or "W4"
        timestamp (str): ISO-8601 string; defaults to UTC now

    Returns:
        dict with keys: action, package_id, hub_id, metadata, status

    Raises:
        ValueError — malformed QR string

    Complexity — CD343AI Unit III — Hash Map Lookup + Firestore I/O:
      Time:  O(L) parse + O(1) Firestore get/set (network latency aside)
      Space: O(H) where H = length of scan_history
    """
    ts = timestamp or now_ts()
    meta    = _parse_qr_string(qr_string)   # raises ValueError on bad string
    db      = _get_db()

    # ── Duplicate check (30-second cooldown) ─────────────────────────────────
    # Complexity: O(1) dict lookup
    cooldown_key = f"{qr_string}@{hub_id}"
    now_unix     = _time.time()
    if cooldown_key in _scan_cooldown and (now_unix - _scan_cooldown[cooldown_key]) < _SCAN_COOLDOWN_S:
        remaining = round(_SCAN_COOLDOWN_S - (now_unix - _scan_cooldown[cooldown_key]), 1)
        logger.info("DUPLICATE scan suppressed: %s @ %s (cooldown %.1fs remaining).",
                    qr_string, hub_id, remaining)
        return {
            "action":     "DUPLICATE",
            "package_id": qr_string,
            "hub_id":     hub_id,
            "timestamp":  ts,
            "metadata":   meta,
            "status":     "DUPLICATE",
            "message":    f"Duplicate scan within {_SCAN_COOLDOWN_S}s — ignored",
            "cooldown_remaining_s": remaining,
        }
    _scan_cooldown[cooldown_key] = now_unix

    pkg_ref = db.collection("packages").document(qr_string)
    snap    = pkg_ref.get()

    scan_entry = {
        "hub_id":    hub_id,
        "timestamp": ts,
    }

    if not snap.exists:
        # First-ever scan: create the document on the fly
        action = "INBOUND"
        scan_entry["action"] = action
        pkg_data = {
            "package_id":   qr_string,
            "group_id":     f"G{meta['group_number']}",
            "origin":       meta["origin"],
            "destination":  meta["destination"],
            "package_type": "UNKNOWN",
            "current_hub":  hub_id,
            "status":       "INBOUND",
            "scan_history": [scan_entry],
            "created_at":   ts,
        }
        pkg_ref.set(pkg_data)
    else:
        existing = snap.to_dict()
        current_hub = existing.get("current_hub")

        if current_hub == hub_id:
            # Already at this hub → OUTBOUND
            action = "OUTBOUND"
            scan_entry["action"] = action
            dest_code = meta["destination"]
            is_final  = (hub_id.startswith(dest_code) or
                         existing.get("destination") == hub_id)
            new_status = "DELIVERED" if is_final else "IN_TRANSIT"
            history    = existing.get("scan_history", [])
            history.append(scan_entry)
            pkg_ref.update({
                "current_hub":  None,
                "status":       new_status,
                "scan_history": history,
            })
        else:
            # At a new hub → INBOUND
            action = "INBOUND"
            scan_entry["action"] = action
            history = existing.get("scan_history", [])
            history.append(scan_entry)
            pkg_ref.update({
                "current_hub":  hub_id,
                "status":       "INBOUND",
                "scan_history": history,
            })

    # ── Persist scan event to scan_events collection ─────────────────────────
    # Complexity: O(1) Firestore write (amortised)
    event_doc = {
        "package_id": qr_string,
        "hub_id":     hub_id,
        "action":     action,
        "timestamp":  ts,
        "method":     "QR",
        "group_id":   f"G{meta['group_number']}",
        "origin":     meta["origin"],
        "destination": meta["destination"],
    }
    # Use timestamp as part of doc ID so newest sort by ID naturally
    safe_ts = ts.replace(":", "-").replace(".", "-")
    db.collection("scan_events").document(f"{safe_ts}_{qr_string}").set(event_doc)

    logger.info("Scan registered: %s action=%s hub=%s.", qr_string, action, hub_id)
    result = {
        "action":     action,
        "package_id": qr_string,
        "hub_id":     hub_id,
        "timestamp":  ts,
        "metadata":   meta,
        "status":     action,
        "message":    {
            "INBOUND":  f"{qr_string} registered as INBOUND at {hub_id}",
            "OUTBOUND": f"{qr_string} dispatched OUTBOUND from {hub_id}",
        }.get(action, action),
    }
    return result


def get_inventory_status(hub_id: str) -> dict:
    """
    Return all packages currently residing at hub_id
    (i.e., documents where current_hub == hub_id).

    Args:
        hub_id (str): hub node ID

    Returns:
        dict with keys:
            hub_id       — echoed
            total        — count of packages at hub
            packages     — list of package dicts
            retrieved_at — ISO timestamp

    Complexity — CD343AI Unit III — Linear Scan / Firestore Query:
      Time:  O(N) where N = total package documents (Firestore full scan)
             O(K) with a Firestore composite index on current_hub
      Space: O(K) where K = packages currently at hub
    """
    db   = _get_db()
    docs = db.collection("packages").where("current_hub", "==", hub_id).stream()

    packages = []
    for doc in docs:
        data = doc.to_dict()
        packages.append({
            "package_id":   data.get("package_id", doc.id),
            "group_id":     data.get("group_id"),
            "origin":       data.get("origin"),
            "destination":  data.get("destination"),
            "package_type": data.get("package_type"),
            "status":       data.get("status"),
            "last_scan":    (data.get("scan_history") or [{}])[-1],
        })

    return {
        "hub_id":       hub_id,
        "total":        len(packages),
        "packages":     packages,
        "retrieved_at": now_ts(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY CACHE: last generated QR set per group (for PDF download)
# ─────────────────────────────────────────────────────────────────────────────

_group_cache: dict[int, tuple[list, dict]] = {}


def cache_group(group_number: int, images: list, metadata: dict) -> None:
    """Store generated group data in module-level cache for PDF download.

    Complexity — CD343AI Unit II — Hash Map O(1):
      Time:  O(1)
      Space: O(N) where N = number of images stored
    """
    _group_cache[group_number] = (images, metadata)


def get_cached_group(group_number: int) -> Optional[tuple]:
    """Retrieve cached group data; returns None if not found.

    Complexity — CD343AI Unit II — Hash Map O(1):
      Time:  O(1)
      Space: O(1)
    """
    return _group_cache.get(group_number)


def get_scan_log(hub_id: Optional[str] = None, limit: int = 50) -> list:
    """
    Return recent scan events from the scan_events Firestore collection,
    optionally filtered by hub_id. Results are sorted newest-first.

    Args:
        hub_id (str | None): if provided, filter events to this hub only
        limit  (int):        maximum number of events to return (default 50)

    Returns:
        list of dicts, each with keys:
            package_id, hub_id, action, timestamp, method,
            group_id, origin, destination

    Complexity — CD343AI Unit III — Linear Scan + Sort:
      Time:  O(N log N) where N = total scan_events documents
             O(K log K) with a Firestore index on hub_id
      Space: O(N) in worst case; O(limit) after slicing
    """
    db   = _get_db()
    docs = db.collection("scan_events").stream()

    events: list[dict] = []
    for doc in docs:
        data = doc.to_dict()
        if hub_id and data.get("hub_id") != hub_id:
            continue
        events.append({
            "package_id":  data.get("package_id", ""),
            "hub_id":      data.get("hub_id", ""),
            "action":      data.get("action", ""),
            "timestamp":   data.get("timestamp", ""),
            "method":      data.get("method", "QR"),
            "group_id":    data.get("group_id", ""),
            "origin":      data.get("origin", ""),
            "destination": data.get("destination", ""),
        })

    # Sort newest first (ISO timestamps sort lexicographically)
    events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    logger.info("get_scan_log: returned %d events (hub_filter=%s).",
                min(len(events), limit), hub_id or "all")
    return events[:limit]
