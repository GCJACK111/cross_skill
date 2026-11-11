#!/usr/bin/env python3
"""Draw the research-approach coverage figure in academic (LaTeX-like) style.

Input JSON
----------
{
  "title": "研究思路覆盖率",
  "sample_size": 23,
  "approaches": [
    {"name": "思路 A", "count": 15},
    {"name": "思路 B", "count": 8}
  ]
}

Outputs
-------
Any combination of:

* ``png``  — raster, for embedding in DOCX/Word or slides;
* ``pdf``  — vector, the paper-ready figure;
* ``tex``  — standalone PGFPlots/TikZ source, the LaTeX figure itself.

Usage
-----
    python plot_distribution.py coverage.json figure.png
    python plot_distribution.py coverage.json figure.pdf --format pdf,tex
    python plot_distribution.py coverage.json figure.png --format all --dpi 600

Percentage = papers using the approach / sample_size.  One paper may cover
several approaches, so the values do not have to sum to 100%.  The value is
descriptive for this sample only: it is not an innovation probability.

The figure follows journal conventions: serif type, thin rules, no grid, no
top/right spines, one hue whose lightness encodes magnitude.
"""

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

# matplotlib is imported lazily: writing only the .tex source must not require it.
_MPL = {}


def _mpl():
    """Import matplotlib on first use and reuse the module handles."""
    if not _MPL:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        from matplotlib.colors import to_rgb
        _MPL.update(plt=plt, font_manager=font_manager, to_rgb=to_rgb)
    return _MPL

# Latin serif first, then CJK serif fallbacks.  Matplotlib falls back per
# glyph, so a missing CJK face in the first entries is harmless.
LATIN_SERIF = ["Times New Roman", "Nimbus Roman", "TeX Gyre Termes", "DejaVu Serif"]
CJK_SERIF = [
    "Songti SC", "STSong", "Noto Serif CJK SC", "Source Han Serif SC",
    "SimSun", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
]
BASE_COLOR = "#2f4f6f"  # single academic blue-grey hue


def installed_fonts():
    return {f.name for f in _mpl()["font_manager"].fontManager.ttflist}


