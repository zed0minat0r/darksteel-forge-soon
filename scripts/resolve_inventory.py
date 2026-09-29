#!/usr/bin/env python3
"""Resolve data/inventory.tsv (the shop's real stock list) to card images.

One source per game, each chosen because it actually answers:
  Magic      Scryfall
  Pokemon    TCGdex. NOT pokemontcg.io - it returns HTTP 500 most of the time
             and it is missing the 2025-26 sets this list leans on.
  One Piece  dotgg. Its card ids ARE the numbers on the stock list (OP13-028).
  Riftbound  dotgg, matched on <SET CODE>-<collector number>.

Writes data/resolved.json (every row, matched or not) so the misses are visible
and can be fixed by hand rather than silently dropped.
"""
import csv, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from difflib import get_close_matches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
os.makedirs(CACHE, exist_ok=True)
# Scryfall 400s without BOTH of these. Its error body says so outright; the
# same request through curl works because curl sends Accept: */* for you.
UA = {"User-Agent": "darksteel-forge-soon/1.0 (inventory art resolver)",
      "Accept": "application/json"}


def get(url, ttl=86400):
    key = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:] + ".json")
    if os.path.exists(key) and time.time() - os.path.getmtime(key) < ttl:
        return json.load(open(key))
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.loads(r.read().decode())
            json.dump(d, open(key, "w"))
            return d
        except Exception as e:
            if attempt == 2:
                print(f"  ! {url[:70]} -> {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Parenthetical qualifiers are the shop's own notes about the printing
# ("(SP)", "(Alternate Art)", "(JP)"), not part of the card name.
def base_name(name):
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


# ---------------------------------------------------------------- Magic
MTG_SETS = {
    "revised": "3ed", "dominaria": "dom", "brothers war": "bro",
    "lord of the rings": "ltr", "double masters 2xm": "2xm",
    "secret lair countdown kit slc": "slc", "urza s saga": "usg",
    "urza s destiny": "uds", "stronghold": "sth",
}
# Special treatments live in a different product than the main set.
MTG_ALT_SETS = {"ltr": ["ltr", "ltc"], "bro": ["bro", "brr"], "2xm": ["2xm"]}


def resolve_magic(row):
    name = base_name(row["name"])
    code = MTG_SETS.get(norm(row["set"]))
    num = row["number"].strip()
    if code and num:
        d = get(f"https://api.scryfall.com/cards/{code}/{num}")
        if d and d.get("object") == "card":
            return d
    for c in (MTG_ALT_SETS.get(code, [code]) if code else [None]):
        q = f'!"{name}"' + (f" set:{c}" if c else "")
        d = get("https://api.scryfall.com/cards/search?" + urllib.parse.urlencode(
            {"q": q, "unique": "prints", "order": "released"}))
        if d and d.get("data"):
            cards = d["data"]
            # Prefer the printing whose frame/treatment matches the note the
            # shop wrote in brackets - "(Borderless)", "(retro frame)".
            note = norm(row["name"])
            for kw, test in (
                ("borderless", lambda c: c.get("border_color") == "borderless"),
                ("retro", lambda c: "retro" in (c.get("frame_effects") or [])),
                ("showcase", lambda c: "showcase" in (c.get("frame_effects") or [])),
                ("serial", lambda c: bool(c.get("preview")) or "serialized" in (c.get("promo_types") or [])),
            ):
                if kw in note:
                    hit = [c for c in cards if test(c)]
                    if hit:
                        return hit[0]
            return cards[0]
    return None


def magic_image(d):
    u = d.get("image_uris") or (d.get("card_faces", [{}])[0].get("image_uris") or {})
    return u.get("png") or u.get("large")


# ---------------------------------------------------------------- Pokemon
# Set names on the stock list that no amount of fuzzy matching will reach,
# because the shop writes them the way collectors say them and TCGdex files them
# somewhere else entirely. (lang, set id).
PK_SET_ALIASES = {
    "base set unlimited": ("en", "base1"),      # "Unlimited" is a print run, not a set
    "sun moon promo": ("en", "smp"),            # SM Black Star Promos
    "wotc promo": ("en", "basep"),              # Wizards Black Star Promos, and 11/53 is its numbering
    "crown zenith galarian gallery": ("en", "swsh12.5gg"),
    "shiny treasure ex": ("ja", "sv4a"),        # JP-only set
    "mega dream ex": ("ja", "M2a"),             # JP-only; TCGdex has the card but no art (see report)
}

_pk_sets = {}


def pk_sets(lang="en"):
    if lang not in _pk_sets:
        _pk_sets[lang] = get(f"https://api.tcgdex.net/v2/{lang}/sets") or []
    return _pk_sets[lang]


def resolve_pokemon(row):
    want = norm(row["set"])
    lang, set_id = PK_SET_ALIASES.get(want, ("en", None))
    if not set_id:
        by_norm = {norm(s["name"]): s for s in pk_sets("en")}
        hit = by_norm.get(want)
        if not hit:
            m = get_close_matches(want, list(by_norm), 1, 0.72)
            hit = by_norm[m[0]] if m else None
        if not hit:
            return None
        set_id = hit["id"]
    d = get(f"https://api.tcgdex.net/v2/{lang}/sets/{set_id}")
    if not d:
        return None
    num = (row["number"].split("/")[0] or "").strip()
    cards = d.get("cards", [])
    for c in cards:
        if c["localId"].lower() == num.lower():
            return dict(c, _set_id=set_id, _lang=lang)
    for c in cards:  # 010 vs 10
        if re.sub(r"^0+", "", c["localId"].lower()) == re.sub(r"^0+", "", num.lower()):
            return dict(c, _set_id=set_id, _lang=lang)
    want_name = norm(base_name(row["name"]))
    for c in cards:
        if norm(c["name"]) == want_name:
            return dict(c, _set_id=set_id, _lang=lang)
    return None


def url_ok(u):
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200 and r.headers.get("Content-Type", "").startswith("image/")
    except Exception:
        return False


def pokemon_detail(c, set_id, lang):
    """The set listing only carries id/name/image, so pull the card itself for
    the things a viewer wants to show. Cached, so it is one request per card once."""
    d = get(f"https://api.tcgdex.net/v2/{lang}/cards/{c['id']}") or {}
    return {k: v for k, v in {
        "rarity": d.get("rarity"),
        "artist": d.get("illustrator"),
        "released": (d.get("set") or {}).get("releaseDate", "")[:4] or None,
        "type": d.get("category"),
        "hp": d.get("hp"),
        "text": "; ".join(a.get("name", "") for a in (d.get("attacks") or []))[:220] or None,
    }.items() if v}


def pokemon_image(c, set_id=None):
    if c.get("image"):
        return c["image"] + "/high.png"
    # TCGdex knows plenty of cards it has no art for (Galarian Gallery, most
    # JP-only sets). pokemontcg.io's IMAGE CDN is a separate host from its API
    # and still serves while that API is returning 500s, so it is worth a try.
    # Its set ids are TCGdex's with the dot spelled out: swsh12.5gg -> swsh12pt5gg.
    if set_id:
        u = f"https://images.pokemontcg.io/{set_id.replace('.', 'pt')}/{c['localId']}_hires.png"
        if url_ok(u):
            return u
    return None


# ---------------------------------------------------------------- dotgg
_dotgg = {}


def dotgg(game):
    if game not in _dotgg:
        d = get(f"https://api.dotgg.gg/cgfw/getcards?game={game}&mode=indexed")
        rows, names = (d or {}).get("data", []), (d or {}).get("names", [])
        idx = {n: i for i, n in enumerate(names)}
        _dotgg[game] = ([{k: (r[i] if i < len(r) else None) for k, i in idx.items()} for r in rows])
    return _dotgg[game]


def resolve_onepiece(row):
    num = row["number"].strip().upper()
    cards = dotgg("onepiece")
    exact = [c for c in cards if (c.get("id") or "").upper() == num]
    if exact:
        note = norm(row["name"])
        for kw in ("parallel", "alternate art", "sp", "tr"):
            if kw in note:
                pref = [c for c in exact if kw.split()[0] in norm(c.get("rarity") or "")]
                if pref:
                    return pref[0]
        return exact[0]
    want = norm(base_name(row["name"]))
    for c in cards:
        if norm(c.get("name")) == want:
            return c
    return None


RB_CODES = {"origins": "OGN", "vendetta": "VEN", "spiritforged": "SPF",
            "unleashed": "UNL", "proving grounds": "PRV"}


def resolve_riftbound(row):
    cards = dotgg("riftbound")
    code = RB_CODES.get(norm(row["set"]))
    num = (row["number"].split("/")[0] or "").strip().upper()
    if code and num:
        for c in cards:
            if (c.get("id") or "").upper() == f"{code}-{num}":
                return c
    want = norm(base_name(row["name"]).replace(" - ", " "))
    setn = norm(row["set"])
    cand = [c for c in cards if norm((c.get("name") or "").replace(" - ", " ")) == want
            and (not setn or norm(c.get("set_name") or "") == setn)]
    return cand[0] if cand else None


def magic_detail(c):
    return {k: v for k, v in {
        "rarity": (c.get("rarity") or "").title() or None,
        "artist": c.get("artist"),
        "released": (c.get("released_at") or "")[:4] or None,
        "type": c.get("type_line"),
        "cost": c.get("mana_cost") or None,
        "text": (c.get("oracle_text") or "")[:220] or None,
        "number": c.get("collector_number"),
    }.items() if v}


def onepiece_detail(c):
    return {k: v for k, v in {
        "rarity": c.get("rarity"),
        "type": c.get("cardType"),
        "color": c.get("Color"),
        "cost": c.get("Cost"),
        "power": c.get("Power"),
        "counter": c.get("Counter"),
        "trait": c.get("Type"),
        "text": (c.get("Effect") or "")[:220] or None,
    }.items() if v}


def riftbound_detail(c):
    tags = c.get("tags")
    return {k: v for k, v in {
        "rarity": c.get("rarity"),
        "type": ", ".join(c["type"]) if isinstance(c.get("type"), list) else c.get("type"),
        "color": ", ".join(c["color"]) if isinstance(c.get("color"), list) else c.get("color"),
        "cost": c.get("cost"),
        "might": c.get("might"),
        "trait": ", ".join(tags) if isinstance(tags, list) else tags,
        # Riftbound effect text carries :rb_energy_7: style icon tokens
        "text": re.sub(r"\s+", " ", re.sub(r":rb_[a-z0-9_]+:", "",
                       re.sub(r"<[^>]+>", " ", c.get("effect") or ""))).strip()[:220] or None,
    }.items() if v}


def dotgg_image(c, game):
    return c.get("image") or f"https://static.dotgg.gg/{game}/card/{c['id']}.webp"


# ---------------------------------------------------------------- run
def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data/inventory.tsv")), delimiter="\t"))
    out, misses = [], []
    for i, row in enumerate(rows, 1):
        cat = norm(row["category"])
        try:
            if cat.startswith("magic"):
                c = resolve_magic(row); img = magic_image(c) if c else None
                game, cid = "magic", (c or {}).get("id")
                det = magic_detail(c) if c else {}
            elif cat == "pokemon":
                c = resolve_pokemon(row); img = pokemon_image(c, (c or {}).get("_set_id")) if c else None
                game, cid = "pokemon", (c or {}).get("id")
                det = pokemon_detail(c, c.get("_set_id"), c.get("_lang", "en")) if c else {}
            elif cat == "one piece":
                c = resolve_onepiece(row); img = dotgg_image(c, "onepiece") if c else None
                game, cid = "onepiece", (c or {}).get("id")
                det = onepiece_detail(c) if c else {}
            elif cat == "riftbound":
                c = resolve_riftbound(row); img = dotgg_image(c, "riftbound") if c else None
                game, cid = "riftbound", (c or {}).get("id")
                det = riftbound_detail(c) if c else {}
            else:
                c, img, game, cid, det = None, None, cat, None, {}
        except Exception as e:
            print(f"  ! row {i} {row['name']}: {e}", file=sys.stderr)
            c, img, game, cid, det = None, None, cat, None, {}
        rec = dict(row, game=game, card_id=cid, src=img,
                   matched_name=(c or {}).get("name"), detail=det)
        out.append(rec)
        if not img:
            misses.append(rec)
        print(f"{i:3} {'OK ' if img else 'MISS'} {row['category'][:9]:9} {row['name'][:44]:44} -> {(c or {}).get('name') or ''}")
    json.dump(out, open(os.path.join(ROOT, "data/resolved.json"), "w"), indent=1)
    print(f"\nmatched {len(out)-len(misses)}/{len(out)}; {len(misses)} misses")
    for m in misses:
        why = "no artwork anywhere" if m.get("matched_name") else "card not found"
        print(f"  MISS  {m['category']} | {m['set']} | {m['name']} | {m['number']}  ({why})")


if __name__ == "__main__":
    main()
