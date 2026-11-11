# 报告 JSON 结构

`scripts/build_report.py` 读取这份 JSON，输出论文样式的 DOCX；加 `--pdf` 时再转成 PDF。内容与版式分离：作者只写文字，版式由脚本固定。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 报告标题，居中 17 pt 加粗 |
| `subtitle` | 否 | 副标题，居中灰色 |
| `meta` | 否 | 字符串数组，逐行居中小字，写材料路径、日期、口径等 |
| `sections` | 是 | 章节数组，按顺序渲染 |

## section 类型

`type` 省略时按 `bullets` 处理。

| type | 字段 | 渲染效果 |
|---|---|---|
| `bullets` | `heading?`, `items` | 圆点列表，悬挂缩进 |
| `paragraphs` | `heading?`, `items` | 正文，首行缩进 2 字，两端对齐，1.5 倍行距 |
| `figure` | `image`, `caption?`, `width_cm?` | 居中插图（默认 15 cm），图注在下 |
| `table` | `header`, `rows`, `caption?`, `widths?`, `font_size?`, `align?` | 三线表，表注在上，长表换页重复表头 |
| `note` | `items` | 灰色小字说明 |
| `pagebreak` | — | 强制分页 |

`heading` 存在时先输出标题。`level: 2` 输出二级标题（11 pt），否则一级标题（13 pt）。

## 文本内联标记

- `**文本**` 渲染为加粗。
- `\n` 渲染为单元格或段落内换行。

## 完整示例

```json
{
  "title": "城市建筑表面光伏潜力评估：23 篇文献横向综合",
  "subtitle": "purpose-driven-introduction 横向 skill 交付",
  "meta": ["材料：/path/to/papers", "生成日期：2026-11-11"],
  "sections": [
    {"heading": "1  材料范围与统计口径", "items": [
      "**独立论文数 N = 23**。编号 01–08、10–24，缺 09。",
      "覆盖率 = 该路线取 1 的论文数 ÷ N。"
    ]},
    {"heading": "2  研究思路分布", "type": "figure",
     "image": "01-思路覆盖率分布.png",
     "caption": "图 1  研究思路覆盖率分布（N = 23）",
     "width_cm": 15},
    {"heading": "3  解读", "type": "paragraphs", "items": ["……"]},
    {"heading": "4  矩阵", "type": "table",
     "caption": "表 1  文献 × 研究思路（1 = 采用；0 = 未归入；R = 综述）",
     "header": ["编号", "文献", "路线 A"],
     "rows": [["01", "Zhuang 2025", "1"]],
     "widths": [1.0, 4.5, 1.2],
     "font_size": 7.5,
     "align": "l"}
  ]
}
```

## 版式约定

- A4，四边 2.5 cm 页边距，可用宽度 16 cm。
- 正文宋体五号（10.5 pt），标题黑体；西文统一 Times New Roman。
- 三线表：顶线 1 pt、表头下边线 0.75 pt、底线 1 pt，无竖线。
- 图注、表注 9 pt 居中；表格正文默认 8.5 pt，宽表可降到 7 pt。
- 页脚居中页码。

## 常见问题

- **表格跨页把表题留在上一页**：表题已设 `keep_with_next`，若仍发生，给表格前加 `pagebreak`。
- **最后一页只有一行空白**：说明末尾有多余空段。脚本已不再在表后补空段，若自查发现，检查 `sections` 末尾是否多了一个空 `paragraphs`。
- **PDF 没有生成**：`build_report.py` 会说明找不到转换器；此时 DOCX 仍可用 Word/WPS 手工导出。
