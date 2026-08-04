#!/usr/bin/env python3
"""Find every downloadable appraisal roll / data export on Texas CAD websites.

An appraisal roll lists, per account, the exact set of taxing units that bill
it — the ground truth the map is missing for ESDs, PIDs and partial-county
special districts. `parse_ta_roll.py` / `parse_ta_export.py` / `roll_rates.py`
already turn one into per-parcel rates (proven on Wilson, Bandera, Guadalupe),
so the only obstacle is locating the files.

This crawls each CAD site for links that look like a roll or bulk data export,
then HEADs each candidate to keep only ones that are actually a downloadable
file of plausible size. Nothing large is fetched here — `download_rolls.py`
does that from the manifest this writes.

Output: data/build/roll-sources.json
    {county: {"files": [{url, label, type, bytes}], "pages": [...], "notes": []}}

Usage:
    python pipeline/find_rolls.py [--only Blanco,Bastrop] [--all-counties]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_cad_rates import SSL_CTX, UA, clean_url, fetch  # noqa: E402

SOURCES = ROOT / "data" / "build" / "cad-sources.json"
AUDIT = ROOT / "data" / "build" / "coverage-audit.json"
OUT = ROOT / "data" / "build" / "roll-sources.json"

# What a bulk roll/export link calls itself.
ROLL_HINT = re.compile(
    r"appraisal[\s_-]*(roll|export|data)|certified[\s_-]*roll|tax[\s_-]*roll"
    r"|data[\s_-]*(download|export|request|file)|export[\s_-]*data"
    r"|public[\s_-]*(data|information)|open[\s_-]*record|bulk[\s_-]*data"
    r"|gis[\s_-]*data|downloads?$|/downloads?/", re.I)
# Pages worth opening one more hop for.
PAGE_HINT = re.compile(r"data|download|report|form|record|roll|export|gis", re.I)
FILE_EXT = re.compile(r"\.(zip|txt|csv|tsv|xlsx?|gz|7z|dat|mdb|accdb)(?:$|\?)", re.I)
SKIP = re.compile(r"\.(jpg|jpeg|png|gif|svg|mp4|ico|css|js|woff2?)(?:$|\?)"
                  r"|mailto:|tel:|javascript:", re.I)
# Sizes below this are almost certainly a form or a cover letter, not a roll.
MIN_BYTES = 200_000


def links(html: bytes, base: str) -> list[tuple[str, str]]:
    """Every anchor on the page, archives included.

    Deliberately not `scrub_cad_rates.links`, which drops .zip — for the rate
    scraper an archive is noise, but here the archive IS the thing we want.
    """
    s = html.decode("utf-8", "replace")
    out = []
    for href, label in re.findall(
            r'<a[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', s, re.S | re.I):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", label)).strip()
        href = urllib.parse.urljoin(base, href.strip())
        if href.startswith(("http://", "https://")):
            out.append((href, text))
    return out


def head(url):
    """Content type + length without pulling the body."""
    url = clean_url(url)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40, context=SSL_CTX) as r:
            return (r.status, (r.headers.get("Content-Type") or "").lower(),
                    int(r.headers.get("Content-Length") or 0))
    except Exception:  # noqa: BLE001
        # Some CAD servers reject HEAD; fall back to a ranged GET.
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Range": "bytes=0-0"})
        try:
            with urllib.request.urlopen(req, timeout=40, context=SSL_CTX) as r:
                cr = r.headers.get("Content-Range") or ""
                total = int(cr.rsplit("/", 1)[-1]) if "/" in cr else 0
                return (r.status, (r.headers.get("Content-Type") or "").lower(),
                        total)
        except Exception as e:  # noqa: BLE001
            return (0, f"{type(e).__name__}", 0)


def crawl(county, rec):
    seeds = [u for u in (rec.get("cad"), rec.get("cad_seed"),
                         rec.get("worksheets")) if u]
    seen, cand_files, cand_pages, notes = set(), {}, {}, []
    queue = [(u, 0) for u in dict.fromkeys(seeds)]
    fetched = 0
    while queue and fetched < 25:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            status, body, ctype = fetch(url, timeout=40)
        except Exception as e:  # noqa: BLE001
            notes.append(f"{url} :: {type(e).__name__}")
            continue
        fetched += 1
        if status != 200 or "html" not in ctype:
            continue
        host = urllib.parse.urlparse(url).netloc
        # On a page that is itself the data-download page, any archive is a
        # candidate — its link text is often just "2025" or a button label.
        on_data_page = bool(ROLL_HINT.search(url))
        for href, label in links(body, url):
            if SKIP.search(href) or href in seen:
                continue
            blob = f"{href} {label}"
            if FILE_EXT.search(href) and (on_data_page or ROLL_HINT.search(blob)):
                cand_files.setdefault(href, label or href.rsplit("/", 1)[-1])
            elif depth < 2 and ROLL_HINT.search(blob):
                cand_pages.setdefault(href, label)
                if urllib.parse.urlparse(href).netloc == host:
                    queue.append((href, depth + 1))
            elif depth < 1 and PAGE_HINT.search(label or "") and \
                    urllib.parse.urlparse(href).netloc == host:
                queue.append((href, depth + 1))

    files = []
    for url, label in list(cand_files.items())[:40]:
        st, ct, n = head(url)
        files.append({"url": url, "label": (label or "")[:90],
                      "status": st, "type": ct, "bytes": n,
                      "usable": bool(st in (200, 206) and n >= MIN_BYTES)})
    files.sort(key=lambda f: -f["bytes"])
    return {"county": county, "fips": rec["fips"], "ptad": rec["ptad"],
            "files": files, "pages": [{"url": u, "label": (l or "")[:90]}
                                      for u, l in list(cand_pages.items())[:25]],
            "notes": notes[:10]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--all-counties", action="store_true",
                    help="crawl all 254, not just the ESD-gap counties")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    sources = json.loads(SOURCES.read_text())
    audit = json.loads(AUDIT.read_text())
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        sources = {k: v for k, v in sources.items() if k.lower() in want}
    elif not args.all_counties:
        sources = {k: v for k, v in sources.items()
                   if audit.get(k, {}).get("esd_count")}
    print(f"hunting rolls for {len(sources)} counties")

    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(crawl, k, v): k for k, v in sources.items()}
        for f in as_completed(futs):
            county = futs[f]
            done += 1
            try:
                out[county] = f.result()
            except Exception as e:  # noqa: BLE001
                out[county] = {"county": county, "files": [], "pages": [],
                               "notes": [f"{type(e).__name__}: {e}"]}
            if done % 10 == 0 or done == len(futs):
                print(f"  {done}/{len(futs)}", flush=True)

    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    hits = {c: v for c, v in out.items() if any(f["usable"] for f in v["files"])}
    total = sum(max((f["bytes"] for f in v["files"] if f["usable"]), default=0)
                for v in hits.values())
    print(f"\ncounties with a downloadable roll/export: {len(hits)}/{len(out)}")
    print(f"largest-file total if we pull one per county: {total / 1e6:.0f} MB")
    for c in sorted(hits):
        best = max((f for f in out[c]["files"] if f["usable"]),
                   key=lambda f: f["bytes"])
        print(f"  {c:16s} {best['bytes'] / 1e6:8.1f} MB  {best['label'][:44]:44s} "
              f"{best['url'][:70]}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
