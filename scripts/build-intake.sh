#!/usr/bin/env bash
# Build the GLP questionnaire Next.js app and copy static files into Jekyll's intake/ folder.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUESTIONNAIRE="${GLP_QUESTIONNAIRE_DIR:-$ROOT/../Desktop/GLP Questionnaire}"
OUT="$ROOT/intake"

if [[ ! -d "$QUESTIONNAIRE" ]]; then
  echo "Questionnaire not found at: $QUESTIONNAIRE" >&2
  echo "Set GLP_QUESTIONNAIRE_DIR to the glp-questionnaire project root." >&2
  exit 1
fi

cd "$QUESTIONNAIRE"
npm ci
NEXT_PUBLIC_BASE_PATH=/intake npm run build

rm -rf "$OUT"
mkdir -p "$OUT"

# Next static export with basePath=/intake writes under out/intake/
if [[ -d "$QUESTIONNAIRE/out/intake" ]]; then
  cp -R "$QUESTIONNAIRE/out/intake/." "$OUT/"
else
  cp -R "$QUESTIONNAIRE/out/." "$OUT/"
fi

touch "$OUT/.nojekyll"

# GitHub Pages runs Jekyll, which excludes underscore-prefixed folders (e.g. _next).
# Rename assets so CSS/JS are published alongside index.html.
if [[ -d "$OUT/_next" ]]; then
  mv "$OUT/_next" "$OUT/next-static"
  while IFS= read -r -d '' file; do
    sed -i '' 's|/intake/_next/|/intake/next-static/|g' "$file"
    sed -i '' 's|/_next/|/next-static/|g' "$file"
  done < <(find "$OUT" -type f \( -name '*.html' -o -name '*.js' -o -name '*.txt' \) -print0)

  # Jekyll also drops individual files whose names start with _.
  build_id_dir="$(find "$OUT/next-static/static" -maxdepth 1 -mindepth 1 -type d ! -name chunks ! -name media | head -1)"
  if [[ -n "$build_id_dir" ]]; then
    for manifest in _buildManifest.js _clientMiddlewareManifest.js _ssgManifest.js; do
      if [[ -f "$build_id_dir/$manifest" ]]; then
        renamed="${manifest#_}"
        mv "$build_id_dir/$manifest" "$build_id_dir/$renamed"
        while IFS= read -r -d '' file; do
          sed -i '' "s|${manifest}|${renamed}|g" "$file"
        done < <(find "$OUT" -type f \( -name '*.html' -o -name '*.js' \) -print0)
      fi
    done
  fi
fi

# Drop Next internal RSC payloads and underscore 404 bundle (not needed on static host).
rm -rf "$OUT/_not-found" 2>/dev/null || true
find "$OUT" -type d -name '__next.*' -prune -o -type f -name '__next*.txt' -delete 2>/dev/null || true
find "$OUT" -type f -name 'index.txt' -delete 2>/dev/null || true

if [[ ! -d "$OUT/next-static" ]]; then
  echo "ERROR: intake/next-static missing after build." >&2
  exit 1
fi

echo "Intake static files written to $OUT"
