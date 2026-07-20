#!/usr/bin/env python3
"""Download the statewide TCEQ Water Districts polygon layer (MUD/WCID/WID/
FWSD/etc.) to data/raw/tceq_water_districts.geojson for the special-district
spatial join in build_region.py."""
import json, urllib.request, time
SVC = "https://services2.arcgis.com/LYMgRMwHfrWWEg3s/arcgis/rest/services/TCEQ_Water_Districts/FeatureServer/0/query"
def q(params):
    url = SVC + "?" + urllib.parse.urlencode(params)
    for _ in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: return json.load(r)
        except Exception as e: time.sleep(2)
    raise RuntimeError("fail")
import urllib.parse
# count
n = q({"where":"1=1","returnCountOnly":"true","f":"json"})["count"]
print("total districts:", n)
feats=[]; off=0
while off < n:
    d = q({"where":"1=1","outFields":"NAME,TYPE,COUNTY,DISTRICT_ID,STATUS","resultOffset":off,"resultRecordCount":1000,"outSR":"4326","f":"geojson"})
    fs=d.get("features",[]); feats+=fs; off+=len(fs)
    if not fs: break
    print("fetched", off)
open("data/raw/tceq_water_districts.geojson","w").write(json.dumps({"type":"FeatureCollection","features":feats}))
from collections import Counter
print("types:", Counter(f["properties"]["TYPE"] for f in feats))
print("active:", sum(1 for f in feats if f["properties"].get("STATUS")=="A"))
