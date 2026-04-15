#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drug Search - 药物信息搜索工具
从多个数据源获取药物信息：UniProt、PubMed、ClinicalTrials.gov
结合 pubmed-fetcher 下载全文 PDF 分析半衰期
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
LITERATURE_DIR = Path(__file__).parent.parent / "pubmed-fetcher" / "literature"
EMAIL = "lele@example.com"

# HTTP 头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ========== UniProt 搜索 ==========
def search_uniprot(drug_name):
    print(f"🔍 搜索 UniProt: {drug_name}")
    url = f"https://rest.uniprot.org/uniprotkb/search?query={quote(drug_name)}&format=json&size=10"
    
    info = {"found": False, "entries": []}
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                info["found"] = True
                for entry in results[:3]:
                    entry_info = {}
                    protein = entry.get("proteinDescription", {})
                    rec_name = protein.get("recommendedName", {})
                    if rec_name:
                        entry_info["name"] = rec_name.get("fullName", {}).get("value", "")
                    genes = entry.get("genes", [])
                    if genes:
                        entry_info["gene_name"] = genes[0].get("geneName", {}).get("value", "")
                    seq = entry.get("sequence", {})
                    if seq:
                        entry_info["length"] = seq.get("length", 0)
                        entry_info["mass_da"] = seq.get("molWeight", 0)
                        seq_value = seq.get("value", "")
                        if len(seq_value) > 400:
                            entry_info["sequence"] = seq_value[:200] + "..." + seq_value[-200:]
                            entry_info["sequence_truncated"] = True
                        else:
                            entry_info["sequence"] = seq_value
                    organism = entry.get("organism", {})
                    if organism:
                        entry_info["organism"] = organism.get("scientificName", "")
                    entry_info["accession"] = entry.get("primaryAccession", "")
                    info["entries"].append(entry_info)
                print(f"   ✅ 找到 {len(info['entries'])} 个蛋白质/抗体")
    except Exception as e:
        print(f"   ⚠️ UniProt 搜索失败: {e}")
    return info

# ========== ClinicalTrials.gov ==========
def search_clinicaltrials(drug_name, max_results=5):
    print(f"🔍 搜索 ClinicalTrials.gov: {drug_name}")
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {"query.term": drug_name, "pageSize": max_results, "format": "json"}
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
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    query = f"{drug_name}[Title/Abstract]"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json", "email": EMAIL, "sort": "relevance"}
    print(f"🔍 搜索 PubMed: {drug_name}")
    response = requests.get(base_url, params=params)
    data = response.json()
    pmids = data.get("esearchresult", {}).get("idlist", [])
    print(f"   找到 {len(pmids)} 篇相关文献")
    return pmids

def fetch_pubmed_details(pmids):
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

# ========== PK 数据提取 ==========
def get_pubmed_pk_data(pmids):
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
                abstract_text = ""
                for abst in article.findall('.//AbstractText'):
                    if abst.text:
                        abstract_text += abst.text + " "
                if not abstract_text:
                    continue
                # 半衰期
                for pattern in [r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)', r't1/2\s*[=:]?\s*(\d+\.?\d*)\s*(weeks?|w)', r'half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)', r'elimination\s*half.?life\s*[=:]?\s*(\d+\.?\d*)\s*(days?|d)']:
                    match = re.search(pattern, abstract_text, re.IGNORECASE)
                    if match and "half_life" not in pk_data:
                        pk_data["half_life"] = {"value": f"{match.group(1)} {match.group(2)}", "pmid": pmid}
                        break
                # 清除率
                cl_match = re.search(r'clearance\s*[=:]?\s*(\d+\.?\d*)\s*(mL/min|L/h)', abstract_text, re.IGNORECASE)
                if cl_match and "clearance" not in pk_data:
                    pk_data["clearance"] = {"value": f"{cl_match.group(1)} {cl_match.group(2)}", "pmid": pmid}
                # 生物利用度
                f_match = re.search(r'bioavailability\s*[=:]?\s*(\d+\.?\d*)\s*%', abstract_text, re.IGNORECASE)
                if f_match and "bioavailability" not in pk_data:
                    pk_data["bioavailability"] = {"value": f"{f_match.group(1)}%", "pmid": pmid}
    except Exception as e:
        print(f"   ⚠️ PK 数据提取失败: {e}")
    return [{"type": k, "value": v["value"], "source_pmid": v["pmid"]} for k, v in pk_data.items()]

# ========== PDF 下载 ==========
def download_pmc_pdf(pmcid, save_path):
    if not pmcid:
        return False, "No PMC ID"
    
    try:
        # 先访问文章页面获取 PDF 链接
        article_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
        article_resp = requests.get(article_url, headers=HEADERS, timeout=30)
        
        if article_resp.status_code != 200:
            return False, f"Page status: {article_resp.status_code}"
        
        # 检查是否被 reCAPTCHA 拦截
        if 'recaptcha' in article_resp.text.lower():
            return False, "Blocked by reCAPTCHA"
        
        # 查找 PDF 链接
        pdf_patterns = [
            r'href="(/pmc/articles/[^/]+/pdf/[^\"]+)"',
            r'href="(pdf/[^\"]+\.pdf)"',
        ]
        
        pdf_url = None
        for pattern in pdf_patterns:
            matches = re.findall(pattern, article_resp.text)
            if matches:
                pdf_link = matches[0]
                if pdf_link.startswith('/'):
                    pdf_url = "https://www.ncbi.nlm.nih.gov" + pdf_link
                else:
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/{pdf_link}"
                break
        
        if not pdf_url:
            return False, "No PDF link found on page"
        
        # 下载 PDF
        pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
        
        if pdf_resp.status_code == 200 and len(pdf_resp.content) > 5000:
            with open(save_path, "wb") as f:
                f.write(pdf_resp.content)
            return True, f"Downloaded {len(pdf_resp.content)} bytes"
        else:
            return False, f"Status: {pdf_resp.status_code}, Size: {len(pdf_resp.content)}"
            
    except Exception as e:
        return False, str(e)

