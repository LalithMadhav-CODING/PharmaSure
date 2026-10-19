#!/usr/bin/env python
"""Expand the PharmaSure corpus with real PubMed abstracts for many diseases.

For each target disease:
  1. Resolve it against the EveryCure disease lookup (MONDO id).
  2. Pull its top repurposing candidates from the pre-computed candidate map.
  3. Query PubMed for abstracts that mention the disease AND a candidate drug.
  4. Attribute each abstract to the drug it actually names.
  5. Emit passages in the corpus schema.

Run:  venv/bin/python scripts/build_corpus.py [--out data/pubmed_passages.json]
"""
import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# NCBI allows 3 req/sec without an API key; stay under it.
SLEEP = 0.40

# Diseases a reviewer is most likely to type. Kept broad on purpose: every entry
# that resolves in the KG gets literature, which is what makes scores non-zero.
TARGET_DISEASES = [
    # demo set
    "Alzheimer disease", "Parkinson disease", "Multiple myeloma", "Type 2 diabetes", "Asthma",
    # common infections
    "Common cold", "Influenza", "COVID-19", "Pneumonia", "Tuberculosis", "Malaria",
    "Dengue fever", "HIV infectious disease", "Hepatitis B", "Hepatitis C", "Sepsis",
    "Meningitis", "Urinary tract infection", "Sinusitis", "Bronchitis", "Otitis media",
    "Gastroenteritis", "Herpes simplex", "Candidiasis", "Measles", "Chickenpox",
    # cardiometabolic
    "Type 1 diabetes", "Obesity", "Hypertension", "Hyperlipidemia", "Atherosclerosis",
    "Heart failure", "Atrial fibrillation", "Stroke", "Myocardial infarction",
    "Chronic kidney disease", "Liver cirrhosis", "Gout", "Hypothyroidism", "Hyperthyroidism",
    "Anemia", "Deep vein thrombosis", "Pulmonary embolism",
    # neuro / psychiatric
    "Epilepsy", "Migraine", "Multiple sclerosis", "Depression", "Anxiety disorder",
    "Schizophrenia", "Bipolar disorder", "Insomnia", "Dementia", "Attention deficit hyperactivity disorder",
    "Autism", "Fibromyalgia", "Chronic fatigue syndrome", "Restless legs syndrome",
    # respiratory / immune
    "Chronic obstructive pulmonary disease", "Allergic rhinitis", "Cystic fibrosis",
    "Rheumatoid arthritis", "Osteoarthritis", "Osteoporosis", "Psoriasis", "Eczema",
    "Systemic lupus erythematosus", "Crohn disease", "Ulcerative colitis", "Celiac disease",
    "Irritable bowel syndrome", "Gastroesophageal reflux disease", "Peptic ulcer",
    "Sleep apnea",
    # oncology
    "Breast cancer", "Lung cancer", "Colorectal cancer", "Prostate cancer", "Leukemia",
    "Lymphoma", "Melanoma", "Pancreatic cancer", "Stomach cancer", "Cervical cancer",
    "Ovarian cancer", "Bladder cancer", "Thyroid cancer", "Liver cancer", "Kidney cancer",
    # eye / skin / reproductive
    "Glaucoma", "Cataract", "Macular degeneration", "Acne", "Alopecia", "Vitiligo",
    "Polycystic ovary syndrome", "Endometriosis", "Benign prostatic hyperplasia",
    "Erectile dysfunction",
    # blood / genetic
    "Sickle cell disease", "Hemophilia", "Thalassemia",
]


