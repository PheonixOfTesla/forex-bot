#!/usr/bin/env bash
# Copy the game client into the site that serves it.
#
# Two things happen here, and the second is the reason this is a script rather
# than a cp. Paths are rewritten from /undertow/ to /games/molua/, and every
# script tag is stamped with the current commit.
#
# Without that stamp a deploy does not reach anybody. Vercel sends
# max-age=0, must-revalidate, which ought to be enough, but Safari on iOS holds
# on to subresources anyway - so players kept running yesterday's client and
# reporting bugs that had already been fixed. A URL that changes with the
# commit cannot be cached across a deploy.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-/workspace/clockwork-landing-page/games/molua}"
VER="$(git -C "$SRC" rev-parse --short HEAD)"

mkdir -p "$DEST"
for f in index.html village.js avatar.js islander.js voice.js sound.js config.js og.html turnaround.html scene-test.html GLTFLoader.js SPEC.md; do
  [ -f "$SRC/$f" ] || continue
  sed "s#/undertow/#/games/molua/#g" "$SRC/$f" > "$DEST/$f"
done
[ -f "$SRC/three.min.js" ] && cp "$SRC/three.min.js" "$DEST/three.min.js"

# Re-stamp the version on whatever the previous stamp was.
perl -pi -e "s{(<script src=\"/games/molua/[^\"?]+)(\?v=[^\"]*)?\"}{\$1?v=$VER\"}g" "$DEST/index.html"

echo "synced to $DEST at v=$VER"
grep -o 'src="/games/molua/[^"]*"' "$DEST/index.html" | head -8
