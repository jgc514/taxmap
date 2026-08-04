#!/usr/bin/env python3
"""Scrub every Texas CAD website for its published adopted-tax-rate tables.

For each of the 254 counties we start from the two URLs cad_sources.py found
(the CAD homepage and the "Property Tax Rate Worksheet(s)" page), crawl one or
two hops inside the same host looking for anything that smells like a rate
table -- HTML pages, PDFs, XLSX -- download it, and cache the extracted text.

Nothing is parsed for meaning here beyond (entity name, rate) pairs; the
comparison against PTAD and against what the app actually shows lives in
compare_cad_rates.py, so parsing can be re-run without re-fetching.

Cache layout (all under data/raw/cad-rates/):
    <FIPS>/index.json     what we fetched, where from, http status
    <FIPS>/<n>.txt        extracted text of each document
Output: data/build/cad-rates.json  {county: {"units": [[name, rate, src]], ...}}

Usage:
    python pipeline/scrub_cad_rates.py [--only Blanco,Comal] [--refetch]
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import ssl
import sys
import traceback
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "cad-rates"
SOURCES = ROOT / "data" / "build" / "cad-sources.json"
OUT = ROOT / "data" / "build" / "cad-rates.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE          # many CADs ship expired/partial chains

TAX_YEAR = 2025

# Link text / href patterns worth following or downloading.
RATE_HINT = re.compile(
    r"tax[\s_-]*rate|rate[\s_-]*(?:sheet|table|chart|info|history)|adopted"
    r"|truth[\s_-]*in[\s_-]*tax|worksheet|jurisdiction|taxing[\s_-]*(?:unit|entit)"
    r"|entity[\s_-]*(?:code|rate)|levy|levies", re.I)
DOC_EXT = re.compile(r"\.(pdf|xlsx?|csv)(?:$|\?)", re.I)
SKIP = re.compile(r"\.(jpg|jpeg|png|gif|svg|zip|mp4|docx?|pptx?)(?:$|\?)|"
                  r"mailto:|tel:|javascript:|/wp-json/|#", re.I)


def clean_url(url: str) -> str:
    """Percent-encode spaces/control chars that CAD sites emit raw in hrefs.

    Roughly a third of all fetch failures on the first statewide pass were
    urllib InvalidURL on links like `/Forms/Ge neral Info.pdf`.
    """
    url = url.strip().replace("\n", "").replace("\r", "").replace("\t", "")
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc,
        urllib.parse.quote(parts.path, safe="/%:@&=+$,~!*'()"),
        urllib.parse.quote(parts.query, safe="/?%:@&=+$,~!*'()"),
        "",
    ))


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes, str]:
    url = clean_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            try:
                body = gzip.decompress(body)
            except OSError:
                pass
        return r.status, body, (r.headers.get("Content-Type") or "").lower()


def html_to_text(raw: bytes) -> str:
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", s)
    # Keep table structure: cells become tabs, rows become newlines.
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"(?i)</(tr|p|div|li|h[1-6]|br)\s*/?>", "\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
         .replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&#187;", ">"))
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def pdf_to_text(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:40])


def xlsx_to_text(raw: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets[:8]:
        out.append(f"### sheet {ws.title}")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 4000:
                break
            cells = ["" if c is None else str(c) for c in row]
            if any(c.strip() for c in cells):
                out.append("\t".join(cells))
    return "\n".join(out)


def extract(raw: bytes, ctype: str, url: str) -> str:
    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
        return pdf_to_text(raw)
    if "sheet" in ctype or "excel" in ctype or re.search(r"\.xlsx?($|\?)", url, re.I):
        return xlsx_to_text(raw)
    if "csv" in ctype or url.lower().split("?")[0].endswith(".csv"):
        return raw.decode("utf-8", "replace")
    return html_to_text(raw)


def links(html: bytes, base: str) -> list[tuple[str, str]]:
    s = html.decode("utf-8", "replace")
    out = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                                  s, re.S | re.I):
        text = re.sub(r"<[^>]+>", " ", label)
        text = re.sub(r"\s+", " ", text).strip()
        href = urllib.parse.urljoin(base, href.strip())
        if href.startswith(("http://", "https://")) and not SKIP.search(href):
            out.append((href, text))
    return out


def score(url: str, text: str) -> int:
    """How likely this link leads to an adopted-rate table for TAX_YEAR."""
    blob = f"{url} {text}"
    if not RATE_HINT.search(blob):
        return 0
    s = 1
    if DOC_EXT.search(url):
        s += 3
    if re.search(r"adopted", blob, re.I):
        s += 3
    if re.search(r"\b(20)?25\b|2025", blob):
        s += 3
    if re.search(r"tax[\s_-]*rate", blob, re.I):
        s += 2
    if re.search(r"truth[\s_-]*in[\s_-]*tax", blob, re.I):
        s += 1
    if re.search(r"2024|2023|2022|2021|2020|history|archive", blob, re.I):
        s -= 2
    # Form 50-856/50-859 "Tax Rate Calculation Worksheet" is a per-unit
    # rate-setting form, not a table of every jurisdiction. Deprioritise.
    if re.search(r"calculation[\s_-]*worksheet|50-8[45]\d", blob, re.I):
        s -= 4
    return s


# Per-unit Truth-in-Taxation calculation forms: full of stray decimals
# ("multiply by 1.035") that would otherwise parse as jurisdiction rates.
CALC_FORM = re.compile(r"Tax Rate Calculation Worksheet|Form 50-8[45]\d"
                       r"|No-New-Revenue Tax Rate Worksheet", re.I)


# A rate per $100 of value: 0.0001 .. 3.5, written with a decimal point.
RATE_RE = re.compile(r"(?<![\d.])(\$?\d{0,2}\.\d{2,8})(?![\d])")
NOISE = re.compile(r"total|combined|^\W*$|copyright|phone|fax|page \d|\bhomestead\b"
                   r"|exemption|percent|%$", re.I)


BARE_NUM = re.compile(r"^\s*\$?\d{0,2}\.\d{2,8}\s*%?\s*$")


def _rejoin(lines: list[str]) -> list[str]:
    """Glue a rate that sits on its own line back onto the name above it.

    Vendor portals (Pritchard & Abbott's texastaxtransparency, for one) wrap
    each table cell in block elements, so a row arrives as "Carson County" then
    "0.47229400" on the next line.
    """
    out = []
    for line in lines:
        if BARE_NUM.match(line) and out and not BARE_NUM.match(out[-1]):
            out[-1] = f"{out[-1].rstrip()}\t{line.strip()}"
        else:
            out.append(line)
    return out


def parse_units(text: str) -> list[tuple[str, float]]:
    """Pull (entity name, rate) pairs out of an extracted rate table."""
    if CALC_FORM.search(text[:6000]):
        return []
    found = []
    for line in _rejoin(text.splitlines()):
        line = line.strip()
        if len(line) < 5 or len(line) > 200:
            continue
        nums = RATE_RE.findall(line)
        if not nums:
            continue
        # entity name = leading run of words before the first number
        head = RATE_RE.split(line)[0].strip(" \t:.-|$")
        head = re.sub(r"\s{2,}|\t", " ", head).strip()
        head = re.sub(r"^\d{2,}[\s.-]*", "", head)          # drop leading row nums
        if len(head) < 4 or not re.search(r"[A-Za-z]{3}", head):
            continue
        if NOISE.search(head):
            continue
        vals = []
        for n in nums:
            try:
                v = float(n.replace("$", ""))
            except ValueError:
                continue
            if 0.0001 <= v <= 3.5:
                vals.append(v)
        if not vals:
            continue
        # Adopted total is usually the largest plausible figure on the row when
        # M&O / I&S components are broken out, and equals their sum.
        rate = max(vals)
        comps = [v for v in vals if v != rate]
        if len(comps) >= 2 and abs(sum(comps[:2]) - rate) < 1e-6:
            pass                                            # confirmed M&O + I&S
        found.append((head[:80], round(rate, 6)))
    return found


def vendor_seeds(rec: dict) -> list[str]:
    """Direct rate-table URLs for the Truth-in-Taxation vendors we know.

    Pritchard & Abbott's portal serves every jurisdiction and its adopted rate
    as plain server-rendered HTML at /<County>/Search/TaxRates — one hop that
    covers ~54 counties whose CAD site itself publishes nothing parsable.
    """
    tnt = rec.get("tnt") or ""
    out = []
    m = re.match(r"(https?://(?:www\.)?texastaxtransparency\.com/([^/?#]+))", tnt, re.I)
    if m:
        out.append(f"https://texastaxtransparency.com/{m.group(2)}/Search/TaxRates")
    m = re.match(r"(https?://[^/]*truthintax\.com)", tnt, re.I)
    if m:
        out.append(f"{m.group(1)}/search/TaxRates")
    return out


def crawl_county(name: str, rec: dict, refetch: bool) -> dict:
    fips = rec["fips"]
    outdir = CACHE / fips
    outdir.mkdir(parents=True, exist_ok=True)
    index_path = outdir / "index.json"
    if index_path.exists() and not refetch:
        return json.loads(index_path.read_text())

    seeds = [u for u in (rec.get("worksheets"), rec.get("cad"), rec.get("cad_seed"),
                         rec.get("tnt")) if u]
    seeds = vendor_seeds(rec) + seeds
    seen, docs, errors = set(), [], []
    queue = [(u, 12, 0) for u in dict.fromkeys(seeds)]     # (url, score, depth)
    n = 0
    while queue and n < 20:
        queue.sort(key=lambda t: (-t[1], t[2]))
        url, sc, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            status, body, ctype = fetch(url)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url} :: {type(e).__name__}: {e}")
            continue
        if status != 200 or not body:
            errors.append(f"{url} :: HTTP {status}")
            continue
        try:
            text = extract(body, ctype, url)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url} :: extract {type(e).__name__}: {e}")
            continue
        is_doc = bool(DOC_EXT.search(url)) or "pdf" in ctype or "sheet" in ctype
        if text.strip():
            path = outdir / f"{n}.txt"
            path.write_text(text[:400_000])
            docs.append({"url": url, "file": path.name, "doc": is_doc,
                         "score": sc, "chars": len(text)})
            n += 1
        if is_doc or depth >= 2:
            continue
        host = urllib.parse.urlparse(url).netloc
        for href, label in links(body, url):
            if href in seen:
                continue
            if urllib.parse.urlparse(href).netloc != host and not DOC_EXT.search(href):
                continue
            s = score(href, label)
            if s > 0:
                queue.append((href, s, depth + 1))
    idx = {"county": name, "fips": fips, "ptad": rec["ptad"],
           "seeds": seeds, "docs": docs, "errors": errors[:20]}
    index_path.write_text(json.dumps(idx, indent=1))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated county names")
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    sources = json.loads(SOURCES.read_text())
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        sources = {k: v for k, v in sources.items() if k.lower() in want}

    results, done = {}, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(crawl_county, k, v, args.refetch): k
                for k, v in sources.items()}
        for f in as_completed(futs):
            county = futs[f]
            done += 1
            try:
                results[county] = f.result()
            except Exception:  # noqa: BLE001
                results[county] = {"county": county, "docs": [],
                                   "errors": [traceback.format_exc(limit=2)]}
            if done % 10 == 0 or done == len(futs):
                print(f"  crawled {done}/{len(futs)}", flush=True)

    parsed = {}
    for county, idx in results.items():
        units, best = [], 0
        for d in idx.get("docs", []):
            text = (CACHE / idx["fips"] / d["file"]).read_text()
            pairs = parse_units(text)
            if pairs:
                units.append({"url": d["url"], "file": d["file"],
                              "n": len(pairs), "pairs": pairs})
                best = max(best, len(pairs))
        parsed[county] = {"fips": idx.get("fips"), "ptad": idx.get("ptad"),
                          "docs": len(idx.get("docs", [])),
                          "tables": units, "best": best,
                          "errors": idx.get("errors", [])}
    OUT.write_text(json.dumps(parsed, indent=1, sort_keys=True))

    with_any = sum(1 for v in parsed.values() if v["best"] >= 3)
    print(f"\ncounties with a usable rate table: {with_any}/{len(parsed)}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
