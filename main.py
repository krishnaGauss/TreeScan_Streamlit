import csv
import io
import re
import zipfile
from pathlib import Path

import fitz  # PyMuPDF
import segno
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ── constants ─────────────────────────────────────────────────────────────────

_SERIF_FONT    = Path(__file__).parent / "fonts" / "NotoSerif-Regular.ttf"
_DEVA_FONT     = Path(__file__).parent / "fonts" / "NotoSansDevanagari-Regular.ttf"
_TABLE_FONT    = Path(__file__).parent / "fonts" / "font.ttf"
_TEMPLATE_PATH = Path(__file__).parent / "template2.png"
_HEADER_PATH   = Path(__file__).parent / "header.jpeg"
_FOOTER_PATH   = Path(__file__).parent / "footer.png"

_CX = 627

_BOX_X1, _BOX_Y1 = 350, 395
_BOX_X2, _BOX_Y2 = 897, 937

_NUM_Y1,  _NUM_Y2  = 50,  182
_NAME_Y1, _NAME_Y2 = 240, 385

_TEXT_COLOR = "#1F3D2E"

_PAGE_W = 1240  # ~A4 at 150 DPI

_TABLE_ROWS = [
    ("S_No_",      "S_No_"),
    ("Vernacular", "Vernacular"),
    ("Scientific", "Scientific"),
    ("Family",     "Family"),
    ("Remarks_",   "Remarks_"),
    ("Latitude",   "Latitude"),
    ("Longitude",  "Longitude"),
    ("Plant_Orig", "Plant_Orig"),
]

# ── helpers (exact from app4.py) ──────────────────────────────────────────────

def _get_font(size: int, path: Path = _SERIF_FONT) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]


