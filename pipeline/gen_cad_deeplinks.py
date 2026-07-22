#!/usr/bin/env python3
"""Augment web/src/cad-links.json with per-property deep-link templates.

Most Texas CADs run on True Automation / Tyler, which has two property-search
platforms with predictable per-property URLs, and our parcel `prop_id` IS the
CAD account number:

  ESearch (newer, self-hosted):
      https://esearch.<cad-domain>/Property/View/<prop_id>
  Property Access (clientdb, hosted):
      https://propaccess.trueautomation.com/clientdb/Property.aspx?cid=<cid>&prop_id=<prop_id>

For each county we pull one real prop_id from the build DB and VERIFY the
candidate URL actually renders that property (the prop_id + a detail-page
signature appear in the response) before emitting a `q` template with `{id}`.
Counties on other platforms (HCAD, Pritchard & Abbott, custom) keep their
search-page link. Nothing that fails verification is emitted, so no deep link
is ever broken.
"""
import concurrent.futures
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
CAD_JSON = ROOT / "web" / "src" / "cad-links.json"
DB = ROOT / "data" / "build" / "taxmap.duckdb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DETAIL_SIG = re.compile(r"Property ID|Owner Name|Legal Description|Owner ID", re.I)

# High-population CADs on their own (non-True-Automation) platforms, with a
# hand-found detail-URL template. Still verified against a real prop_id below,
# so a stale template silently drops to the search fallback.
CURATED_DEEPLINKS = {
    "Dallas": "https://www.dallascad.org/AcctDetailRes.aspx?ID={id}",
    "Williamson": "https://search.wcad.org/Property-Detail/PropertyQuickRefID/{id}",
}


def fetch(url, timeout=18):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status >= 400:
                return None
            return r.read(200000).decode("utf-8", "ignore")
    except Exception:
        return None


def verifies(body, prop_id):
    return bool(body) and prop_id in body and DETAIL_SIG.search(body) is not None


def rep_prop_ids():
    con = duckdb.connect(str(DB), read_only=True)
    out = {}
    for cty, pid in con.execute(
        """SELECT county, any_value(prop_id) FROM parcels_rated
        WHERE prop_id NOT IN ('0','') AND mkt > 50000 GROUP BY county"""
    ).fetchall():
        out[cty] = pid
    return out


def discover(county, entry, prop_id):
    """Return a `q` deep-link template for the county, or None."""
    if not prop_id:
        return None
    # Curated big-county template (verified against a real prop_id).
    if county in CURATED_DEEPLINKS:
        tmpl = CURATED_DEEPLINKS[county]
        if verifies(fetch(tmpl.replace("{id}", prop_id)), prop_id):
            return tmpl
    if entry.get("search"):
        return None
    host = urllib.parse.urlparse(entry["url"]).netloc
    host = re.sub(r"^www\.", "", host)
    if not host:
        return None

    # 1) ESearch self-hosted
    es = f"https://esearch.{host}/Property/View/{prop_id}"
    if verifies(fetch(es), prop_id):
        return f"https://esearch.{host}/Property/View/{{id}}"

    # 2) Property Access cid — find the cid from the CAD homepage, then verify
    home = fetch(entry["url"])
    if home:
        m = re.search(r"clientdb/[^\"']*?cid=(\d+)", home) or re.search(r"[?&]cid=(\d+)", home)
        if m:
            cid = m.group(1)
            pa = (f"https://propaccess.trueautomation.com/clientdb/Property.aspx"
                  f"?cid={cid}&prop_id={prop_id}")
            if verifies(fetch(pa), prop_id):
                return ("https://propaccess.trueautomation.com/clientdb/Property.aspx"
                        f"?cid={cid}&prop_id={{id}}")
        # 3) some homepages link an esearch host on a different domain
        m2 = re.search(r"https?://(esearch\.[a-z0-9.\-]+)/", home)
        if m2:
            es2 = f"https://{m2.group(1)}/Property/View/{prop_id}"
            if verifies(fetch(es2), prop_id):
                return f"https://{m2.group(1)}/Property/View/{{id}}"
    return None


def main():
    cad = json.loads(CAD_JSON.read_text())
    pids = rep_prop_ids()
    items = list(cad.items())
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(lambda kv: discover(kv[0], kv[1], pids.get(kv[0])), items))
    n = 0
    for (county, entry), q in zip(items, results):
        if q:
            entry["q"] = q
            n += 1
        else:
            entry.pop("q", None)
    CAD_JSON.write_text(json.dumps(cad, separators=(",", ":")))
    print(f"deep-links: {n}/{len(cad)} counties got a verified per-property link")
    # sample
    for c, e in list(cad.items()):
        if e.get("q"):
            print(f"  e.g. {c}: {e['q']}")
            break


if __name__ == "__main__":
    main()
