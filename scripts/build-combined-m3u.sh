#!/usr/bin/env bash
set -euo pipefail

echo "=== BUILD COMBINED M3U ==="

MY_PLAYLIST="custom2/my.m3u"
OUT_PLAYLIST="custom2/combined.m3u"

UPSTREAM_URLS=(
  "https://iptv-org.github.io/iptv/index.m3u"
  "https://iptv-org.gitlab.io/iptv/index.m3u"
)

mkdir -p custom2

TMP="$(mktemp)"
COMBINED_TMP="$(mktemp custom2/.combined.XXXXXX)"
trap 'rm -f "$TMP" "$COMBINED_TMP"' EXIT
echo "Temp file: $TMP"

FOUND=0
for URL in "${UPSTREAM_URLS[@]}"; do
  echo "Trying upstream: $URL"
  if curl -L --fail --silent --show-error --connect-timeout 10 --max-time 120 --retry 2 "$URL" -o "$TMP" && python3 scripts/validate-custom-playlist.py "$TMP"; then
    FOUND=1
    echo "Upstream OK: $URL"
    break
  else
    echo "Failed: $URL"
  fi
done

if [[ "$FOUND" -ne 1 ]]; then
  echo "ERROR: No upstream playlist could be downloaded"
  exit 1
fi

if [[ ! -s "$TMP" ]]; then
  echo "ERROR: Upstream playlist is empty"
  exit 1
fi

echo "Upstream size:"
wc -l "$TMP"

echo "Building combined playlist…"

{
  echo "#EXTM3U"
  sed '1{/^#EXTM3U/d}' "$TMP"
  echo ""
  if [[ -f "$MY_PLAYLIST" ]]; then
    echo "Including $MY_PLAYLIST" >&2
    python3 scripts/validate-custom-playlist.py "$MY_PLAYLIST" >&2
    sed '1{/^#EXTM3U/d}' "$MY_PLAYLIST"
  else
    echo "# custom2/my.m3u not found"
  fi
} > "$COMBINED_TMP"

echo "Combined draft created (pre-fix):"
wc -l "$COMBINED_TMP"

echo "Converting viamotion DASH (.mpd) to HLS8 (.m3u8) when available…"

# Extract unique viamotion DASH URLs
mapfile -t DASH_URLS < <(grep -Eo 'https://viamotionhsi\.netplus\.ch/live/eds/[^ ]+/browser-dash/[^ ]+\.mpd' "$COMBINED_TMP" | sort -u || true)

echo "Found ${#DASH_URLS[@]} viamotion DASH URL(s)"

# Replace in the combined temp (only if HLS exists)
for u in "${DASH_URLS[@]}"; do
  hls="${u/browser-dash/browser-HLS8}"
  hls="${hls%.mpd}.m3u8"

  # HEAD first, fallback to GET if needed
  if curl -fsSI --max-time 8 "$hls" >/dev/null 2>&1 || curl -fsS --max-time 8 -o /dev/null "$hls" >/dev/null 2>&1; then
    # Replace all occurrences
    python3 - "$COMBINED_TMP" "$u" "$hls" <<'PY_REPLACE'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text().replace(sys.argv[2], sys.argv[3]))
PY_REPLACE
    echo "OK  : $u -> $hls"
  else
    echo "SKIP: $u (HLS not found)"
  fi
done

# Validate before replacing the last working playlist.
python3 scripts/validate-custom-playlist.py "$COMBINED_TMP"

# Write final output
mv "$COMBINED_TMP" "$OUT_PLAYLIST"

echo "Combined playlist created:"
ls -la custom2
wc -l "$OUT_PLAYLIST"

echo "=== DONE ==="
