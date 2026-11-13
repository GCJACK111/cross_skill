# 横向 SKILL

从多篇论文中归纳研究思路，围绕研究目的建立连续的 Introduction 论证，并生成完整 PDF。

## 最简使用

把仓库链接与多篇论文原文或文献解读一起发给具备网页读取和文件生成功能的 GPT：

```text
请按照 https://github.com/GCJACK111/cross_skill 中的 skill 分析这些论文。
```

可以补充研究目的或希望采用的组织方向，例如“空间—时空—动态时空”。没有这些提示时，skill 从这批材料的共同问题归纳主线，仍会完成 Introduction 写法思路。

支持原生 skills 的客户端也可将整个仓库放进 skills 目录，重新加载后调用 `purpose-driven-introduction`。仓库链接用于读取指令，PDF 的实际创建由当前会话的文件生成工具执行。

## 输出内容与顺序

回复与 PDF 正文只保留三个部分：

1. **研究思路覆盖率分布图**：根据本批文献计算，显示每种思路的篇数、比例与分母 N。
2. **Introduction 完整写法思路**：先给一句话主线，再逐段写出主题句、展开论证、对应文献与过渡句，从背景和核心问题一直写到具体剩余问题及本文工作。
3. **主要分布与思路边界**：说明图中各类的实际机制、已有答案、适用条件及与研究目的相关的边界。

PDF 包含同样的三部分，随本轮修改同步更新。证据矩阵、关键句提取、科学问题综合和方向推演在内部完成，不另设可见章节或附录。辅助源文件默认留在内部。

## Introduction 怎样保持连续

段落围绕一个共同问题组织。每次从 A 推进到 B，都解释 A 已回答什么、当前研究目的还要求回答什么、B 新增什么考虑。并列路线先分别回答共同问题，再说明它们如何汇合。段落数与层次数由材料决定，图中每类不必各占一段。

用户指定组织方向时，依据文献方法事实解释各层含义。例如时间输入、时变输出、固定图上的序列处理和关系随条件更新，需要分别核对。最接近当前目的的研究进入关键转折，已有能力成为定位下一步问题的依据。

自身方法尚未提供时，末段只留一句具体占位；摘要中的参考论文目标归属于参考论文，不替代用户自己的目标。

If a sentence serves only to preempt criticism rather than advance the argument, delete it.

## 内部工作流程

```text
多篇论文或解读
  → 去重、还原方法链、定位证据
  → 建立文献 × 思路矩阵、计算覆盖率、绘图
  → 综合已有答案、剩余问题与路线联系
  → 组织 Introduction 的完整写法
  → 按三部分顺序生成 PDF
```

[角色契约](agents/README.md)定义内部分析职责；需要比较候选收束点时使用研究方向推演。运行环境不支持独立子智能体时，由主智能体按相同契约执行。

## 统计口径

覆盖率 = 实际采用该思路的独立论文数 ÷ 纳入统计的独立论文数 N × 100%。

同一论文的原文、总结和重复版本合并。编号不连续时按实际材料计数；综述及外围材料的处理在图注交代。一篇可归入多列，比例之和可超过 100%。内部矩阵使用 `1 / 0 / ? / R` 表示采用、未归入、信息不足和综述归纳。低覆盖率本身不构成研究缺口。

## 配套文件

- [主 SKILL.md](SKILL.md)：入口、证据规则、连续论证与三部分交付要求。
- [输出模板](references/output-template.md)：三部分内容及段内写法。
- [报告 JSON 结构](references/report-spec.md)：将同一内容排入 PDF。
- [绘图脚本](scripts/plot_distribution.py)：由同一份统计生成 PNG、矢量 PDF、PGFPlots 源。
- [报告脚本](scripts/build_report.py)：论文样式 DOCX → PDF。
- [参考资源](assets/README.md)：仅演示图形样式，虚构数值不参与统计。

脚本供能够执行代码的助手使用，用户无需手动运行：

```bash
pip install -r scripts/requirements.txt
python scripts/plot_distribution.py coverage.json figure.png --format all
python scripts/build_report.py report.json -o report.docx --pdf
```

报告沿用 A4、宋体五号、1.5 倍行距、首行缩进与页脚页码。转换器支持 LibreOffice Kit（`--kit-cli` / `--kit-node`）或系统 `soffice`。交付前确认 PDF 文件真实存在并检查排版。

当前修订：2.1.0，三部分输出。变更见 [CHANGELOG.md](CHANGELOG.md)。
