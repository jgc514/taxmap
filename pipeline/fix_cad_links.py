#!/usr/bin/env python3
"""Rebuild web/src/cad-links.json so every county points at a real CAD.

Two defects this fixes:

  1. 37 counties had a duckduckgo SEARCH URL as their link — gen_cad_links.py
     guessed domains like "<county>cad.org" and fell back when the guess missed.
     cad_sources.py has since harvested a verified CAD URL for all 254 counties
     from the Texas appraisal-district directory, so the guessing is obsolete.
  2. Only 77 counties had a per-property deep link, partly because
     gen_cad_deeplinks.py skipped any county flagged `search` — exactly the ones
     most in need of one.

Discovery works off whatever property-search platform the CAD actually runs.
Every candidate is verified against a real prop_id from the build DB (the id
must appear in the response along with a property-detail signature), so a
template is only emitted when it demonstrably renders that parcel. A county
that resolves to nothing keeps its CAD homepage — never a search engine.

    python pipeline/fix_cad_links.py [--only Blanco] [--dry-run]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_cad_rates import SSL_CTX, UA  # noqa: E402

CAD_JSON = ROOT / "web" / "src" / "cad-links.json"
SOURCES = ROOT / "data" / "build" / "cad-sources.json"
DB = ROOT / "data" / "build" / "taxmap.duckdb"

DETAIL_SIG = re.compile(
    r"Property ID|Owner Name|Legal Description|Owner ID|Property Details"
    r"|Appraised Value|Market Value|Geographic ID", re.I)

# Per-property URL shapes, in order of how common they are in Texas. {h} is the
# CAD's bare host, {id} the account number.
TEMPLATES = [
    "https://esearch.{h}/Property/View/{id}",
    "https://propaccess.{h}/clientdb/Property.aspx?prop_id={id}",
    "https://{h}/Property/View/{id}",
    "https://search.{h}/Property-Detail/PropertyQuickRefID/{id}",
    "https://{h}/property-detail/{id}",
    "https://{h}/PropertyDetail/{id}",
]

# Big CADs on their own platforms. Still verified below, so a stale template
# silently drops back to the homepage rather than shipping a broken link.
CURATED = {
    "Dallas": "https://www.dallascad.org/AcctDetailRes.aspx?ID={id}",
    "Williamson": "https://search.wcad.org/Property-Detail/PropertyQuickRefID/{id}",
    "Harris": "https://hcad.org/property-search/real-property/real-property-search-by-account-number?account={id}",
    "Tarrant": "https://www.tad.org/property/{id}",
    "Bexar": "https://propaccess.trueautomation.com/clientdb/Property.aspx?cid=110&prop_id={id}",
}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            if r.status >= 400:
                return None
            return r.read(300_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return None


def verifies(body, prop_id):
    """The page must show THIS property, not just be a working page."""
    return bool(body) and prop_id in body and DETAIL_SIG.search(body) is not None


def host_of(url):
    return re.sub(r"^www\.", "", urllib.parse.urlparse(url or "").netloc)


def rep_prop_ids(n=4):
    """Several sample parcels per county, not one.

    A single sample is fragile: `any_value` picks a different parcel whenever
    parcels_rated is rebuilt, and if that one happens to be an account the CAD's
    public search doesn't serve, a perfectly good template fails verification
    and gets dropped. Seven working links were lost exactly this way.

    There is deliberately NO minimum market value. The old `mkt > 50000` filter
    left 75 rural counties with no sample at all, so their CADs were never even
    tested — ordering by value already puts substantial properties first.
    """
    con = duckdb.connect(str(DB), read_only=True)
    out = {}
    for county, pid in con.execute(
            f"""SELECT county, prop_id FROM (
                  SELECT county, prop_id,
                         row_number() OVER (PARTITION BY county
                                            ORDER BY mkt DESC NULLS LAST) rn
                  FROM parcels_rated
                  WHERE prop_id NOT IN ('0', '')
                ) WHERE rn <= {n}""").fetchall():
        out.setdefault(county, []).append(pid)
    return out


def try_template(tmpl, prop_ids):
    """True if `tmpl` renders any of these parcels."""
    for pid in prop_ids:
        if verifies(fetch(tmpl.replace("{id}", pid)), pid):
            return True
    return False


def discover(county, cad_url, prop_ids, existing_q=None):
    """A verified per-property template for this county, or None."""
    if not prop_ids:
        return existing_q
    # Re-verify a template we already shipped before considering anything else:
    # never trade a working link for a transient fetch failure.
    if existing_q and try_template(existing_q, prop_ids):
        return existing_q
    if county in CURATED and try_template(CURATED[county], prop_ids):
        return CURATED[county]
    host = host_of(cad_url)
    if not host:
        return existing_q

    for t in TEMPLATES:
        cand = t.format(h=host, id="{id}")
        if try_template(cand, prop_ids):
            return cand
    prop_id = prop_ids[0]

    # Fall back to reading the CAD's own site: find whichever property-search
    # host it links to (often a different domain than the CAD's own) and the
    # Property Access client id, then verify those.
    home = fetch(cad_url) or ""
    for m in re.finditer(r"https?://(esearch\.[a-z0-9.\-]+)/", home):
        cand = f"https://{m.group(1)}/Property/View/{{id}}"
        if try_template(cand, prop_ids):
            return cand
    m = re.search(r"clientdb/[^\"']*?cid=(\d+)", home) or re.search(r"[?&]cid=(\d+)", home)
    if m:
        cid = m.group(1)
        base = ("https://propaccess.trueautomation.com/clientdb/Property.aspx"
                f"?cid={cid}&prop_id=")
        if try_template(base + "{id}", prop_ids):
            return base + "{id}"
    for m in re.finditer(r"https?://(propaccess\.[a-z0-9.\-]+)/", home):
        cand = f"https://{m.group(1)}/clientdb/Property.aspx?prop_id={{id}}"
        if try_template(cand, prop_ids):
            return cand
    return existing_q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    cad = json.loads(CAD_JSON.read_text())
    sources = json.loads(SOURCES.read_text())
    pids = rep_prop_ids()

    counties = list(cad)
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        counties = [c for c in counties if c.lower() in want]

    # Step 1: every county gets a real CAD URL, no search engines.
    replaced = []
    for county in counties:
        entry = cad[county]
        real = (sources.get(county) or {}).get("cad")
        if entry.get("search") and real:
            entry["url"] = real
            entry.pop("search", None)
            entry["name"] = f"{county} CAD"
            replaced.append(county)
        elif entry.get("search"):
            replaced.append(f"{county}(NO SOURCE)")

    # Step 2: per-property deep links, verified.
    def work(county):
        return county, discover(county, cad[county]["url"], pids.get(county, []),
                                cad[county].get("q"))

    found, lost = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for county, q in ex.map(work, counties):
            had = bool(cad[county].get("q"))
            if q:
                cad[county]["q"] = q
                if not had:
                    found.append(county)
            else:
                cad[county].pop("q", None)
                if had:
                    lost.append(county)

    still_search = [c for c in cad if cad[c].get("search")]
    withq = sum(1 for c in cad.values() if c.get("q"))
    print(f"search-engine links replaced : {len(replaced)}")
    print(f"still a search fallback      : {len(still_search)} "
          f"{still_search if still_search else ''}")
    print(f"per-property deep links      : {withq}/{len(cad)} "
          f"(+{len(found)} new, -{len(lost)} lost)")
    if found:
        print("  gained:", ", ".join(sorted(found)))
    if lost:
        print("  LOST (verify manually):", ", ".join(sorted(lost)))
    if args.dry_run:
        print("\n--dry-run: cad-links.json not written")
        return
    CAD_JSON.write_text(json.dumps(cad, separators=(",", ":")))
    print(f"-> {CAD_JSON}")


if __name__ == "__main__":
    main()
