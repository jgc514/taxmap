#!/usr/bin/env python3
"""Emit web/src/cad-links.json — per-county appraisal-district site links.

Every county gets an entry. `url` is the CAD's property-search landing page
(verified domains for the high-population CADs; the long tail uses the near-
universal <countyname>cad.org convention). `q` is an optional query-string
template with {id}; when present the app deep-links to the property, else it
opens the search page (the popup also shows the prop_id to paste). A parcel
in a CAD we haven't verified still gets a working search link.
"""
import concurrent.futures
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import COUNTIES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "src" / "cad-links.json"

# Verified CAD domains for the largest counties (property-search landing).
# q = deep-link query template appended to url, {id} = prop_id, where the
# vendor reliably accepts an id in the URL.
VERIFIED = {
    "Harris": ("https://hcad.org/property-search/", None),
    "Dallas": ("https://www.dallascad.org/SearchAddr.aspx", None),
    "Tarrant": ("https://www.tad.org/property-search/", None),
    "Bexar": ("https://bcad.org/clientdb/?cid=1", None),
    "Travis": ("https://traviscad.org/property-search/", None),
    "Collin": ("https://www.collincad.org/propertysearch", None),
    "Denton": ("https://www.dentoncad.com/property-search", None),
    "El Paso": ("https://www.epcad.org/Search/Result?keywords={id}", "deep"),
    "Hidalgo": ("https://www.hidalgoad.org/", None),
    "Fort Bend": ("https://www.fbcad.org/property-search/", None),
    "Montgomery": ("https://mcad-tx.org/property-search/", None),
    "Williamson": ("https://www.wcad.org/property-search/", None),
    "Cameron": ("https://www.cameroncad.org/", None),
    "Nueces": ("https://www.ncadistrict.com/", None),
    "Bell": ("https://bellcad.org/property-search/", None),
    "Brazoria": ("https://www.brazoriacad.org/", None),
    "Galveston": ("https://www.galvestoncad.org/", None),
    "Lubbock": ("https://lubbockcad.org/", None),
    "Webb": ("https://webbcad.org/", None),
    "McLennan": ("https://www.mclennancad.org/", None),
    "Hays": ("https://www.hayscad.com/property-search/", None),
    "Comal": ("https://www.comalad.org/", None),
    "Guadalupe": ("https://www.guadalupead.org/", None),
    "Ellis": ("https://www.elliscad.org/", None),
    "Smith": ("https://www.smithcad.org/", None),
    "Jefferson": ("https://www.jcad.org/", None),
    "Midland": ("https://www.midcad.org/", None),
    "Ector": ("https://www.ectorcad.org/", None),
    "Taylor": ("https://www.taylor-cad.org/", None),
    "Potter": ("https://www.prad.org/", None),
    "Randall": ("https://www.randallcad.org/", None),
    "Johnson": ("https://www.johnsoncad.com/", None),
    "Parker": ("https://www.parkercad.org/", None),
    "Kaufman": ("https://www.kaufman-cad.org/", None),
    "Rockwall": ("https://www.rockwallcad.com/", None),
    "Wichita": ("https://www.wadtx.com/", None),
    "Gregg": ("https://www.gcad.org/", None),
    "Grayson": ("https://www.graysonappraisal.org/", None),
    "Angelina": ("https://www.angelinacad.org/", None),
    "Victoria": ("https://www.victoriacad.org/", None),
}


def slug(name):
    return re.sub(r"[^a-z]", "", name.lower())


def alive(url):
    """True if the domain answers (any 2xx/3xx). CADs vary in path, so we
    only trust the host resolving, not a specific page."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status < 400
    except Exception:
        try:  # some hosts reject HEAD; retry GET
            req.method = "GET"
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status < 400
        except Exception:
            return False


def search_url(county):
    return ("https://duckduckgo.com/?q=" +
            urllib.parse.quote(f"{county} County TX appraisal district property search"))


def main():
    # Probe the convention domain for every non-verified county in parallel;
    # keep direct links that resolve, else a guaranteed search deep-link.
    candidates = {c: f"https://www.{slug(c)}cad.org/" for c in COUNTIES if c not in VERIFIED}
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        results = dict(zip(candidates, ex.map(alive, candidates.values())))

    out = {}
    direct = search = 0
    for cname in COUNTIES:
        if cname in VERIFIED:
            url, mode = VERIFIED[cname]
            entry = {"name": f"{cname} CAD", "url": url}
            if mode == "deep":
                entry["q"] = url
                entry["url"] = url.split("?")[0]
            out[cname] = entry
            direct += 1
        elif results.get(cname):
            out[cname] = {"name": f"{cname} CAD", "url": candidates[cname]}
            direct += 1
        else:
            out[cname] = {"name": f"Find {cname} CAD", "url": search_url(cname), "search": True}
            search += 1
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT.name}: {len(out)} counties ({direct} direct CAD links, "
          f"{search} search fallbacks)")


if __name__ == "__main__":
    main()
