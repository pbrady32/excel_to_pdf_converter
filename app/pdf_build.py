"""Dynamic PDF generation for client worksheets."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas


@dataclass
class Margins:
    left: float
    right: float
    top: float
    bottom: float


@dataclass
class Fonts:
    base: str
    bold: str
    title_size: int
    client_name_size: int
    item_text_size: int
    column_header_size: int


@dataclass
class RowLayout:
    row_height: float
    item_text_width: float
    textfield_width: float
    textfield_height: float
    gap_x: float
    checkbox_size: float


@dataclass
class LayoutConfig:
    year_label_template: str
    logo_path: str
    margins: Margins
    fonts: Fonts
    row_layout: RowLayout
    uploaded_label: str
    not_needed_label: str
    page_size: Sequence[float]


@dataclass
class OptionsConfig:
    choice_style: str
    prefix_mode: str
    auto_prefix: str
    radio_values: dict


@dataclass
class RowPositions:
    item_text_width: float
    gap_x: float
    textfield_x: float
    textfield_width: float
    uploaded_x: float
    not_needed_x: float


class PDFBuildError(Exception):
    """Raised when PDF generation fails."""


HEADER_COLOR = colors.HexColor("#712674")
TEXT_COLOR = colors.black
CHECKBOX_SPACING = 72.0
LOGO_MAX_HEIGHT = 60.0
LOGO_MAX_WIDTH = 60.0
MIN_ITEM_WIDTH = 170.0
MIN_TEXTFIELD_WIDTH = 210.0
TEXT_LINE_SPACING = 2.0
TEXT_TOP_PADDING = 18.0
TEXTFIELD_PADDING = 0.0
BOTTOM_PADDING = 12.0
COLUMN_LABEL_OFFSET = 8.0


def _build_layout(config: dict) -> LayoutConfig:
    margins = Margins(**config["margins"])
    fonts = Fonts(
        base=config["fonts"]["base"],
        bold=config["fonts"]["bold"],
        title_size=config["fonts"]["sizes"]["title"],
        client_name_size=config["fonts"]["sizes"]["client_name"],
        item_text_size=config["fonts"]["sizes"]["item_text"],
        column_header_size=config["fonts"]["sizes"]["column_header"],
    )
    row_layout = RowLayout(
        row_height=config["row_layout"]["row_height"],
        item_text_width=config["row_layout"]["item_text_width"],
        textfield_width=config["row_layout"]["textfield_width"],
        textfield_height=config["row_layout"]["textfield_height"],
        gap_x=config["row_layout"]["gap_x"],
        checkbox_size=config["columns"]["checkbox_size"],
    )
    page_size = letter if config.get("page_size", "LETTER").upper() == "LETTER" else tuple(config["page_size"])
    return LayoutConfig(
        year_label_template=config["year_label_template"],
        logo_path=config.get("logo_path", ""),
        margins=margins,
        fonts=fonts,
        row_layout=row_layout,
        uploaded_label=config["columns"]["uploaded_label"],
        not_needed_label=config["columns"]["not_needed_label"],
        page_size=page_size,
    )


def _build_options(config: dict) -> OptionsConfig:
    return OptionsConfig(
        choice_style=config.get("choice_style", "checkbox"),
        prefix_mode=config.get("prefix_mode", "auto"),
        auto_prefix=config.get("auto_prefix", ""),
        radio_values=config.get("radio_values", {}),
    )


def _prefix_item(text: str, options: OptionsConfig) -> str:
    normalized = text.strip()
    if options.prefix_mode == "verbatim":
        return normalized
    prefix = options.auto_prefix
    if not prefix:
        return normalized
    if normalized.lower().startswith(prefix.lower()):
        return normalized
    return f"{prefix}{normalized}"


def _draw_logo(c: canvas.Canvas, layout: LayoutConfig, page_width: float, header_bottom: float) -> None:
    if not layout.logo_path:
        return
    try:
        logo = ImageReader(layout.logo_path)
    except Exception:
        return
    width, height = logo.getSize()
    scale = min(LOGO_MAX_WIDTH / width, LOGO_MAX_HEIGHT / height, 1.0)
    draw_width = width * scale
    draw_height = height * scale
    x = page_width - 80.0
    y = header_bottom + draw_height
    c.drawImage(logo, x, y, width=draw_width, height=draw_height, mask="auto")


def _compute_row_positions(layout: LayoutConfig) -> RowPositions:
    page_width, _ = layout.page_size
    margins = layout.margins
    row = layout.row_layout

    not_needed_x = page_width - margins.right - row.checkbox_size
    uploaded_x = not_needed_x - CHECKBOX_SPACING
    textfield_right_limit = uploaded_x - 24.0

    textfield_x = margins.left
    textfield_width = textfield_right_limit - textfield_x
    if textfield_width < MIN_TEXTFIELD_WIDTH:
        raise PDFBuildError("Insufficient space for text field column")

    item_text_width = textfield_width

    return RowPositions(
        item_text_width=item_text_width,
        gap_x=0.0,
        textfield_x=textfield_x,
        textfield_width=textfield_width,
        uploaded_x=uploaded_x,
        not_needed_x=not_needed_x,
    )


def _draw_header(
    c: canvas.Canvas,
    layout: LayoutConfig,
    client_name: str,
    year_label: str,
    positions: RowPositions,
) -> float:
    page_width, page_height = layout.page_size
    margins = layout.margins

    header_height = 60.0
    header_bottom = page_height - margins.top - header_height

    c.setFillColor(HEADER_COLOR)
    c.rect(0, header_bottom, page_width-100, header_height, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont(layout.fonts.base, layout.fonts.title_size)
    c.drawString(margins.left, header_bottom + header_height - 42.0, year_label)

    _draw_logo(c, layout, page_width, header_bottom - header_height)

    c.setFillColor(TEXT_COLOR)
    c.setFont(layout.fonts.base, layout.fonts.client_name_size)
    c.drawString(margins.left, header_bottom - 26.0, client_name)

    if c.getPageNumber() == 1:
        c.setFont("Helvetica-Oblique", layout.fonts.item_text_size)
        instruction_text = "Please upload your documents and then mark the below checkbox as uploaded or not needed."
        c.drawString(margins.left, header_bottom - 46.0, instruction_text)

    column_y = header_bottom - 70.0
    c.setFont(layout.fonts.bold, layout.fonts.column_header_size)
    c.drawString(margins.left, column_y, "Document")

    checkbox_center = layout.row_layout.checkbox_size / 2.0
    uploaded_label_width = c.stringWidth(layout.uploaded_label, layout.fonts.bold, layout.fonts.column_header_size)
    uploaded_label_x = positions.uploaded_x + checkbox_center - uploaded_label_width / 2.0
    not_needed_label_width = c.stringWidth(layout.not_needed_label, layout.fonts.bold, layout.fonts.column_header_size)
    not_needed_label_x = positions.not_needed_x + checkbox_center - not_needed_label_width / 2.0
    c.drawString(uploaded_label_x, column_y, layout.uploaded_label)
    c.drawString(not_needed_label_x, column_y, layout.not_needed_label)

    return column_y - 16.0


def _prepare_item(
    item_text: str,
    layout: LayoutConfig,
    positions: RowPositions,
):
    lines = simpleSplit(
        item_text,
        layout.fonts.base,
        layout.fonts.item_text_size,
        positions.item_text_width,
    )
    if not lines:
        lines = [""]

    line_height = layout.fonts.item_text_size + TEXT_LINE_SPACING
    text_block_height = len(lines) * line_height

    row = layout.row_layout
    required_height = (
        TEXT_TOP_PADDING
        + text_block_height
        + TEXTFIELD_PADDING
        + row.textfield_height
        + BOTTOM_PADDING
    )
    row_height = max(row.row_height, required_height)
    return lines, row_height, line_height, text_block_height


def _draw_item(
    c: canvas.Canvas,
    layout: LayoutConfig,
    options: OptionsConfig,
    positions: RowPositions,
    lines,
    row_height: float,
    line_height: float,
    text_block_height: float,
    index: int,
    row_top: float,
) -> None:
    row = layout.row_layout

    text_y = row_top - TEXT_TOP_PADDING
    c.setFillColor(TEXT_COLOR)
    c.setFont(layout.fonts.base, layout.fonts.item_text_size)
    for line in lines:
        c.drawString(positions.textfield_x, text_y, line)
        text_y -= line_height

    textfield_y = (
        row_top
        - TEXT_TOP_PADDING
        - text_block_height
        - TEXTFIELD_PADDING
        - row.textfield_height
    )

    form = c.acroForm
    form.textfield(
        name=f"note_{index}",
        x=positions.textfield_x,
        y=textfield_y,
        width=positions.textfield_width,
        height=row.textfield_height,
        borderStyle="inset",
        borderColor=HEADER_COLOR,
        fillColor=colors.white,
        textColor=TEXT_COLOR,
        forceBorder=True,
    )

    checkbox_y = textfield_y + (row.textfield_height - row.checkbox_size) / 2.0
    if options.choice_style.lower() == "radio":
        uploaded_value = options.radio_values.get("uploaded", "uploaded")
        not_needed_value = options.radio_values.get("not_needed", "not_needed")
        form.radio(
            name=f"status_{index}",
            value=uploaded_value,
            x=positions.uploaded_x,
            y=checkbox_y,
            size=row.checkbox_size,
            selected=False,
            borderStyle="solid",
            borderColor=HEADER_COLOR,
        )
        form.radio(
            name=f"status_{index}",
            value=not_needed_value,
            x=positions.not_needed_x,
            y=checkbox_y,
            size=row.checkbox_size,
            selected=False,
            borderStyle="solid",
            borderColor=HEADER_COLOR,
        )
    else:
        form.checkbox(
            name=f"uploaded_{index}",
            x=positions.uploaded_x,
            y=checkbox_y,
            size=row.checkbox_size,
            borderStyle="solid",
            borderColor=HEADER_COLOR,
            fillColor=colors.white,
        )
        form.checkbox(
            name=f"notneeded_{index}",
            x=positions.not_needed_x,
            y=checkbox_y,
            size=row.checkbox_size,
            borderStyle="solid",
            borderColor=HEADER_COLOR,
            fillColor=colors.white,
        )


def _iter_items(items: Sequence[str], options: OptionsConfig):
    for idx, item in enumerate(items, start=1):
        yield idx, _prefix_item(item, options)


def build_pdf(client_name: str, items: Sequence[str], layout_cfg: dict, options_cfg: dict) -> Tuple[bytes, int]:
    """Generate a fillable PDF for the client worksheet."""

    if not items:
        raise PDFBuildError("No items to render")

    layout = _build_layout(layout_cfg)
    year_value = layout_cfg.get("tax_year")
    year_label = layout.year_label_template.format(year=year_value or "").strip()
    if not year_label:
        year_label = "Client Worksheet"
    options = _build_options(options_cfg)
    positions = _compute_row_positions(layout)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=layout.page_size)
    c.setTitle(f"Client Worksheet - {client_name}")

    margins = layout.margins
    row = layout.row_layout
    
    row_top = _draw_header(c, layout, client_name, year_label, positions)

    for index, item_text in _iter_items(items, options):
        lines, row_height, line_height, text_block_height = _prepare_item(
            item_text, layout, positions
        )
        if row_top - row_height < margins.bottom:
            c.showPage()
            row_top = _draw_header(c, layout, client_name, year_label, positions)
        _draw_item(
            c,
            layout,
            options,
            positions,
            lines,
            row_height,
            line_height,
            text_block_height,
            index,
            row_top,
        )
        row_top -= row_height

    page_count = c.getPageNumber()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes, page_count


__all__ = ["build_pdf", "PDFBuildError"]
