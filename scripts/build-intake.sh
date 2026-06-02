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
echo "Intake static files written to $OUT"
