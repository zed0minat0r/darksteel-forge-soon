#!/usr/bin/env python3
"""Download the resolved card art and bake it to the size the marquee draws.

The lane caps a card at 200px wide (index.html .lane figure), so 400px covers a
2x screen and anything beyond that is weight for nothing. The previous art was
baked at 480x670 and ran 80-148 KB a card; at ~100 cards that would have been a
10 MB page.

Encodes WebP with cwebp - less than half the bytes of JPEG at a quality that is
indistinguishable at 200px (checked side by side, not assumed): 36 KB against
84 KB a card. Falls back to sips/JPEG if cwebp is not installed. No PIL or
ImageMagick on this machine; sips is the fallback because it ships with macOS
and reads the webp dotgg serves.
"""
import json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img", "c")
# THE SHOP'S OWN PHOTOS WIN. Bandai stamps SAMPLE across every One Piece image
# it publishes - checked against dotgg, Limitless, TCGplayer and Bandai's own EN
# and JP card lists, and it is on all of them, so no API gets around it. The way
# around it is a photo of the actual card, which the shop has because they own
# the stock. Drop a file in img/own/ named after the card number (ST32-002.jpg,
# OP02-004.png) and it is used instead of the official art.
OWN = os.path.join(ROOT, "img", "own")
RAW = os.path.join(ROOT, ".cache", "raw")
# The lane draws a card at 200px, so 600 is crisp on a 3x phone and past the
# point any screen can resolve. Native (745) was measured too: it triples the
# bytes for detail nothing displays.
#   400px q72  35 KB a card   ~3 MB   crisp to 2x
#   600px q78  92 KB a card   ~8 MB   crisp to 3x   <- here
#   native q80 209 KB a card ~19 MB   invisible past 3x
WIDTH, QUALITY = 600, 78
HAVE_CWEBP = subprocess.run(["which", "cwebp"], capture_output=True).returncode == 0
EXT = ".webp" if HAVE_CWEBP else ".jpg"
UA = {"User-Agent": "darksteel-forge-soon/1.0", "Accept": "image/*,*/*"}
os.makedirs(OUT, exist_ok=True)
os.makedirs(OWN, exist_ok=True)
os.makedirs(RAW, exist_ok=True)


def slug(rec):
    return re.sub(r"[^a-z0-9]+", "-", f"{rec['game']}-{rec['card_id']}".lower()).strip("-")


def bake(rec):
    s = slug(rec)
    dest = os.path.join(OUT, s + EXT)
    if os.path.exists(dest) and os.path.getsize(dest) > 4000:
        return s, os.path.getsize(dest), None
    own = None
    for e in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
        cand = os.path.join(OWN, (rec.get("number") or "").strip() + e)
        if (rec.get("number") or "").strip() and os.path.exists(cand):
            own = cand
            break
    ext = os.path.splitext(rec["src"].split("?")[0])[1] or ".png"
    raw = own or os.path.join(RAW, s + ext)
    try:
        if not own and (not os.path.exists(raw) or os.path.getsize(raw) < 2000):
            req = urllib.request.Request(rec["src"], headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(raw, "wb") as f:
                f.write(r.read())
        # -resize W 0 upscales a smaller source, which invents detail. Only
        # resize when the source is actually wider than the cap.
        src_w = 0
        try:
            out = subprocess.run(["sips", "-g", "pixelWidth", raw],
                                 capture_output=True, text=True).stdout
            src_w = int(re.search(r"pixelWidth:\s*(\d+)", out).group(1))
        except Exception:
            pass
        resize = ["-resize", str(WIDTH), "0"] if src_w > WIDTH else []
        if HAVE_CWEBP:
            subprocess.run(["cwebp", "-quiet", "-q", str(QUALITY)] + resize + [raw, "-o", dest],
                           check=True, capture_output=True)
        else:
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(QUALITY),
                 "-Z", str(int(WIDTH * 88 / 63)), raw, "--out", dest],
                check=True, capture_output=True)
        return s, os.path.getsize(dest), None
    except Exception as e:
        return s, 0, f"{rec['name']}: {str(e)[:110]}"


def main():
    recs = json.load(open(os.path.join(ROOT, "data/resolved.json")))
    have = [r for r in recs if r.get("src")]
    # Held back from the carousel, not from the stock list. Bandai's published
    # art for this one has SAMPLE across it in letters you cannot miss at any
    # size; the rest of the marked cards read as foil texture at 200px. Drop a
    # photo into img/own/P-110.jpg and delete this line to put it back.
    HOLD = {"P-110"}
    held = [r for r in have if (r.get("number") or "").strip() in HOLD]
    have = [r for r in have if (r.get("number") or "").strip() not in HOLD]
    for r in held:
        print(f"  HELD {r['number']} {r['name']} - watermark too loud, needs a real photo")
    # One card can be on the stock list twice; the carousel shows it once.
    seen, uniq = set(), []
    for r in have:
        k = (r["game"], r["card_id"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    print(f"{len(recs)} rows, {len(have)} with art, {len(uniq)} unique cards")

    errs, total = [], 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for s, size, err in ex.map(bake, uniq):
            if err:
                errs.append(err)
            total += size
    # Round-robin the games so each lane reads as a mixed case rather than 31
    # Magic cards in a row - the stock list is grouped by game, the shelf is not.
    by_game = {}
    for r in uniq:
        by_game.setdefault(r["game"], []).append(r)
    mixed, order = [], sorted(by_game, key=lambda g: -len(by_game[g]))
    while any(by_game.values()):
        for g in order:
            if by_game[g]:
                mixed.append(by_game[g].pop(0))
    uniq = mixed

    cards = []
    for r in uniq:
        f = os.path.join(OUT, slug(r) + EXT)
        if os.path.exists(f) and os.path.getsize(f) > 4000:
            cards.append({"name": r["name"], "set": r["set"],
                          "game": r["game"], "img": f"img/c/{slug(r)}{EXT}"})
    json.dump(cards, open(os.path.join(ROOT, "cards.json"), "w"), indent=1)
    print(f"baked {len(cards)} cards, {total/1e6:.2f} MB total, "
          f"avg {total/max(len(cards),1)/1000:.0f} KB")
    for e in errs:
        print("  ERR", e)


if __name__ == "__main__":
    main()