def _fit_and_draw(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int, cy: int,
    max_w: int, max_h: int,
    start_size: int,
    color: str,
    font_path: Path = _SERIF_FONT,
) -> None:
    size = start_size
    while size >= 12:
        font = _get_font(size, font_path)
        tw, th, ox, oy = _measure(draw, text, font)
        if tw <= max_w and th <= max_h:
            break
        size -= 2
    font = _get_font(size, font_path)
    tw, th, ox, oy = _measure(draw, text, font)
    draw.text((cx - tw // 2 - ox, cy - th // 2 - oy), text, fill=color, font=font)


def _has_devanagari(text: str) -> bool:
    return any('ऀ' <= ch <= 'ॿ' for ch in text)


def _english_from_vernacular(vernacular: str) -> str:
    """Return English name from inside (), or the raw Vernacular if absent/numeric."""
    m = re.search(r'\(([^)]+)\)', vernacular)
    if m:
        inner = m.group(1).strip()
        if inner and not inner.isdigit():
            return inner
    return vernacular.strip()


# ── QR generation (exact from app4.py) ───────────────────────────────────────

def make_qr_on_template2(url: str, tree_name: str = "", tree_number: str = "") -> Image.Image:
    qr = segno.make(url, error="h")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=10, border=2, dark="#000000", light="#ffffff")
    buf.seek(0)
    qr_img = Image.open(buf).convert("RGB")

    box_w  = _BOX_X2 - _BOX_X1
    box_h  = _BOX_Y2 - _BOX_Y1
    pad    = int(min(box_w, box_h) * 0.10)
    qr_size = min(box_w - 2 * pad, box_h - 2 * pad)

    canvas = Image.open(_TEMPLATE_PATH).convert("RGB")
    canvas.paste(
        qr_img.resize((qr_size, qr_size), Image.LANCZOS),
        (_BOX_X1 + (box_w - qr_size) // 2, _BOX_Y1 + (box_h - qr_size) // 2),
    )

    draw = ImageDraw.Draw(canvas)

    if tree_number.strip():
        zone_h = _NUM_Y2 - _NUM_Y1
        _fit_and_draw(
            draw, tree_number.strip(),
            cx=_CX, cy=(_NUM_Y1 + _NUM_Y2) // 2,
            max_w=int(canvas.width * 0.55), max_h=int(zone_h * 0.70),
            start_size=int(zone_h * 0.55),
            color=_TEXT_COLOR,
        )

    if tree_name.strip():
        zone_h    = _NAME_Y2 - _NAME_Y1
        name_font = _DEVA_FONT if _has_devanagari(tree_name) else _SERIF_FONT
        _fit_and_draw(
            draw, tree_name.strip(),
            cx=_CX, cy=(_NAME_Y1 + _NAME_Y2) // 2,
            max_w=int(canvas.width * 0.62), max_h=int(zone_h * 0.70),
            start_size=int(zone_h * 0.65),
            color=_TEXT_COLOR,
            font_path=name_font,
        )

    return canvas


def _img_to_bytes(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


def process_csv(
    csv_bytes: bytes, base_url: str, fmt: str,
) -> bytes:
    """Generate one QR image per CSV row; return a ZIP of all images."""
    ext      = "jpg" if fmt == "JPEG" else "png"
    base_url = base_url.rstrip("/")
    out_buf  = io.BytesIO()

    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))

    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for row in reader:
            s_no       = row["S_No_"].strip()
            vernacular = row["Vernacular"].strip()
            tree_name  = _english_from_vernacular(vernacular)
            url        = f"{base_url}/{s_no}.pdf"
            img        = make_qr_on_template2(url, tree_name, s_no)
            zout.writestr(f"{s_no}.{ext}", _img_to_bytes(img, fmt))

    out_buf.seek(0)
    return out_buf.read()


# ── PDF generation ────────────────────────────────────────────────────────────

def _load_header_img(width: int) -> Image.Image:
    img    = Image.open(_HEADER_PATH).convert("RGB")
    aspect = img.height / img.width
    return img.resize((width, int(width * aspect)), Image.LANCZOS)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        w, _, _, _ = _measure(draw, test, font)
        if w <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _split_script_runs(text: str) -> list[tuple[str, bool]]:
    """Split text into (segment, is_devanagari) runs so each can use its own font."""
    if not text:
        return [("", False)]
    runs: list[tuple[str, bool]] = []
    current = text[0]
    current_deva = 'ऀ' <= text[0] <= 'ॿ'
    for ch in text[1:]:
        is_deva = 'ऀ' <= ch <= 'ॿ'
        if is_deva == current_deva:
            current += ch
        else:
            runs.append((current, current_deva))
            current = ch
            current_deva = is_deva
    runs.append((current, current_deva))
    return runs


def _measure_mixed(
    draw: ImageDraw.ImageDraw,
    text: str,
    deva_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
) -> tuple[int, int]:
    total_w = max_h = 0
    for seg, is_deva in _split_script_runs(text):
        w, h, _, _ = _measure(draw, seg, deva_font if is_deva else latin_font)
        total_w += w
        max_h = max(max_h, h)
    return total_w, max_h


def _wrap_text_mixed(
    draw: ImageDraw.ImageDraw,
    text: str,
    deva_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
    max_w: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        w, _ = _measure_mixed(draw, test, deva_font, latin_font)
        if w <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _draw_mixed_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int, baseline_y: int,
    deva_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
    color: str,
) -> None:
    cx = x
    for seg, is_deva in _split_script_runs(text):
        font = deva_font if is_deva else latin_font
        draw.text((cx, baseline_y), seg, fill=color, font=font, anchor="ls")
        cx += int(draw.textlength(seg, font=font))


def _render_table(row: dict, width: int) -> Image.Image:
    LABEL_W  = int(width * 0.18)
    VAL_W    = width - LABEL_W
    PAD      = 7
    FONT_SZ  = max(14, int(width * 0.0132))
    BORDER   = "#333333"
    LABEL_BG = "#a8b5af"

    label_font = _get_font(FONT_SZ, _TABLE_FONT)
    deva_font  = _get_font(FONT_SZ, _DEVA_FONT)
    latin_font = _get_font(FONT_SZ, _SERIF_FONT)

    probe      = Image.new("RGB", (width, 50))
    probe_draw = ImageDraw.Draw(probe)

    deva_ascent,  deva_descent  = deva_font.getmetrics()
    latin_ascent, latin_descent = latin_font.getmetrics()
    line_ascent  = max(deva_ascent,  latin_ascent)
    line_descent = max(deva_descent, latin_descent)
    lh = line_ascent + line_descent

    row_data: list[tuple[int, list[str]]] = []
    for col_key, _ in _TABLE_ROWS:
        val   = row.get(col_key, "")
        lines = _wrap_text_mixed(probe_draw, val, deva_font, latin_font, VAL_W - 2 * PAD)
        h     = max(lh * len(lines) + 2 * PAD, 35)
        row_data.append((h, lines))

    total_h = sum(h for h, _ in row_data) + 2

    tbl  = Image.new("RGB", (width, total_h), "white")
    draw = ImageDraw.Draw(tbl)

    y = 0
    for (col_key, col_label), (rh, val_lines) in zip(_TABLE_ROWS, row_data):
        draw.rectangle([0, y, LABEL_W - 1, y + rh - 1], fill=LABEL_BG)
        lw, ll_h, lox, loy = _measure(draw, col_label, label_font)
        draw.text((PAD, y + (rh - ll_h) // 2 - loy), col_label, fill="#1a1a1a", font=label_font)

        total_text_h = lh * len(val_lines)
        ty = y + (rh - total_text_h) // 2
        for line in val_lines:
            _draw_mixed_line(draw, line, LABEL_W + PAD, ty + line_ascent, deva_font, latin_font, "#1a1a1a")
            ty += lh

        draw.line([(0, y), (width - 1, y)], fill=BORDER, width=1)
        y += rh

    draw.line([(0, total_h - 1), (width - 1, total_h - 1)], fill=BORDER, width=1)
    draw.line([(0, 0),           (0, total_h - 1)],          fill=BORDER, width=2)
    draw.line([(width - 1, 0),   (width - 1, total_h - 1)],  fill=BORDER, width=2)
    draw.line([(LABEL_W, 0),     (LABEL_W, total_h - 1)],    fill=BORDER, width=1)

    return tbl


def _load_footer_img(width: int) -> Image.Image:
    img = Image.open(_FOOTER_PATH).convert("RGB")
    img = img.crop((0, 155, img.width, img.height))
    aspect = img.height / img.width
    return img.resize((width, int(width * aspect)), Image.LANCZOS)


def _pdf_to_images(pdf_bytes: bytes, width: int) -> list[Image.Image]:
    doc    = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        scale = width / page.rect.width
        mat   = fitz.Matrix(scale, scale)
        pix   = page.get_pixmap(matrix=mat, alpha=False)
        img   = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # Crop "X | Page" footer strip from the bottom of each page
        footer_crop = int(img.height * 0.07)
        img = img.crop((0, 0, img.width, img.height - footer_crop))
        images.append(img)
    doc.close()
    return images


def build_tree_pdf(pdf_bytes: bytes, row: dict) -> bytes:
    width  = _PAGE_W
    margin = 80
    tbl    = _render_table(row, width - 2 * margin)
    tbl_canvas = Image.new("RGB", (width, tbl.height), "white")
    tbl_canvas.paste(tbl, (margin, 0))
    spacer = Image.new("RGB", (width, 12), "white")
    footer = _load_footer_img(width)
    parts  = (
        [_load_header_img(width), spacer]
        + [tbl_canvas]
        + _pdf_to_images(pdf_bytes, width)
    )

    body_h  = sum(p.height for p in parts)
    total_h = body_h + footer.height - 5
    canvas  = Image.new("RGB", (width, total_h), "white")
    y = 0
    for p in parts:
        canvas.paste(p, (0, y))
        y += p.height
    canvas.paste(footer, (0, body_h - 5))

    buf = io.BytesIO()
    canvas.save(buf, format="PDF", resolution=150)
    buf.seek(0)
    return buf.read()


def process_pdf_zip(zip_bytes: bytes, csv_bytes: bytes) -> bytes:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    rows   = {r["S_No_"].strip(): r for r in reader}

    in_zip  = zipfile.ZipFile(io.BytesIO(zip_bytes))
    out_buf = io.BytesIO()

    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for name in sorted(in_zip.namelist()):
            if name.endswith("/"):
                continue
            s_no = Path(name).stem
            if s_no not in rows:
                continue
            out_zip.writestr(f"{s_no}.pdf", build_tree_pdf(in_zip.read(name), rows[s_no]))

    out_buf.seek(0)
    return out_buf.read()


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Tree QR & PDF Generator", page_icon="🌿", layout="centered")
st.title("Tree QR & PDF Generator")

mode = st.radio("Mode", ["QR Generation", "PDF Generation"], horizontal=True)

with st.form("main_form"):
    if mode == "QR Generation":
        base_url = st.text_input("Base URL *", placeholder="https://example.com/docs")
        upload   = st.file_uploader("CSV file *", type=["csv"])
        st.caption("Tree number and name are read automatically from `S_No_` and `Vernacular` columns.")
        fmt    = st.radio("Output format", ["PNG", "JPG"], horizontal=True)
        csv_up = None
        zip_up = None
    else:
        csv_up   = st.file_uploader("CSV file *", type=["csv"])
        zip_up   = st.file_uploader("PDF ZIP *", type=["zip"])
        st.caption("Each PDF in the ZIP must be named `<S_No_>.pdf` to match CSV rows.")
        base_url = ""
        fmt      = "PNG"
        upload   = None

    go = st.form_submit_button("Generate", use_container_width=True, type="primary")

if go:
    errors: list[str] = []
    if mode == "QR Generation":
        if not base_url.strip():
            errors.append("Base URL is required.")
        if upload is None:
            errors.append("Please upload a CSV file.")
    else:
        if csv_up is None:
            errors.append("Please upload a CSV file.")
        if zip_up is None:
            errors.append("Please upload a ZIP of PDFs.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Generating…"):
            if mode == "QR Generation":
                save_fmt = "JPEG" if fmt == "JPG" else "PNG"
                result   = process_csv(upload.read(), base_url.strip(), save_fmt)
                st.success("Done!")
                st.download_button(
                    "Download QR Codes ZIP",
                    data=result,
                    file_name="qr_codes.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
            else:
                result = process_pdf_zip(zip_up.read(), csv_up.read())
                st.success("Done!")
                st.download_button(
                    "Download Modified PDFs ZIP",
                    data=result,
                    file_name="tree_pdfs.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
