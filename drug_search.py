#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drug Search - 药物信息搜索工具
从多个数据源获取药物信息：UniProt、PubMed、ClinicalTrials.gov
重点：分子量、序列、半衰期等药代动力学数据
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from urllib.parse import quote
import re
import xml.etree.ElementTree as ET

# Windows UTF-8 支持
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 配置 ==========
DEFAULT_COUNT = 30
DRUGS_DIR = Path(__file__).parent / "drugs"
EMAIL = "lele@example.com"

# ========== UniProt 搜索 ==========
def search_uniprot(drug_name):
    """从 UniProt 获取蛋白质/抗体信息"""
    print(f"🔍 搜索 UniProt: {drug_name}")
    
    url = f"https://rest.uniprot.org/uniprotkb/search?query={quote(drug_name)}&format=json&size=10"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    info = {"found": False, "entries": []}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                info["found"] = True
                
                for entry in results[:3]:
                    entry_info = {}
                    
                    # 蛋白质名称
                    protein = entry.get("proteinDescription", {})
                    rec_name = protein.get("recommendedName", {})
                    if rec_name:
                        entry_info["name"] = rec_name.get("fullName", {}).get("value", "")
                    
                    # 基因名
                    genes = entry.get("genes", [])
                    if genes:
                        entry_info["gene_name"] = genes[0].get("geneName", {}).get("value", "")
                    
                    # 氨基酸序列
                    seq = entry.get("sequence", {})
                    if seq:
                        entry_info["length"] = seq.get("length", 0)
                        entry_info["mass_da"] = seq.get("molWeight", 0)
                        seq_value = seq.get("value", "")
                        # 序列太长，截取前200和后200
                        if len(seq_value) > 400:
                            entry_info["sequence"] = seq_value[:200] + "..." + seq_value[-200:]
                            entry_info["sequence_truncated"] = True
                        else:
                            entry_info["sequence"] = seq_value
                    
                    # 物种
                    organism = entry.get("organism", {})
                    if organism:
                        entry_info["organism"] = organism.get("scientificName", "")
                    
                    entry_info["accession"] = entry.get("primaryAccession", "")
                    
                    info["entries"].append(entry_info)
                
                print(f"   ✅ 找到 {len(info['entries'])} 个蛋白质/抗体")
                
    except Exception as e:
        print(f"   ⚠️ UniProt 搜索失败: {e}")
    
    return info


# ========== ClinicalTrials.gov 搜索 ==========
def search_clinicaltrials(drug_name, max_results=5):
    """从 ClinicalTrials.gov 获取临床试验信息"""
    print(f"🔍 搜索 ClinicalTrials.gov: {drug_name}")
    
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": drug_name,
        "pageSize": max_results,
        "format": "json"
    }
    
    trials = []
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            studies = data.get("studies", [])
            
            for study in studies:
                protocol = study.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                status = protocol.get("statusModule", {})
                
                trial_info = {
                    "nct_id": ident.get("nctId", ""),
                    "title": ident.get("briefTitle", ""),
                    "status": status.get("overallStatus", ""),
                    "phase": ident.get("phases", [])
                }
                trials.append(trial_info)
            
            print(f"   ✅ 找到 {len(trials)} 个临床试验")
            
    except Exception as e:
        print(f"   ⚠️ ClinicalTrials 搜索失败: {e}")
    
    return trials


