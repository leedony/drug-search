# SKILL.md - Drug Search

## 用途

搜索药物信息，包括药代动力学数据、相关文献和临床试验信息。

## 触发方式

用户提到以下关键词时使用：
- "药物搜索"
- "drug search"
- "药物信息"
- "查一下 [药物名]"
- "搜索药物"

## 使用方式

### 1. 克隆仓库（首次使用）

```bash
git clone https://github.com/leedony/drug-search.git
cd drug-search
pip install -r requirements.txt
```

### 2. 运行

```bash
# 交互式（推荐）
python drug_search.py

# 命令行模式
python drug_search.py ustekinumab
python drug_search.py denosumab -n 20
```

## 输出

- 药物基本信息（类型、靶点等）
- 药代动力学数据（半衰期、清除率等）
- PubMed 相关文献列表
- 保存到 `drugs/[药物名]/info.json`

## 示例输出

搜索 `garadacimab` 会返回：
- PubMed 文献（9篇，包括 PK/PD 研究）
- 相关临床试验信息

## 数据来源

- **PubMed**: 文献检索和摘要
- **UniProt**: 蛋白质/抗体信息
- **ClinicalTrials.gov**: 临床试验信息

## 注意事项

- 药代动力学数据从 PubMed 摘要中提取，可能不完整
- DrugBank 因反爬措施需要认证，优先使用其他来源
- 建议使用精确的药物名称以获得更准确的结果