def load_json(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def normalize(text):
    return "".join(c for c in (text or "").lower() if c.isalnum() or c == " ").strip()


def build_resolver(diseases):
    """normalized name -> (mondo_id, canonical name)"""
    out = {}
    for did, info in diseases.items():
        norm = normalize(info.get("n", ""))
        if norm and norm not in out:
            out[norm] = (did, info.get("n", ""))
    return out


def resolve(query, resolver):
    q = normalize(query)
    if q in resolver:
        return resolver[q]
    matches = [(len(n), v) for n, v in resolver.items() if q and q in n]
    if matches:
        matches.sort(key=lambda x: x[0])
        return matches[0][1]
    return None


def esearch(term, retmax):
    r = httpx.get(
        f"{EUTILS}/esearch.fcgi",
        params={"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json",
                "sort": "relevance"},
        timeout=45,
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def efetch(pmids):
    if not pmids:
        return []
    r = httpx.get(
        f"{EUTILS}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
        timeout=90,
    )
    r.raise_for_status()
    return parse_articles(r.text)


def text_of(node, path):
    el = node.find(path)
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_articles(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = text_of(art, ".//PMID")
        title = text_of(art, ".//ArticleTitle")

        # Abstract may be split into labelled sections.
        chunks = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            body = "".join(ab.itertext()).strip()
            if body:
                chunks.append(f"{label}: {body}" if label else body)
        abstract = " ".join(chunks).strip()
        if not abstract:
            continue

        year = text_of(art, ".//JournalIssue/PubDate/Year") or \
               text_of(art, ".//JournalIssue/PubDate/MedlineDate")[:4]
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None

        types = [t.text for t in art.findall(".//PublicationType") if t.text]
        low = " ".join(types).lower()
        if "clinical trial" in low:
            pub_type = "clinical_trial"
        elif "randomized controlled trial" in low:
            pub_type = "clinical_trial"
        elif "review" in low:
            pub_type = "review"
        elif "meta-analysis" in low:
            pub_type = "meta_analysis"
        elif "case reports" in low:
            pub_type = "case_report"
        else:
            pub_type = "journal_article"

        out.append({
            "pmid": pmid,
            "title": title,
            "text": f"{title} {abstract}".strip(),
            "year": year,
            "pub_type": pub_type,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DATA, "pubmed_passages.json"))
    ap.add_argument("--per-drug", type=int, default=2, help="abstracts to keep per drug")
    ap.add_argument("--max-drugs", type=int, default=5, help="candidate drugs per disease")
    args = ap.parse_args()

    diseases = load_json("disease_lookup.json")
    candidates = load_json("candidates.json")
    drugs_lookup = load_json("drug_lookup.json")
    resolver = build_resolver(diseases)

    # Existing corpus -> reuse so we only pay for what is new.
    existing_path = args.out
    existing = []
    if os.path.exists(existing_path):
        with open(existing_path) as f:
            existing = json.load(f)
    seen_pmids = {p.get("pmid") for p in existing if p.get("pmid")}

    passages = list(existing)
    stats = {"resolved": 0, "unresolved": [], "fetched": 0, "skipped_dup": 0}

    for raw in TARGET_DISEASES:
        hit = resolve(raw, resolver)
        if not hit:
            stats["unresolved"].append(raw)
            print(f"  [skip] {raw}: not in KG")
            continue
        did, dname = hit
        stats["resolved"] += 1

        entry = candidates.get(did, {})
        cand = entry.get("c", [])[: args.max_drugs]
        drug_names = []
        for item in cand:
            # entries are [drug_id, score] pairs
            drug_id = item[0] if isinstance(item, (list, tuple)) else \
                (item.get("drug_id") if isinstance(item, dict) else None)
            if not drug_id:
                continue
            n = drugs_lookup.get(drug_id) or drugs_lookup.get(drug_id.replace("CHEBI:", ""))
            if n and n not in drug_names:
                drug_names.append(n)
        if not drug_names:
            print(f"  [skip] {dname}: no candidates")
            continue

        kept = 0
        for drug in drug_names:
            term = f'("{dname}"[Title/Abstract]) AND ("{drug}"[Title/Abstract])'
            try:
                pmids = esearch(term, args.per_drug * 3)
            except Exception as e:
                print(f"  [warn] esearch failed {dname}/{drug}: {e}")
                time.sleep(1.0)
                continue
            time.sleep(SLEEP)

            fresh = [p for p in pmids if p not in seen_pmids][: args.per_drug]
            if not fresh:
                continue
            try:
                arts = efetch(fresh)
            except Exception as e:
                print(f"  [warn] efetch failed {dname}/{drug}: {e}")
                time.sleep(1.0)
                continue
            time.sleep(SLEEP)

            for a in arts:
                if a["pmid"] in seen_pmids:
                    stats["skipped_dup"] += 1
                    continue
                seen_pmids.add(a["pmid"])
                passages.append({
                    "text": a["text"],
                    "source": "pubmed",
                    "drug": drug,
                    "disease": dname,
                    "pmid": a["pmid"],
                    "year": a["year"],
                    "pub_type": a["pub_type"],
                })
                kept += 1
                stats["fetched"] += 1
            print(f"  {dname} / {drug}: +{len(arts)}")

        if kept:
            print(f"[ok] {dname}: {kept} passages")

    with open(args.out, "w") as f:
        json.dump(passages, f, indent=1)

    print()
    print(f"TOTAL passages: {len(passages)} (was {len(existing)})")
    print(f"resolved diseases: {stats['resolved']}/{len(TARGET_DISEASES)}")
    print(f"newly fetched: {stats['fetched']}, dup-skipped: {stats['skipped_dup']}")
    if stats["unresolved"]:
        print(f"unresolved: {stats['unresolved']}")


if __name__ == "__main__":
    main()