# ========== PubMed 搜索 ==========
def search_pubmed(drug_name, max_results=50):
    """搜索 PubMed"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    # 搜索药物 + 药理学关键词
    query = f"{drug_name}[Title/Abstract]"
    
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "email": EMAIL,
        "sort": "relevance"
    }
    
    print(f"🔍 搜索 PubMed: {drug_name}")
    response = requests.get(base_url, params=params)
    data = response.json()
    
    pmids = data.get("esearchresult", {}).get("idlist", [])
    print(f"   找到 {len(pmids)} 篇相关文献")
    
    return pmids


def fetch_pubmed_details(pmids):
    """获取 PubMed 文章元数据"""
    if not pmids:
        return []
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    pmid_str = ",".join(pmids[:200])
    
    params = {"db": "pubmed", "id": pmid_str, "retmode": "json", "email": EMAIL}
    response = requests.get(base_url, params=params)
    data = response.json()
    
    result = data.get("result", {})
    articles = []
    
    for pmid in pmids:
        if pmid in result:
            info = result[pmid]
            # 提取 PMC ID
            pmcid = ""
            for aid in info.get("articleids", []):
                if aid.get("idtype") == "pmc":
                    pmcid = aid.get("value", "")
                    break
            
            authors = [a.get("name", "") for a in info.get("authors", [])[:5]]
            
            articles.append({
                "pmid": pmid,
                "pmcid": pmcid,
                "title": info.get("title", "Unknown"),
                "authors": authors,
                "journal": info.get("fulljournalname", ""),
                "pubdate": info.get("pubdate", ""),
                "doi": info.get("elocationid", "").replace("doi: ", "")
            })
    
    return articles


# ========== PK 数据提取（重点改进半衰期）==========
def get_pubmed_pk_data(pmids):
    """从 PubMed 摘要中提取药代动力学数据"""
    if not pmids:
        return []
    
    pmid_str = ",".join(pmids[:20])
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid_str}&retmode=xml&email={EMAIL}"
    
    pk_data = {}
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            for article in root.findall('.//PubmedArticle'):
                pmid_elem = article.find('.//PMID')
                pmid = pmid_elem.text if pmid_elem is not None else ""
                
                # 获取摘要
                abstract_text = ""
                for abst in article.findall('.//AbstractText'):
                    if abst.text:
                        abstract_text += abst.text + " "
                
                if not abstract_text:
                    continue
                
                # 半衰期提取（多种格式）
                half_life_patterns = [
                    r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)',
                    r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(weeks?|w)',
                    r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(hours?|h)',
                    r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(min|m)',
                    r'half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)',
                    r'half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(weeks?|w)',
                    r'half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(hours?|h)',
                    r'elimination\s*half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)',
                    r'elimination\s*half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(weeks?|w)',
                ]
                
                for pattern in half_life_patterns:
                    match = re.search(pattern, abstract_text, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        unit = match.group(2)
                        hl_key = f"{value} {unit}"
                        if "half_life" not in pk_data:
                            pk_data["half_life"] = {"value": hl_key, "pmid": pmid}
                        break
                
                # 清除率
                cl_patterns = [
                    r'clearance\s*[=:]?\s*(\d+\.?\d*)\s*(mL/min|L/h)',
                    r'total\s*clearance\s*[=:]?\s*(\d+\.?\d*)\s*(mL/min|L/h)',
                ]
                for pattern in cl_patterns:
                    match = re.search(pattern, abstract_text, re.IGNORECASE)
                    if match:
                        if "clearance" not in pk_data:
                            pk_data["clearance"] = {"value": f"{match.group(1)} {match.group(2)}", "pmid": pmid}
                        break
                
                # 分布容积
                vd_patterns = [
                    r'volume\s*of\s*distribution\s*[=:]?\s*(\d+\.?\d*)\s*L/kg',
                    r'Vd\s*[=:]?\s*(\d+\.?\d*)\s*L/kg',
                ]
                for pattern in vd_patterns:
                    match = re.search(pattern, abstract_text, re.IGNORECASE)
                    if match:
                        if "volume_of_distribution" not in pk_data:
                            pk_data["volume_of_distribution"] = {"value": f"{match.group(1)} L/kg", "pmid": pmid}
                        break
                
                # 生物利用度
                f_patterns = [
                    r'bioavailability\s*[=:]?\s*(\d+\.?\d*)\s*%',
                    r'F\s*[=:]?\s*(\d+\.?\d*)\s*%',
                ]
                for pattern in f_patterns:
                    match = re.search(pattern, abstract_text, re.IGNORECASE)
                    if match:
                        if "bioavailability" not in pk_data:
                            pk_data["bioavailability"] = {"value": f"{match.group(1)}%", "pmid": pmid}
                        break
    
    except Exception as e:
        print(f"   ⚠️ PK 数据提取失败: {e}")
    
    # 转换为列表
    return [{"type": k, "value": v["value"], "source_pmid": v["pmid"]} for k, v in pk_data.items()]


def search_pk_literature(drug_name):
    """专门搜索药代动力学文献"""
    print("   🔬 深度搜索 PK 文献...")
    
    # 专门的 PK 搜索词
    pk_queries = [
        f"{drug_name}[Title/Abstract] AND (half-life OR half-life OR t1/2 OR pharmacokinetic)",
        f"{drug_name}[Title/Abstract] AND (elimination OR clearance OR bioavailability)"
    ]
    
    all_pk_data = {}
    
    for query in pk_queries:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": 10,
            "retmode": "json",
            "email": EMAIL,
            "sort": "relevance"
        }
        
        try:
            response = requests.get(base_url, params=params)
            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])[:5]
            
            if pmids:
                pk_data = get_pubmed_pk_data(pmids)
                for pk in pk_data:
                    key = pk["type"]
                    if key not in all_pk_data:
                        all_pk_data[key] = pk
                        
        except Exception as e:
            pass
        
        time.sleep(0.3)
    
    return [{"type": k, "value": v["value"], "source_pmid": v["source_pmid"]} for k, v in all_pk_data.items()]


# ========== 主函数 ==========
def search_drug(drug_name, count=30, drugs_dir=DRUGS_DIR):
    """搜索药物信息"""
    print(f"\n{'='*60}")
    print(f"💊 搜索药物: {drug_name}")
    print(f"{'='*60}")
    
    drug_dir = drugs_dir / drug_name.lower().replace(" ", "_")
    drug_dir.mkdir(exist_ok=True)
    
    result = {
        "drug_name": drug_name,
        "search_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 1. UniProt 信息
    print("\n🧬 获取蛋白质/抗体信息...")
    uniprot_info = search_uniprot(drug_name)
    
    if uniprot_info.get("found"):
        result["uniprot"] = uniprot_info
        for entry in uniprot_info.get("entries", []):
            print(f"   ✅ {entry.get('name', 'N/A')}")
            if entry.get('mass_da'):
                print(f"      分子量: {entry['mass_da']:,} Da ({entry['mass_da']/1000:.1f} kDa)")
            if entry.get('length'):
                print(f"      氨基酸长度: {entry['length']} aa")
            if entry.get('gene_name'):
                print(f"      基因名: {entry['gene_name']}")
            if entry.get('sequence') and not entry.get('sequence_truncated'):
                print(f"      序列: {entry['sequence'][:100]}...")
    else:
        print("   ⚠️ 未找到 UniProt 信息")
    
    # 2. ClinicalTrials
    print("\n🏥 搜索临床试验...")
    trials = search_clinicaltrials(drug_name)
    if trials:
        result["clinical_trials"] = trials
    else:
        print("   ⚠️ 未找到临床试验")
    
    # 3. PubMed 文献
    print("\n📚 搜索 PubMed 文献...")
    pmids = search_pubmed(drug_name, max_results=count)
    
    if pmids:
        articles = fetch_pubmed_details(pmids)
        result["articles"] = articles
        print(f"   ✅ 获取到 {len(articles)} 篇文献")
        
        # 4. PK 数据
        print("\n📊 提取药代动力学数据...")
        pk_data = get_pubmed_pk_data(pmids)
        
        if pk_data:
            result["pharmacokinetics"] = pk_data
            print(f"   ✅ 找到 {len(pk_data)} 条 PK 数据")
            for pk in pk_data:
                print(f"      - {pk['type']}: {pk['value']}")
        else:
            print("   ⚠️ 未找到 PK 数据，深度搜索...")
            pk_data = search_pk_literature(drug_name)
            if pk_data:
                result["pharmacokinetics"] = pk_data
                print(f"   ✅ 深度搜索找到 {len(pk_data)} 条 PK 数据")
                for pk in pk_data:
                    print(f"      - {pk['type']}: {pk['value']}")
    
    # 保存结果
    result_file = drug_dir / "info.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存到: {result_file}")
    print_summary(result)
    
    return result


def print_summary(result):
    """打印摘要"""
    print(f"\n{'='*60}")
    print(f"📊 搜索结果摘要")
    print(f"{'='*60}")
    
    print(f"\n💊 药物: {result['drug_name']}")
    
    # UniProt 信息
    if "uniprot" in result and result["uniprot"].get("found"):
        for entry in result["uniprot"].get("entries", [])[:1]:
            print(f"\n🧬 蛋白质信息:")
            if entry.get("name"):
                print(f"   名称: {entry['name']}")
            if entry.get("mass_da"):
                print(f"   分子量: {entry['mass_da']:,} Da ({entry['mass_da']/1000:.1f} kDa)")
            if entry.get("length"):
                print(f"   氨基酸: {entry['length']} aa")
            if entry.get("sequence") and not entry.get("sequence_truncated"):
                print(f"   序列: {entry['sequence'][:80]}...")
    
    # PK 数据
    if "pharmacokinetics" in result and result["pharmacokinetics"]:
        print(f"\n📈 药代动力学数据:")
        for pk in result["pharmacokinetics"]:
            print(f"   {pk['type']}: {pk['value']}")
    
    # 文献
    if "articles" in result:
        print(f"\n📚 PubMed 文献 ({len(result['articles'])} 篇):")
        for i, art in enumerate(result["articles"][:5], 1):
            print(f"   {i}. {art['title'][:60]}...")
            print(f"      PMID: {art['pmid']}, 年份: {art['pubdate'][:4]}")


def interactive_mode():
    """交互式模式"""
    print("\n" + "="*60)
    print("💊 Drug Search - 药物信息搜索工具")
    print("="*60)
    
    drug_name = input("\n🔑 请输入药物名称: ").strip()
    if not drug_name:
        print("⚠️ 未输入药物名称")
        return
    
    count_input = input(f"📊 搜索文献数量（默认 {DEFAULT_COUNT}）: ").strip()
    count = int(count_input) if count_input.isdigit() else DEFAULT_COUNT
    
    print(f"\n🚀 搜索药物: {drug_name}")
    search_drug(drug_name, count)


def main():
    """主入口"""
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        count = DEFAULT_COUNT
        
        if "-n" in args:
            idx = args.index("-n")
            if idx + 1 < len(args):
                try:
                    count = int(args[idx + 1])
                    args = args[:idx] + args[idx+2:]
                except:
                    pass
        
        drug_name = " ".join(args)
        
        if drug_name:
            search_drug(drug_name, count)
        else:
            interactive_mode()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
