#!/usr/bin/env python3
"""Build a per-county index of authoritative tax-rate sources.

Two seeds, merged:
  1. web/src/cad-links.json  — CAD homepages already probed by gen_cad_links.py
     (212 direct hits, 42 duckduckgo search fallbacks we need to replace).
  2. knowyourtaxes.org/county/<slug>/ — the Texas Association of Appraisal
     Districts' county directory. Every page links the county's CAD site, its
     Truth-in-Taxation lookup tool (<county>.countytaxrates.com or a vendor
     equivalent) and its "Property Tax Rate Worksheet(s)" page. This is the one
     statewide index that is uniform across all 254 counties.

Output: data/build/cad-sources.json
  {county: {fips, ptad, cad: url|None, tnt: url|None, worksheets: url|None}}
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import HAND_CURATED  # noqa: E402
from recipes_statewide import STATEWIDE_COUNTIES  # noqa: E402

OUT = ROOT / "data" / "build" / "cad-sources.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def harvest(county):
    """Pull CAD / TNT / worksheet URLs off the county's knowyourtaxes page."""
    url = f"https://knowyourtaxes.org/county/{slug(county)}/"
    try:
        html = get(url)
    except Exception as e:  # noqa: BLE001
        return county, {"error": f"{type(e).__name__}: {e}"}

    out = {}
    # Links are emitted as <a href="URL">Label</a>; match on the label text.
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"<[^>]+>", " ", label).strip().lower()
        href = href.strip()
        if not href.startswith("http"):
            continue
        if "truth in taxation" in text and "tnt" not in out:
            out["tnt"] = href
        elif "appraisal district" in text and "cad" not in out:
            out["cad"] = href
        elif "worksheet" in text and "worksheets" not in out:
            out["worksheets"] = href
        elif "property look-up" in text and "cad" not in out:
            out["cad"] = href
    return county, out


def main():
    counties = {}
    for name, c in HAND_CURATED.items():
        counties[name] = {"fips": c["fips"], "ptad": c["ptad"]}
    for name, c in STATEWIDE_COUNTIES.items():
        counties.setdefault(name, {"fips": c["fips"], "ptad": c["ptad"]})
    print(f"{len(counties)} counties")

    cad_links = json.loads((ROOT / "web" / "src" / "cad-links.json").read_text())

    with ThreadPoolExecutor(max_workers=12) as ex:
        for county, found in ex.map(harvest, counties):
            counties[county].update(found)

    ok = 0
    for name, rec in counties.items():
        seed = cad_links.get(name) or {}
        if not rec.get("cad") and not seed.get("search"):
            rec["cad"] = seed.get("url")
        rec["cad_seed"] = None if seed.get("search") else seed.get("url")
        if rec.get("cad"):
            ok += 1
    OUT.write_text(json.dumps(counties, indent=1, sort_keys=True))
    tnt = sum(1 for r in counties.values() if r.get("tnt"))
    ws = sum(1 for r in counties.values() if r.get("worksheets"))
    err = sum(1 for r in counties.values() if r.get("error"))
    print(f"cad url: {ok}   tnt: {tnt}   worksheets: {ws}   page errors: {err}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
