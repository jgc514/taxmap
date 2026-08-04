#!/usr/bin/env python3
"""Hunt for published ESD (and other special-district) boundary layers.

Two families, both ArcGIS REST:
  1. BIS Consultants hosts the GIS web service for a large share of Texas CADs
     under org accounts named `bis_<county>cad`. Those services frequently
     carry a jurisdiction/ESD/fire-district layer alongside parcels.
  2. Individual county / city open-data orgs publish standalone ESD layers.

We enumerate candidate Feature Services, read each one's layer list, and keep
any layer whose name looks like an emergency-services / fire / jurisdiction
boundary. Nothing is downloaded here — this produces the shopping list.

Output: data/build/esd-layer-candidates.json
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "build" / "esd-layer-candidates.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0"

HIT = re.compile(r"\besd\b|emergency\s*serv|fire\s*(district|dept|department|protection)"
                 r"|jurisdiction|taxing|tax\s*unit|entit", re.I)
QUERIES = [
    'owner:bis_* AND type:"Feature Service"',
    '("emergency service district" OR "emergency services district" OR ESD) '
    'AND Texas AND type:"Feature Service"',
    '("fire district" OR "fire districts") AND Texas AND type:"Feature Service"',
    '("taxing jurisdictions" OR "tax jurisdictions" OR "taxing entities") '
    'AND Texas AND type:"Feature Service"',
]


def get(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def search_all(q):
    out, start = [], 1
    while start > 0 and len(out) < 600:
        try:
            d = get("https://www.arcgis.com/sharing/rest/search",
                    {"q": q, "num": 100, "start": start, "f": "json"})
        except Exception:  # noqa: BLE001
            break
        out.extend(d.get("results", []))
        start = d.get("nextStart", -1)
    return out


def layers_of(item):
    url = item.get("url") or ""
    if not url.endswith(("FeatureServer", "MapServer")):
        return None
    try:
        d = get(url, {"f": "pjson"})
    except Exception as e:  # noqa: BLE001
        return {"item": item["title"], "owner": item.get("owner"), "url": url,
                "error": f"{type(e).__name__}"}
    layers = [{"id": l["id"], "name": l["name"]}
              for l in (d.get("layers") or []) + (d.get("tables") or [])]
    hits = [l for l in layers if HIT.search(l["name"])]
    return {"item": item["title"], "owner": item.get("owner"), "url": url,
            "layers": [l["name"] for l in layers], "hits": hits}


def main():
    items, seen = [], set()
    for q in QUERIES:
        for r in search_all(q):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            items.append(r)
    print(f"{len(items)} candidate services")

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for i, res in enumerate(ex.map(layers_of, items), 1):
            if res:
                results.append(res)
            if i % 50 == 0:
                print(f"  probed {i}/{len(items)}", flush=True)

    hits = [r for r in results if r.get("hits")]
    OUT.write_text(json.dumps({"hits": hits, "all": results}, indent=1))
    print(f"\nservices with an ESD/fire/jurisdiction layer: {len(hits)}")
    for h in sorted(hits, key=lambda r: r["item"])[:60]:
        print(f"  {h['owner']:26s} {h['item'][:38]:38s} "
              f"{[l['name'] for l in h['hits']][:3]}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
