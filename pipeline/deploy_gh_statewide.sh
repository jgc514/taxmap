#!/bin/bash
# Interim statewide hosting on GitHub Pages (until R2 exists — see
# docs/LAUNCH-CHECKLIST.md §1): GitHub caps each Pages site at ~1GB, so
# archives that don't fit on the main site spill into extra public repos
# (taxmap-tiles-1, -2, ...), each serving its own gh-pages tiles/ dir.
#
# - metro-rest + bexar-parcels stay on the MAIN site (stable URLs that
#   HomeMatrix depends on), then more archives fill the main site up to
#   MAIN_BUDGET; overflow goes to tile repos up to REPO_BUDGET each.
# - Rewrites web/src/archives.json with {name, url} entries for overflow,
#   rebuilds the app, and stages every repo's worktree under SCRATCH.
# - Requires: gh auth (repo create), git. Run from anywhere.
# Usage: pipeline/deploy_gh_statewide.sh <scratch-dir> [--push]
#   without --push: stages everything and prints the plan (dry run)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_TILES="$ROOT/web/public/tiles"
ARCHIVES_JSON="$ROOT/web/src/archives.json"
SCRATCH="${1:?usage: deploy_gh_statewide.sh <scratch-dir> [--push]}"
PUSH="${2:-}"
OWNER="jgc514"
MAIN_BUDGET=$((900 * 1024 * 1024))
REPO_BUDGET=$((950 * 1024 * 1024))
PAGES_BASE="https://${OWNER}.github.io"

names=$(python3 -c "
import json
for e in json.load(open('$ARCHIVES_JSON')):
    print(e if isinstance(e, str) else e['name'])")

# Pinned-to-main archives first (stable URLs), then the rest in listed order.
main_list="metro-rest-2025 bexar-parcels-2025"
rest=$(echo "$names" | grep -vE '^(metro-rest-2025|bexar-parcels-2025)$')

main_used=0
declare -a overflow=()
plan_main=""
for a in $main_list $rest; do
  f="$WEB_TILES/$a.pmtiles"
  [ -f "$f" ] || { echo "missing archive: $a"; exit 1; }
  sz=$(stat -f%z "$f")
  case " $main_list " in *" $a "*) pinned=1 ;; *) pinned=0 ;; esac
  if [ "$pinned" = 1 ] || [ $((main_used + sz)) -le "$MAIN_BUDGET" ]; then
    main_used=$((main_used + sz))
    plan_main="$plan_main $a"
  else
    overflow+=("$a")
  fi
done

echo "MAIN site ($((main_used / 1048576))MB):$plan_main"

# Pack overflow into tile repos.
declare -a repo_lists=() repo_sizes=()
for a in "${overflow[@]+"${overflow[@]}"}"; do
  sz=$(stat -f%z "$WEB_TILES/$a.pmtiles")
  placed=0
  for i in "${!repo_lists[@]}"; do
    if [ $((repo_sizes[i] + sz)) -le "$REPO_BUDGET" ]; then
      repo_lists[i]="${repo_lists[i]} $a"; repo_sizes[i]=$((repo_sizes[i] + sz)); placed=1; break
    fi
  done
  [ "$placed" = 0 ] && { repo_lists+=(" $a"); repo_sizes+=("$sz"); }
done
for i in "${!repo_lists[@]+"${!repo_lists[@]}"}"; do
  echo "taxmap-tiles-$((i + 1)) ($((repo_sizes[i] / 1048576))MB):${repo_lists[i]}"
done

# Rewrite archives.json with absolute URLs for overflow archives.
python3 - "$ARCHIVES_JSON" <<PYEOF
import json, sys
main = "$plan_main".split()
repo_lists = [s.split() for s in """${repo_lists[@]+${repo_lists[@]/#/|}}""".split("|") if s.strip()]
url_of = {}
for i, lst in enumerate(repo_lists):
    for a in lst:
        url_of[a] = f"$PAGES_BASE/taxmap-tiles-{i+1}/tiles/{a}.pmtiles"
entries = []
for e in json.load(open(sys.argv[1])):
    name = e if isinstance(e, str) else e["name"]
    entries.append({"name": name, "url": url_of[name]} if name in url_of else name)
json.dump(entries, open(sys.argv[1], "w"), indent=2)
print("archives.json rewritten:", sum(1 for e in entries if isinstance(e, dict)), "remote entries")
PYEOF

echo "== rebuild app =="
(cd "$ROOT/web" && BASE_PATH=/taxmap/ npm run build >/dev/null 2>&1 && echo built)

echo "== stage repos under $SCRATCH =="
mkdir -p "$SCRATCH"
# main site
MAIN_DIR="$SCRATCH/ghpages-main"
if [ ! -d "$MAIN_DIR/.git" ]; then
  mkdir -p "$MAIN_DIR" && (cd "$MAIN_DIR" && git init -q -b gh-pages \
    && git remote add origin "https://github.com/$OWNER/taxmap.git" \
    && git config http.postBuffer 524288000)
fi
rsync -a --delete --exclude ".git" "$ROOT/web/dist/" "$MAIN_DIR/"
rm -rf "$MAIN_DIR/tiles"; mkdir -p "$MAIN_DIR/tiles"
for a in $plan_main; do cp "$WEB_TILES/$a.pmtiles" "$MAIN_DIR/tiles/"; done
touch "$MAIN_DIR/.nojekyll"

for i in "${!repo_lists[@]+"${!repo_lists[@]}"}"; do
  repo="taxmap-tiles-$((i + 1))"
  dir="$SCRATCH/ghpages-$repo"
  if [ ! -d "$dir/.git" ]; then
    mkdir -p "$dir" && (cd "$dir" && git init -q -b gh-pages \
      && git remote add origin "https://github.com/$OWNER/$repo.git" \
      && git config http.postBuffer 524288000)
  fi
  mkdir -p "$dir/tiles"
  for a in ${repo_lists[i]}; do cp "$WEB_TILES/$a.pmtiles" "$dir/tiles/"; done
  touch "$dir/.nojekyll"
  echo "Statewide tile shard $((i + 1)) for jgc514/taxmap" > "$dir/README.md"
done

if [ "$PUSH" != "--push" ]; then
  echo "DRY RUN staged. Re-run with --push to create repos, push, and enable Pages."
  exit 0
fi

echo "== push everything =="
for i in "${!repo_lists[@]+"${!repo_lists[@]}"}"; do
  repo="taxmap-tiles-$((i + 1))"
  gh repo view "$OWNER/$repo" >/dev/null 2>&1 || gh repo create "$OWNER/$repo" --public >/dev/null
  (cd "$SCRATCH/ghpages-$repo" && git add -A && git commit -q -m "Tiles shard" --allow-empty \
    && git push -q -f origin gh-pages)
  gh api -X POST "repos/$OWNER/$repo/pages" -f "source[branch]=gh-pages" -f "source[path]=/" >/dev/null 2>&1 \
    || echo "  (Pages already enabled for $repo)"
done
(cd "$MAIN_DIR" && git add -A && git commit -q -m "Deploy: statewide (254 counties)" && git push -q -f origin gh-pages)
echo "== pushed. Warm every archive URL after Pages finishes building =="
