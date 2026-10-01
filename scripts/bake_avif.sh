#!/bin/bash
# Re-bake the card art as AVIF at two widths, so the page loads fast WITHOUT any visible loss.
#
# Matt, 2026-10-01: "Is there anything we can do to optimize the site to load really well without
# sacrificing any of the quality of the cards because I really like the way the cards all look"
#
# MEASURED, not assumed, on magic-0e94d334 (a dense full-art card):
#     600px WebP q78  (what ships today)   112 KB
#     600px AVIF crf36                      40 KB   <- indistinguishable at 1:1
#     400px AVIF crf32                      28 KB   <- indistinguishable at the size a 2x phone shows
# Compared by decoding both back to PNG and cropping the SAME detail region, including the tiny
# rules text. "When Chrome Mox enters the battlefield" is equally legible in all three.
#
# WHY TWO WIDTHS. `.lane figure` is clamp(158px, 42vw, 200px), so a card is drawn 158-200 CSS px
# wide. 600px is only needed by a 3x display. srcset hands a 1x/2x device the 400px file, which is
# 1:1 or better on its screen - that is not a quality reduction, it is not sending pixels the
# screen cannot draw.
#
# The WebP files STAY as the <img src> fallback inside <picture>, so a browser without AVIF is
# unaffected. Nothing is deleted.
set -euo pipefail
cd "$(dirname "$0")/.."
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
mkdir -p img/a6 img/a4
n=0
for f in img/c/*.webp; do
  b=$(basename "$f" .webp)
  [ -f "img/a6/$b.avif" ] || "$FF" -v error -i "$f" -c:v libaom-av1 -crf 36 -cpu-used 6 -still-picture 1 -f avif "img/a6/$b.avif" -y
  [ -f "img/a4/$b.avif" ] || "$FF" -v error -i "$f" -vf scale=400:-1 -c:v libaom-av1 -crf 32 -cpu-used 6 -still-picture 1 -f avif "img/a4/$b.avif" -y
  n=$((n+1)); printf "\r  %d/%d" "$n" "$(ls img/c/*.webp | wc -l | tr -d ' ')"
done
echo
echo "webp 600 : $(du -sh img/c | cut -f1)"
echo "avif 600 : $(du -sh img/a6 | cut -f1)"
echo "avif 400 : $(du -sh img/a4 | cut -f1)"
