import json
import os
import re
import sys
import xml.etree.ElementTree as ET  # used for Form 4 parsing
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import requests

EDGAR_HEADERS = {"User-Agent": "smartmoney-agent contact@smartmoney.dev"}
BASE = "https://data.sec.gov"
EFTS = "https://efts.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def insider_tracker(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.fetch("fixture file", f"fixtures/{ticker.lower()}.json")
        return _load_fixture(ticker)

    logger.fetch("SEC EDGAR", f"www.sec.gov/files/company_tickers.json — looking up CIK for {ticker}")
    cik = _get_cik(ticker)
    if not cik:
        logger.warn(f"CIK not found for {ticker}")
        return _empty()
    logger.found("CIK", cik)

    logger.fetch("SEC EDGAR", f"data.sec.gov/submissions/CIK{cik}.json — Form 4 insider transactions")
    form4_data = _fetch_form4(cik)

    logger.fetch("SEC EDGAR EFTS", f"efts.sec.gov — 13F-HR filings mentioning {ticker}")
    institutional = _fetch_13f(ticker)

    return {
        "net_institutional_direction": institutional["direction"],
        "recent_13f_changes": institutional["changes"],
        "insider_buys": form4_data,
        "notable_funds": institutional["notable_funds"],
    }


def _get_cik(ticker: str) -> str | None:
    """Use EDGAR's authoritative ticker→CIK map."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            return str(entry["cik_str"]).zfill(10)
    return None


# ── Form 4 ────────────────────────────────────────────────────────────────────

def _fetch_form4(cik: str) -> list[dict]:
    url = f"{BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])

    cutoff = (date.today() - timedelta(days=90)).isoformat()
    insider_buys = []

    for i, form in enumerate(forms):
        if len(insider_buys) >= 5:
            break
        if form == "4" and dates[i] >= cutoff:
            acc = accessions[i].replace("-", "")
            # Filer CIK is the first 10 digits of the accession number
            filer_cik = str(int(acc[:10]))
            parsed = _parse_form4_xml(filer_cik, acc, dates[i])
            insider_buys.extend(parsed)

    return insider_buys[:5]


def _parse_form4_xml(cik: str, accession_no: str, filing_date: str) -> list[dict]:
    # Get filing index to find the XML document
    index_url = f"{ARCHIVES}/{int(cik)}/{accession_no}/{accession_no}-index.json"
    try:
        resp = requests.get(index_url, headers=EDGAR_HEADERS, timeout=10)
        resp.raise_for_status()
        index = resp.json()
    except Exception:
        return []

    xml_file = None
    for doc in index.get("documents", []):
        if doc.get("type") == "4" and doc.get("document", "").endswith(".xml"):
            xml_file = doc["document"]
            break
    if not xml_file:
        return []

    xml_url = f"{ARCHIVES}/{int(cik)}/{accession_no}/{xml_file}"
    try:
        resp = requests.get(xml_url, headers=EDGAR_HEADERS, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []

    def text(el, path):
        node = el.find(path)
        return node.text.strip() if node is not None and node.text else ""

    owner_name = text(root, ".//rptOwnerName")
    officer_title = text(root, ".//officerTitle") or (
        "Director" if text(root, ".//isDirector") == "1" else "Insider"
    )

    results = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        if text(txn, ".//transactionAcquiredDisposedCode/value") != "A":
            continue
        try:
            shares = int(float(text(txn, ".//transactionShares/value")))
            price_str = text(txn, ".//transactionPricePerShare/value")
            price = float(price_str) if price_str else 0.0
        except (ValueError, TypeError):
            continue
        results.append({
            "name": owner_name,
            "role": officer_title,
            "shares": shares,
            "value_usd": round(shares * price, 2),
            "date": filing_date,
        })

    return results


# ── 13F ──────────────────────────────────────────────────────────────────────

def _fetch_13f(ticker: str) -> dict:
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    url = (
        f"{EFTS}/LATEST/search-index?q=%22{ticker}%22"
        f"&forms=13F-HR&dateRange=custom&startdt={cutoff}"
    )
    try:
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {"direction": "neutral", "changes": [], "notable_funds": []}

    hits = data.get("hits", {}).get("hits", [])
    changes = []
    notable_funds = []

    for hit in hits[:8]:
        src = hit.get("_source", {})

        # Parse fund name from display_names, e.g. "Millennium Management LLC (CIK 0001273931)"
        display = src.get("display_names", [""])[0]
        fund = re.sub(r"\s*\(CIK[^)]+\)", "", display).strip()
        filed_date = src.get("file_date", "")
        accession_no = src.get("adsh", "").replace("-", "")
        entity_id = (src.get("ciks", ["0"]) or ["0"])[0].zfill(10)

        if not fund:
            continue

        # Mark as "recent" if filed within last 90 days
        days_ago = (date.today() - date.fromisoformat(filed_date)).days if filed_date else 999
        action = "recent filing" if days_ago <= 90 else "holding"

        notable_funds.append(fund)
        changes.append({
            "fund": fund,
            "action": action,
            "shares_delta": 0,
            "filed_date": filed_date,
        })

    changes = changes[:5]
    notable_funds = list(dict.fromkeys(notable_funds))[:5]

    recent = sum(1 for c in changes if c["action"] == "recent filing")
    if recent >= 2:
        direction = "accumulating"
    elif len(changes) >= 3:
        direction = "accumulating"
    else:
        direction = "neutral"

    return {"direction": direction, "changes": changes, "notable_funds": notable_funds}


# ── helpers ───────────────────────────────────────────────────────────────────

def _empty() -> dict:
    return {
        "net_institutional_direction": "neutral",
        "recent_13f_changes": [],
        "insider_buys": [],
        "notable_funds": [],
    }


def _load_fixture(ticker: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data["insider_tracker"]