def search_and_download_pk_pdfs(drug_name, articles, literature_dir):
    print("\n📥 下载 PubMed Open Access 文献 PDF...")
    drug_lit_dir = literature_dir / drug_name.lower().replace(" ", "_")
    drug_lit_dir.mkdir(parents=True, exist_ok=True)
    articles_with_pmc = [a for a in articles if a.get('pmcid')]
    if not articles_with_pmc:
        print("   ⚠️ 没有可下载的 Open Access 文献")
        return []
    downloaded = []
    for article in articles_with_pmc[:15]:
        pmcid = article.get('pmcid')
        pmid = article.get('pmid')
        title = article.get('title', 'unknown')[:50]
        pdf_files = list(drug_lit_dir.glob(f"*{pmid}*.pdf"))
        if pdf_files:
            downloaded.append({"pmid": pmid, "pmcid": pmcid, "status": "exists"})
            continue
        print(f"   📥 下载: {title}... (PMID: {pmid})")
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', article.get('title', ''))[:80]
        pdf_filename = f"{pmid}_{safe_title}.pdf"
        pdf_path = drug_lit_dir / pdf_filename
        success, msg = download_pmc_pdf(pmcid, pdf_path)
        if success:
            downloaded.append({"pmid": pmid, "pmcid": pmcid, "title": article.get('title'), "file": str(pdf_path), "status": "downloaded"})
            print(f"      ✅ 成功")
        else:
            downloaded.append({"pmid": pmid, "pmcid": pmcid, "status": "failed", "error": msg})
            print(f"      ⚠️ {msg}")
        time.sleep(0.5)
    success_count = len([d for d in downloaded if d.get('status') == 'downloaded'])
    print(f"   ✅ 成功下载 {success_count} 篇，保存到: {drug_lit_dir}")
    return downloaded

# ========== 主函数 ==========
def search_drug(drug_name, count=30, drugs_dir=DRUGS_DIR, download_pdfs=True):
    print(f"\n{'='*60}")
    print(f"💊 搜索药物: {drug_name}")
    print(f"{'='*60}")
    drug_dir = drugs_dir / drug_name.lower().replace(" ", "_")
    drug_dir.mkdir(exist_ok=True)
    result = {"drug_name": drug_name, "search_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    
    # 1. UniProt
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
    else:
        print("   ⚠️ 未找到 UniProt 信息")
    
    # 2. ClinicalTrials
    print("\n🏥 搜索临床试验...")
    trials = search_clinicaltrials(drug_name)
    if trials:
        result["clinical_trials"] = trials
        print(f"   ✅ 找到 {len(trials)} 个临床试验")
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
            print("   ⚠️ 摘要中未找到 PK 数据")
        
        # 5. 下载 PDF
        if download_pdfs:
            print("\n📥 下载 Open Access 文献全文...")
            downloaded = search_and_download_pk_pdfs(drug_name, articles, LITERATURE_DIR)
            if downloaded:
                result["downloaded_articles"] = downloaded
                success_count = len([d for d in downloaded if d.get('status') == 'downloaded'])
                print(f"   ✅ 已下载 {success_count} 篇 PDF")
    
    # 保存结果
    result_file = drug_dir / "info.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存到: {result_file}")
    print_summary(result)
    return result

def print_summary(result):
    print(f"\n{'='*60}")
    print(f"📊 搜索结果摘要")
    print(f"{'='*60}")
    print(f"\n💊 药物: {result['drug_name']}")
    if "uniprot" in result and result["uniprot"].get("found"):
        for entry in result["uniprot"].get("entries", [])[:1]:
            print(f"\n🧬 蛋白质信息:")
            if entry.get("name"):
                print(f"   名称: {entry['name']}")
            if entry.get("mass_da"):
                print(f"   分子量: {entry['mass_da']:,} Da ({entry['mass_da']/1000:.1f} kDa)")
            if entry.get("length"):
                print(f"   氨基酸: {entry['length']} aa")
    if "pharmacokinetics" in result and result["pharmacokinetics"]:
        print(f"\n📈 药代动力学数据:")
        for pk in result["pharmacokinetics"]:
            print(f"   {pk['type']}: {pk['value']}")
    if "articles" in result:
        print(f"\n📚 PubMed 文献 ({len(result['articles'])} 篇):")
        for i, art in enumerate(result["articles"][:5], 1):
            print(f"   {i}. {art['title'][:60]}...")
            print(f"      PMID: {art['pmid']}, PMCID: {art.get('pmcid', 'N/A')}")
    if "downloaded_articles" in result:
        dl = result["downloaded_articles"]
        success = len([d for d in dl if d.get('status') == 'downloaded'])
        print(f"\n📥 已下载 {success} 篇 PDF 全文")

def interactive_mode():
    print("\n" + "="*60)
    print("💊 Drug Search - 药物信息搜索工具 (含 PDF 下载)")
    print("="*60)
    drug_name = input("\n🔑 请输入药物名称: ").strip()
    if not drug_name:
        print("⚠️ 未输入药物名称")
        return
    search_drug(drug_name)

def main():
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