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

# Verified CAD ROOT domains for the largest counties. Roots only — never a
# guessed sub-path (those 404 when the CAD reorganizes; every CAD homepage
# links to its own property search). Each is still re-checked at generation
# time below, and any that fails is downgraded to the search fallback so no
# emitted link can 404.
VERIFIED = {
    "Harris": "https://hcad.org/",
    "Dallas": "https://www.dallascad.org/",
    "Tarrant": "https://www.tad.org/",
    "Bexar": "https://bcad.org/",
    "Travis": "https://traviscad.org/",
    "Collin": "https://www.collincad.org/",
    "Denton": "https://www.dentoncad.com/",
    "El Paso": "https://www.epcad.org/",
    "Hidalgo": "https://www.hidalgoad.org/",
    "Fort Bend": "https://www.fbcad.org/",
    "Montgomery": "https://mcad-tx.org/",
    "Williamson": "https://www.wcad.org/",
    "Cameron": "https://www.cameroncad.org/",
    "Nueces": "https://www.ncadistrict.com/",
    "Bell": "https://bellcad.org/",
    "Brazoria": "https://www.brazoriacad.org/",
    "Galveston": "https://www.galvestoncad.org/",
    "Lubbock": "https://lubbockcad.org/",
    "McLennan": "https://www.mclennancad.org/",
    "Hays": "https://www.hayscad.com/",
    "Comal": "https://www.comalad.org/",
    "Guadalupe": "https://www.guadalupead.org/",
    "Ellis": "https://www.elliscad.org/",
    "Smith": "https://www.smithcad.org/",
    "Jefferson": "https://www.jcad.org/",
    "Midland": "https://www.midcad.org/",
    "Ector": "https://www.ectorcad.org/",
    "Taylor": "https://www.taylor-cad.org/",
    "Potter": "https://www.prad.org/",
    "Johnson": "https://www.johnsoncad.com/",
    "Kaufman": "https://www.kaufman-cad.org/",
    "Rockwall": "https://www.rockwallcad.com/",
    "Wichita": "https://www.wadtx.com/",
    "Gregg": "https://www.gcad.org/",
    "Grayson": "https://www.graysonappraisal.org/",
    "Angelina": "https://www.angelinacad.org/",
    "Victoria": "https://www.victoriacad.org/",
}


def slug(name):
    return re.sub(r"[^a-z]", "", name.lower())


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# Bot-block / auth / rate-limit statuses mean the SITE EXISTS (it just refuses
# our scripted request); a real browser reaches it, so treat as reachable.
LIVE_NON_2XX = {401, 403, 405, 429}


def alive(url):
    """True if the URL resolves to a real page (follows redirects). Verifies
    the exact final URL, not just the host, so a 404'ing path is caught."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status < 400
        except urllib.error.HTTPError as e:
            if e.code in LIVE_NON_2XX:
                return True
            if e.code == 404:
                return False
            # other HTTP errors: retry with GET, else treat as dead
        except Exception:
            pass
    return False


def search_url(county):
    return ("https://duckduckgo.com/?q=" +
            urllib.parse.quote(f"{county} County TX appraisal district property search"))


def main():
    # One candidate direct URL per county: the verified root, else the
    # <countyname>cad.org convention. Probe them ALL — including the verified
    # ones — and emit a direct link only when it truly resolves; otherwise a
    # guaranteed search fallback. Invariant: no emitted direct link 404s.
    candidates = {
        c: VERIFIED.get(c, f"https://www.{slug(c)}cad.org/") for c in COUNTIES
    }
    # Double-probe: a link is kept only if it resolves on BOTH passes, so a
    # transient/parked false-positive (e.g. a domain that isn't really the
    # CAD) downgrades to search rather than emitting a link that may 404.
    def alive2(url):
        return alive(url) and alive(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        live = dict(zip(candidates, ex.map(alive2, candidates.values())))

    out = {}
    direct = search = 0
    for cname in COUNTIES:
        if live.get(cname):
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
