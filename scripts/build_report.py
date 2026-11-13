#!/usr/bin/env python3
"""Build a paper-styled report (DOCX) and convert it to PDF.

The report is described by a small JSON spec so the analysis content stays in
one place and the layout stays reproducible.

Spec
----
{
  "title": "城市建筑太阳能潜力评估文献综合",
  "sections": [
    {"heading": "1  研究思路覆盖率分布图", "type": "figure",
     "image": "figure.png", "caption": "图 1  研究思路覆盖率分布（N = 20）", "width_cm": 15},
    {"heading": "2  Introduction 完整写法思路", "type": "paragraphs",
     "items": ["主线与逐段主题句、展开论证、文献依据及过渡句。"]},
    {"heading": "3  主要分布与思路边界", "type": "paragraphs", "items": ["..."]}
  ]
}

Section ``type`` defaults to ``bullets``.  Supported: bullets, paragraphs,
figure, table, note, pagebreak.

Usage
-----
    python build_report.py report.json -o report.docx          # DOCX only
    python build_report.py report.json -o report.docx --pdf     # DOCX + PDF
    python build_report.py report.json -o report.docx --pdf --keep-docx

PDF conversion prefers the bundled LibreOffice Kit CLI (``--kit-cli`` /
``--kit-node``, or the ``DSH_LIBREOFFICE_KIT_CLI`` / ``DSH_LIBREOFFICE_KIT_NODE``
environment variables) and falls back to a system ``soffice``.  If no converter
is found the DOCX is kept and the limitation is reported -- never a silent loss.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BODY_EA = "宋体"
HEAD_EA = "黑体"
LATIN = "Times New Roman"
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x55, 0x55, 0x55)


# --------------------------------------------------------------------------- #
# low-level typography helpers
# --------------------------------------------------------------------------- #
def style_run(run, size=10.5, bold=False, italic=False, color=INK,
              latin=LATIN, east=BODY_EA):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = latin
    run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), east)


def add_rich_text(paragraph, text, size=10.5, color=INK, base_bold=False):
    """Render ``**bold**`` spans and ``\\n`` breaks; everything else is body face."""
    for line_index, line in enumerate(str(text).split("\n")):
        if line_index:
            paragraph.add_run().add_break()
        chunks = line.split("**")
        for index, chunk in enumerate(chunks):
            if not chunk:
                continue
            run = paragraph.add_run(chunk)
            style_run(run, size=size, bold=(base_bold or index % 2 == 1), color=color)


def add_paragraph(doc, text, size=10.5, first_line_indent=True, space_after=6,
                  align=WD_ALIGN_PARAGRAPH.JUSTIFY, color=INK, line_spacing=1.5):
    paragraph = doc.add_paragraph()
    paragraph.alignment = align
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = line_spacing
    if first_line_indent:
        fmt.first_line_indent = Pt(size * 2)
    add_rich_text(paragraph, text, size=size, color=color)
    return paragraph


def add_heading(doc, text, level=1):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.keep_with_next = True
    if level == 1:
        fmt.space_before = Pt(16)
        fmt.space_after = Pt(6)
        size = 13
    else:
        fmt.space_before = Pt(10)
        fmt.space_after = Pt(4)
        size = 11
    run = paragraph.add_run(text)
    style_run(run, size=size, bold=True, east=HEAD_EA)
    return paragraph


def add_bullet(doc, text, size=10.5):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.left_indent = Pt(size * 2)
    fmt.first_line_indent = Pt(-size)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(3)
    fmt.line_spacing = 1.45
    bullet = paragraph.add_run("· ")
    style_run(bullet, size=size)
    add_rich_text(paragraph, text, size=size)
    return paragraph


def add_caption(doc, text, size=9, before=4, after=10, keep_with_next=False):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = 1.2
    fmt.keep_with_next = keep_with_next
    add_rich_text(paragraph, text, size=size, color=INK)
    return paragraph


def add_note(doc, text, size=8.5):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(6)
    fmt.line_spacing = 1.3
    add_rich_text(paragraph, text, size=size, color=MUTED)
    return paragraph


def add_figure(doc, image, caption, width_cm=15.0):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(8)
    fmt.space_after = Pt(2)
    fmt.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(image), width=Cm(width_cm))
    if caption:
        add_caption(doc, caption)


# --------------------------------------------------------------------------- #
# three-line table (booktabs look)
# --------------------------------------------------------------------------- #
def _border(el_name, size):
    element = OxmlElement(f"w:{el_name}")
    if size:
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:color"), "000000")
    else:
        element.set(qn("w:val"), "none")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:color"), "auto")
    return element


def apply_three_line_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    borders.append(_border("top", 8))
    borders.append(_border("bottom", 8))
    for edge in ("left", "right", "insideH", "insideV"):
        borders.append(_border(edge, 0))
    tbl_pr.append(borders)

    for cell in table.rows[0].cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        tc_borders = OxmlElement("w:tcBorders")
        tc_borders.append(_border("bottom", 6))
        tc_pr.append(tc_borders)

    header_row = table.rows[0]._tr
    tr_pr = header_row.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    tr_pr.append(repeat)


def set_cell_margins(table, left=0.08, right=0.08, top=0.04, bottom=0.04):
    """Tighten padding so dense tables can hold more columns or rows."""
    tbl_pr = table._tbl.tblPr
    margins = OxmlElement("w:tblCellMar")
    for side, value in (("top", top), ("left", left),
                        ("bottom", bottom), ("right", right)):
        element = OxmlElement(f"w:{side}")
        element.set(qn("w:w"), str(int(value * 567)))
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    tbl_pr.append(margins)


def add_table(doc, header, rows, caption=None, font_size=8.5, widths=None,
              align="c", usable_cm=16.0):
    if caption:
        add_caption(doc, caption, size=9, before=10, after=4, keep_with_next=True)

    table = doc.add_table(rows=1, cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Column widths: explicit, else proportional to the longest cell text.
    if widths is None:
        lengths = []
        for index in range(len(header)):
            column = [str(header[index])] + [str(row[index]) for row in rows]
            lengths.append(max(len(text) for text in column))
        total = sum(lengths) or 1
        widths = [usable_cm * length / total for length in lengths]
        widths = [max(1.4, width) for width in widths]
        scale = usable_cm / sum(widths)
        widths = [width * scale for width in widths]

    for index, title in enumerate(header):
        cell = table.rows[0].cells[index]
        cell.width = Cm(widths[index])
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(3)
        paragraph.paragraph_format.space_after = Pt(3)
        run = paragraph.add_run(str(title))
        style_run(run, size=font_size, bold=True, east=HEAD_EA)

    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cell = cells[index]
            cell.width = Cm(widths[index])
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(2)
            paragraph.paragraph_format.space_after = Pt(2)
            paragraph.paragraph_format.line_spacing = 1.0
            text = str(value)
            if align == "l" and index <= 1:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_rich_text(paragraph, text, size=font_size)

    # Keep every row intact; long tables break between rows, never inside one.
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))

    apply_three_line_borders(table)
    set_cell_margins(table)
    # No trailing spacer paragraph: as the last element it can spill onto a
    # blank page.  The next caption's space_before already separates blocks.
    return table


# --------------------------------------------------------------------------- #
# document scaffolding
# --------------------------------------------------------------------------- #
def add_page_number_footer(section):
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    style_run(run, size=9, color=MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def setup_document():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    add_page_number_footer(section)

    normal = doc.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_EA)
    return doc


def build(spec, output, resolve_paths=True):
    doc = setup_document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(6)
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run(spec.get("title", "横向综合报告"))
    style_run(run, size=17, bold=True, east=HEAD_EA)

    if spec.get("subtitle"):
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.paragraph_format.space_after = Pt(2)
        run = subtitle.add_run(spec["subtitle"])
        style_run(run, size=10.5, color=MUTED)

    for line in spec.get("meta", []):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(1)
        paragraph.paragraph_format.line_spacing = 1.25
        run = paragraph.add_run(line)
        style_run(run, size=8.5, color=MUTED)

    rule = doc.add_paragraph()
    rule.paragraph_format.space_before = Pt(8)
    rule.paragraph_format.space_after = Pt(12)
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")
    borders.append(bottom)
    rule._p.get_or_add_pPr().append(borders)

    for position, item in enumerate(spec.get("sections", [])):
        kind = item.get("type", "bullets")
        if kind == "pagebreak":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            continue
        if item.get("heading"):
            add_heading(doc, item["heading"], item.get("level", 1))
        if kind == "bullets":
            for text in item.get("items", []):
                add_bullet(doc, text)
        elif kind == "paragraphs":
            for text in item.get("items", []):
                add_paragraph(doc, text)
        elif kind == "figure":
            image = Path(item["image"])
            if resolve_paths and not image.is_absolute():
                image = (output.parent / image).resolve()
            if image.exists():
                add_figure(doc, image, item.get("caption", ""), item.get("width_cm", 15.0))
            else:
                add_note(doc, f"[缺少图片：{image}]")
        elif kind == "table":
            add_table(doc, item["header"], item["rows"],
                      caption=item.get("caption"), font_size=item.get("font_size", 8.5),
                      widths=item.get("widths"), align=item.get("align", "c"))
            # Separate the table from what follows, but never leave a dangling
            # paragraph at the end of the document (it can spill to a blank page).
            if position < len(spec["sections"]) - 1:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.space_before = Pt(0)
                spacer.paragraph_format.space_after = Pt(0)
                spacer.paragraph_format.line_spacing = 1.0
                style_run(spacer.add_run(""), size=6)
        elif kind == "note":
            for text in item.get("items", []):
                add_note(doc, text)
        else:
            raise ValueError(f"未知的 section 类型：{kind}")

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return output


# --------------------------------------------------------------------------- #
# PDF conversion
# --------------------------------------------------------------------------- #
def _kit_candidates():
    """Common locations of the bundled LibreOffice Kit CLI, without user paths."""
    home = Path.home()
    patterns = [
        "/Applications/DeepSeek Harness.app/Contents/Resources/app.asar.unpacked/"
        "dsh/node_modules/@deepseek-ai/libreoffice-kit/lib/cli.js",
        "/opt/DeepSeek Harness/resources/app.asar.unpacked/"
        "dsh/node_modules/@deepseek-ai/libreoffice-kit/lib/cli.js",
    ]
    patterns += [
        str(p) for p in home.glob(
            ".dsh/dsh-runtimes/*/dependencies/node_modules/"
            "@deepseek-ai/libreoffice-kit/lib/cli.js")
    ]
    return patterns


def _node_candidates():
    home = Path.home()
    found = [shutil.which("node") or ""]
    found += [str(p) for p in home.glob(
        ".dsh/dsh-runtimes/*/dependencies/node/bin/node")]
    return [p for p in found if p and Path(p).exists()]


def find_converter(kit_cli=None, kit_node=None):
    """Return ('kit', node, cli), ('soffice', path, None) or (None, None, None)."""
    cli = kit_cli or os.environ.get("DSH_LIBREOFFICE_KIT_CLI")
    node = kit_node or os.environ.get("DSH_LIBREOFFICE_KIT_NODE")

    if not cli:
        cli = next((p for p in _kit_candidates() if Path(p).exists()), None)
    if cli and not node:
        node = next(iter(_node_candidates()), None)
    if cli and node:
        return ("kit", node, cli)

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        return ("soffice", soffice, None)
    return (None, None, None)


def convert_to_pdf(docx_path, pdf_path, kit_cli=None, kit_node=None):
    kind, first, second = find_converter(kit_cli, kit_node)
    if kind is None:
        print(
            "warning: 未找到 PDF 转换器，已保留 DOCX。"
            "可安装 LibreOffice，或通过 --kit-cli/--kit-node 指定能力。",
            file=sys.stderr,
        )
        return None
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # The kit refuses to overwrite an existing output file.
    if pdf_path.is_file():
        pdf_path.unlink()
    if kind == "kit":
        command = [first, second, "convert", "--input", str(docx_path),
                   "--output", str(pdf_path)]
    else:
        command = [first, "--headless", "--convert-to", "pdf", "--outdir",
                   str(pdf_path.parent), str(docx_path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: PDF 转换失败：{result.stderr.strip()[:400]}", file=sys.stderr)
        return None
    if kind == "soffice":
        produced = pdf_path.parent / (docx_path.stem + ".pdf")
        if produced != pdf_path and produced.exists():
            produced.replace(pdf_path)
    if not pdf_path.exists():
        print("warning: 转换命令返回成功但未生成 PDF。", file=sys.stderr)
        return None
    with pdf_path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            print("warning: 输出文件不是有效 PDF。", file=sys.stderr)
            return None
    return pdf_path


def main():
    parser = argparse.ArgumentParser(description="生成论文样式报告，并转换为 PDF")
    parser.add_argument("spec", type=Path, help="报告 JSON 描述文件")
    parser.add_argument("-o", "--output", type=Path, required=True, help="输出 DOCX 路径")
    parser.add_argument("--pdf", action="store_true", help="同时转换为 PDF")
    parser.add_argument("--kit-cli", default=None, help="LibreOffice Kit CLI 路径")
    parser.add_argument("--kit-node", default=None, help="运行 Kit 的 Node 可执行文件")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    output = args.output.resolve()
    build(spec, output, resolve_paths=True)
    print(f"wrote {output}")

    if args.pdf:
        pdf_path = output.with_suffix(".pdf")
        produced = convert_to_pdf(output, pdf_path, args.kit_cli, args.kit_node)
        if produced:
            print(f"wrote {produced}")
        else:
            print("DOCX 已保留，供手工导出 PDF。", file=sys.stderr)


if __name__ == "__main__":
    main()
