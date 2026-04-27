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
import logging
from datetime import datetime, timezone
from typing import Optional

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False

logger = logging.getLogger(__name__)

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

# ─────────────────────────────────────────────────────────────────────────────
# FIREBASE INITIALISATION (lazy, safe)
# ─────────────────────────────────────────────────────────────────────────────

_db: Optional[object] = None          # Firestore client singleton


def _get_db():
    """
    Lazily initialise and return the Firestore client.
    Falls back to an in-memory stub when Firebase is unavailable
    (local dev without service-account credentials).

    Complexity — CD343AI Unit I — Singleton / Lazy Init:
      Time:  O(1) after first call
      Space: O(1)
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
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        except Exception:
            try:
                cred = credentials.Certificate("serviceAccountKey.json")
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
    now_iso     = datetime.now(timezone.utc).isoformat()
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
    ts      = timestamp or datetime.now(timezone.utc).isoformat()
    meta    = _parse_qr_string(qr_string)   # raises ValueError on bad string
    db      = _get_db()
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

    logger.info("Scan registered: %s action=%s hub=%s.", qr_string, action, hub_id)
    return {
        "action":     action,
        "package_id": qr_string,
        "hub_id":     hub_id,
        "timestamp":  ts,
        "metadata":   meta,
        "status":     scan_entry.get("action"),
    }


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
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY CACHE: last generated QR set per group (for PDF download)
# ─────────────────────────────────────────────────────────────────────────────

_group_cache: dict[int, tuple[list[Image.Image], dict]] = {}


def cache_group(group_number: int, images: list, metadata: dict) -> None:
    """Store generated group data in module-level cache for PDF download."""
    _group_cache[group_number] = (images, metadata)


def get_cached_group(group_number: int) -> Optional[tuple]:
    """Retrieve cached group data; returns None if not found."""
    return _group_cache.get(group_number)
