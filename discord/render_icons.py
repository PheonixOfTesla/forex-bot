"""Render brand/*.svg to the raster sizes Discord actually accepts.

Discord takes PNG/GIF/JPG/WEBP and rejects SVG on every upload surface --
app icon, server icon, custom emoji, role icon. So the SVGs are the source
of truth in this repo and the PNGs are build output.

    pip install cairosvg
    python render_icons.py

Writes brand/png/. Sizes come from Discord's own guidance:
  app icon     1024x1024   developer portal, manual upload
  server icon   512x512    PATCH /guilds/{id}
  emoji         128x128    max 256 KB, so this warns if one runs over
"""

from pathlib import Path

import cairosvg

BRAND = Path(__file__).parent / "brand"
OUT = BRAND / "png"

# (source, output name, pixel size)
TARGETS = [
    ("logo.svg", "app-icon-1024.png",   1024),
    ("logo.svg", "server-icon-512.png",  512),
    ("logo.svg", "logo-256.png",         256),
    ("emoji-bolt.svg",   "emoji-bolt.png",   128),
    ("emoji-long.svg",   "emoji-long.png",   128),
    ("emoji-short.svg",  "emoji-short.png",  128),
    ("emoji-funded.svg", "emoji-funded.png", 128),
]

EMOJI_MAX_BYTES = 256 * 1024


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    over = []

    for src_name, out_name, size in TARGETS:
        src = BRAND / src_name
        if not src.exists():
            print(f"  ! missing {src_name}, skipping")
            continue

        dest = OUT / out_name
        cairosvg.svg2png(
            url=str(src),
            write_to=str(dest),
            output_width=size,
            output_height=size,
        )
        kb = dest.stat().st_size / 1024
        flag = ""
        if out_name.startswith("emoji-") and dest.stat().st_size > EMOJI_MAX_BYTES:
            flag = "  <-- OVER Discord's 256 KB emoji limit"
            over.append(out_name)
        print(f"  + {out_name:<24} {size:>4}px  {kb:6.1f} KB{flag}")

    print(f"\nWrote {len(TARGETS)} files to {OUT}")
    if over:
        print("Shrink these before uploading: " + ", ".join(over))


if __name__ == "__main__":
    main()