def configure_style():
    """Apply a neutral, print-oriented style; warn once if no CJK face exists."""
    plt = _mpl()["plt"]
    names = installed_fonts()
    cjk = next((n for n in CJK_SERIF if n in names), None)
    if cjk is None:
        print(
            "warning: 未找到可用的中文字体，中文可能显示为方框。"
            "可安装 Noto Serif CJK SC / 思源宋体，或在 JSON 中改用拉丁标题。",
            file=sys.stderr,
        )
    # Use just one Latin and one CJK face: a longer list only produces
    # weight-resolution warnings without improving glyph coverage.
    latin = next((f for f in LATIN_SERIF if f in names), "DejaVu Serif")
    families = [latin] + ([cjk] if cjk else [])
    plt.rcParams.update({
        # A concrete family list (not the "serif" alias) is what enables
        # matplotlib's per-glyph fallback, so Latin gets Times and CJK gets Songti.
        "font.family": families,
        "font.serif": families,
        "mathtext.fontset": "cm",
        "axes.linewidth": 0.6,
        "axes.edgecolor": "#1a1a1a",
        "axes.labelcolor": "#1a1a1a",
        "axes.labelsize": 9,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 3.0,
        "ytick.major.size": 0,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "xtick.color": "#1a1a1a",
        "ytick.color": "#1a1a1a",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 200,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def shade(base, t):
    """Blend ``base`` toward white; t=1 is the full colour, t=0 is near white."""
    r, g, b = _mpl()["to_rgb"](base)
    return (r + (1 - t) * (1 - r), g + (1 - t) * (1 - g), b + (1 - t) * (1 - b))


def wrap_label(text, width):
    """Wrap long approach names so they cannot collide with the bars."""
    if len(text) <= width:
        return text
    return textwrap.fill(text, width=width, break_long_words=True)


def resolve_title(raw_title, sample_size):
    """Append ``（N = x）`` only when the caller has not already stated N."""
    raw_title = (raw_title or "研究思路覆盖率").strip()
    match = re.search(r"[NＮ]\s*[=＝]\s*(\d+)", raw_title)
    if match:
        declared = int(match.group(1))
        if declared != sample_size:
            raise ValueError(
                f"标题中的 N={declared} 与 sample_size={sample_size} 不一致"
            )
        return raw_title
    return f"{raw_title}（N = {sample_size}）"


def validate(data):
    sample_size = int(data["sample_size"])
    approaches = data.get("approaches") or []
    if sample_size <= 0:
        raise ValueError("sample_size 必须大于 0")
    if not approaches:
        raise ValueError("approaches 不能为空")
    for item in approaches:
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("每个 approach 都需要非空 name")
        count = int(item["count"])
        if count < 0 or count > sample_size:
            raise ValueError(f"{name} 的 count={count} 超出 0..{sample_size}")
    return sample_size, approaches


def escape_latex(text):
    """Escape the characters that are special inside LaTeX text mode."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def ordered(data, sort_desc):
    sample_size, approaches = validate(data)
    names = [str(i["name"]).strip() for i in approaches]
    counts = [int(i["count"]) for i in approaches]
    if sort_desc:
        order = sorted(range(len(counts)), key=lambda i: (-counts[i], names[i]))
        names = [names[i] for i in order]
        counts = [counts[i] for i in order]
    coverage = [c / sample_size * 100 for c in counts]
    title = resolve_title(data.get("title", "研究思路覆盖率"), sample_size)
    return sample_size, title, names, counts, coverage


def build_figure(data, sort_desc=True, footnote=False, xmax_mode="100"):
    """Build the matplotlib figure and return it with its resolved data."""
    sample_size, title, names, counts, coverage = ordered(data, sort_desc)

    configure_style()
    plt = _mpl()["plt"]
    n = len(names)
    fig, ax = plt.subplots(figsize=(5.6, 1.05 + 0.62 * n))

    peak = max(coverage) if coverage else 1.0
    colors = [shade(BASE_COLOR, 0.32 + 0.68 * (v / peak)) for v in coverage]
    y = list(range(n))
    bars = ax.barh(y, coverage, color=colors, height=0.56,
                   edgecolor="#1f3347", linewidth=0.45, zorder=2)

    ax.set_yticks(y)
    ax.set_yticklabels([wrap_label(name, 16) for name in names], linespacing=1.35)
    ax.set_ylim(n - 0.55, -0.55)

    top = 100.0
    if xmax_mode == "auto":
        top = max(10.0, min(100.0, (peak * 1.45 // 10 + 1) * 10))
    ax.set_xlim(0, top)
    ax.set_xlabel("覆盖率（%）")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.0f}")
    ax.set_axisbelow(True)

    for bar, value, count in zip(bars, coverage, counts):
        ax.text(min(value + top * 0.018, top * 0.955),
                bar.get_y() + bar.get_height() / 2,
                f"{value:.0f}% ({count})", va="center", ha="left", fontsize=8)

    ax.set_title(title, loc="left", fontsize=10, fontweight="bold", pad=8)

    if footnote:
        fig.text(
            0.01, 0.01,
            "覆盖率 = 采用该思路的论文数 / 独立论文总数；一篇可覆盖多条思路，比例不要求和为 100%。",
            fontsize=7, color="#5a5a5a", ha="left",
        )
        fig.tight_layout(rect=(0, 0.06, 1, 1))
    else:
        fig.tight_layout()

    return fig, sample_size, title, names, counts, coverage


def write_pgfplots(path, title, sample_size, names, counts, coverage):
    """Emit a standalone PGFPlots document (compile with xelatex)."""
    height = max(4.2, 1.8 + 0.62 * len(names))

    def sym(name):
        # pgfplots splits symbolic coordinates on commas; use the CJK comma and
        # a tie for spaces so the entry stays a single token in both places.
        return escape_latex(name).replace(",", "，").replace(" ", "~")

    symbolic = ", ".join(sym(n) for n in names)
    # point meta is explicit symbolic: each coordinate carries its printed label.
    coords = "\n".join(
        f"    ({cov:.1f},{sym(n)}) [{cov:.0f}\\% ({count})]"
        for n, cov, count in zip(names, coverage, counts)
    )

    template = r"""% Generated by purpose-driven-introduction/scripts/plot_distribution.py
% Compile with:  xelatex thisfile.tex
% Chinese labels need the ctex package; drop it for pure-Latin labels.
\documentclass[tikz,border=3pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage{ctex}
\begin{document}
\begin{tikzpicture}
\begin{axis}[
  xbar,
  xmin=0, xmax=100,
  width=11cm, height=__HEIGHT__cm,
  symbolic y coords={__SYMBOLIC__},
  ytick=data,
  y dir=reverse,
  bar width=9pt,
  xlabel={覆盖率（\%）},
  title={__TITLE__},
  point meta=explicit symbolic,
  nodes near coords,
  nodes near coords align={horizontal},
  every node near coord/.append style={font=\scriptsize, anchor=west},
  tick label style={font=\small},
  label style={font=\small},
  title style={font=\small\bfseries},
  axis line style={line width=0.5pt},
  tick style={line width=0.5pt},
  major tick length=2pt,
  ytick style={draw=none},
  enlarge y limits=0.12,
  xmajorgrids=false,
  ymajorgrids=false,
]
\addplot+[fill=black!22, draw=black!55, line width=0.4pt]
  coordinates {
__COORDS__
  };
\end{axis}
\end{tikzpicture}
\end{document}
"""
    body = (
        template
        .replace("__HEIGHT__", f"{height:.1f}")
        .replace("__SYMBOLIC__", symbolic)
        .replace("__TITLE__", escape_latex(title))
        .replace("__COORDS__", coords)
    )
    path.write_text(body, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="绘制研究思路覆盖率图（LaTeX 风格；可输出 PNG、矢量 PDF 与 PGFPlots 源）"
    )
    parser.add_argument("input", type=Path, help="思路统计 JSON 文件")
    parser.add_argument("output", type=Path, help="输出文件；扩展名决定默认格式")
    parser.add_argument(
        "--format", default=None,
        help="png,pdf,tex 的任意组合，或 all；默认按 output 扩展名输出一种",
    )
    parser.add_argument("--dpi", type=int, default=600, help="PNG 分辨率，默认 600")
    parser.add_argument("--no-sort", action="store_true", help="保持 JSON 顺序，不按篇数降序")
    parser.add_argument("--footnote", action="store_true",
                        help="在图下加一行统计口径说明（论文正文通常由图注承担）")
    parser.add_argument("--xmax", choices=["100", "auto"], default="100",
                        help="横轴上限；默认固定 100 便于跨批次比较")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))

    formats = (args.format or args.output.suffix.lstrip(".") or "png").lower().split(",")
    if "all" in formats:
        formats = ["png", "pdf", "tex"]
    unknown = set(formats) - {"png", "pdf", "tex"}
    if unknown:
        parser.error(f"不支持的格式：{', '.join(sorted(unknown))}")

    stem = args.output.with_suffix("")

    if {"png", "pdf"} & set(formats):
        fig, sample_size, title, names, counts, coverage = build_figure(
            data, not args.no_sort, args.footnote, args.xmax
        )
        if "png" in formats:
            png_path = stem.with_suffix(".png")
            fig.savefig(png_path, dpi=args.dpi, bbox_inches="tight", facecolor="white")
            print(f"wrote {png_path}")
        if "pdf" in formats:
            pdf_path = stem.with_suffix(".pdf")
            fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
            print(f"wrote {pdf_path}")
        _mpl()["plt"].close(fig)
    else:
        sample_size, title, names, counts, coverage = ordered(data, not args.no_sort)

    if "tex" in formats:
        tex_path = stem.with_suffix(".tex")
        write_pgfplots(tex_path, title, sample_size, names, counts, coverage)
        print(f"wrote {tex_path}（用 xelatex 编译）")


if __name__ == "__main__":
    main()
