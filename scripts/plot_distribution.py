#!/usr/bin/env python3
"""Generate a research-approach coverage chart from a JSON evidence summary.

Input JSON:
{
  "title": "研究思路覆盖率",
  "sample_size": 20,
  "approaches": [
    {"name": "思路 A", "count": 15},
    {"name": "思路 B", "count": 12}
  ]
}

This script calculates descriptive coverage (count / sample_size), not the
probability that an approach is innovative. One paper may cover multiple
approaches, so percentages need not sum to 100%.
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


def configure_chinese_font():
    candidates = [
        "PingFang SC", "Hiragino Sans GB", "Heiti SC", "Songti SC",
        "Noto Sans CJK SC", "Source Han Sans SC", "Arial Unicode MS",
    ]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def main():
    parser = argparse.ArgumentParser(description="绘制论文研究思路覆盖率图")
    parser.add_argument("input", type=Path, help="思路统计 JSON 文件")
    parser.add_argument("output", type=Path, help="输出 PNG 文件")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    sample_size = int(data["sample_size"])
    approaches = data["approaches"]
    if sample_size <= 0 or not approaches:
        raise ValueError("sample_size 必须大于 0，approaches 不能为空")

    names = [item["name"] for item in approaches]
    counts = [int(item["count"]) for item in approaches]
    if any(count < 0 or count > sample_size for count in counts):
        raise ValueError("每个 count 必须介于 0 和 sample_size 之间")
    coverage = [count / sample_size * 100 for count in counts]

    configure_chinese_font()
    fig_height = max(3.6, 1.1 + 0.62 * len(approaches))
    fig, ax = plt.subplots(figsize=(10, fig_height), dpi=180)
    colors = ["#376A9F" if value >= 50 else "#86B9B0" if value >= 25 else "#D7A55B" for value in coverage]
    bars = ax.barh(names, coverage, color=colors, height=0.58)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("覆盖率（采用该思路的论文数 / 独立论文总数）")
    ax.set_title(f"{data.get('title', '研究思路覆盖率')}（N = {sample_size}）", loc="left", fontsize=16, fontweight="bold")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.0f}%")
    ax.grid(axis="x", alpha=0.18)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)

    for bar, value, count in zip(bars, coverage, counts):
        ax.text(min(value + 1.5, 94), bar.get_y() + bar.get_height() / 2,
                f"{value:.0f}%（{count} 篇）", va="center", fontsize=10)

    fig.text(0.125, 0.015, "说明：覆盖率描述本批论文的思路分布；一篇论文可覆盖多种思路，比例不要求合计为 100%。", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
