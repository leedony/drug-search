# 💊 Drug Search - 药物信息搜索工具

自动搜索药物信息、药代动力学数据和 PubMed 相关文献。

## ✨ 功能

- 🔍 从 PubMed 搜索药物相关文献
- 📊 提取药代动力学数据（半衰期、清除率等）
- 📚 获取药物相关临床试验信息
- 💾 本地保存搜索结果

## 📦 安装

```bash
git clone https://github.com/leedony/drug-search.git
cd drug-search
pip install -r requirements.txt
```

## 🚀 使用

### 交互式
```bash
python drug_search.py
```

### 命令行
```bash
python drug_search.py ustekinumab
python drug_search.py denosumab -n 20
python drug_search.py "garadacimab" -n 10
```

## 📁 输出

结果保存在 `drugs/[药物名]/info.json`：

```json
{
  "drug_name": "garadacimab",
  "articles": [...],
  "pharmacokinetics": [...]
}
```

## 📋 示例

测试药物：
- `ustekinumab` - IL-12/23 抗体
- `denosumab` - RANKL 抗体
- `garadacimab` - FXII 抗体

## 数据来源

- PubMed 文献和摘要
- UniProt 蛋白质数据库
- ClinicalTrials.gov

## ⚠️ 注意

- 药代动力学数据从论文摘要提取，可能不完整
- 建议使用精确药物名称
- 部分药物可能无 PubMed 全文