# Launching the Darksteel Forge coming-soon site on the client's domain

Written 2026-10-01. The site is ALREADY live and hosted - https://zed0minat0r.github.io/darksteel-forge-soon/
Everything that had to be fixed before a real domain points at it is now fixed. What is left is the
DNS, one Web3Forms key, and the e-commerce decision at the bottom.

---

## 1. The email signup - BUILT, needs one key

`index.html` used to clear the box, print "You are on the list" and **discard the address**. It now
POSTs to Web3Forms, which emails darksteelforge@gmail.com:

    Subject: Darksteel Forge - someone wants to be notified
    buyer@example.com says: I want to be notified when you open your doors.

Reply-to is set to the customer, so hitting reply in Gmail answers them directly. Web3Forms was
picked over FormSubmit because FormSubmit injects adverts into the submission email.

**The one remaining gate:** `const NOTIFY_KEY = ""` near the bottom of `index.html`. Get the key at
web3forms.com with darksteelforge@gmail.com, paste it between the quotes, push. While it is blank
the form says "The list is not switched on yet. Email darksteelforge@gmail.com and we will add you."
rather than lying to a customer.

Verified 2026-10-01 against a stubbed `window.fetch`, all four paths:

| case | result |
|---|---|
| no key | "not switched on yet" message, **0 network calls**, input preserved |
| 200 `success:true` | "You are on the list", input cleared, button re-enabled |
| 401 | "That did not send. Try again, or email darksteelforge@gmail.com.", input preserved |
| network throw | same failure message, no unhandled rejection |

An offscreen honeypot checkbox (`name="botcheck"`) sits in the form. **It was posting `"on"`** - an
unchecked checkbox's `.value` is the string "on" regardless of state, and Web3Forms spam-rejects any
truthy botcheck, so every genuine signup would have been silently dropped. It reads `.checked` now.
That bug was invisible to every test that did not inspect the posted body.

## 2. The contact address - DONE

`hello@darksteelforge.gg` was invented and would have bounced. It is `darksteelforge@gmail.com`
everywhere now (Matt confirmed it 2026-10-01): the mailto on the page, the notify form's
destination, and both fallback messages in the form.

## 3. Page weight - DONE, 10.7 MB -> 2.64 MB

Matt: "anything we can do to optimize the site to load really well without sacrificing any of the
quality of the cards because I really like the way the cards all look." Nothing about the cards
changed visually.

The marquee now pulls from AVIF lanes sized to the device instead of the full-size WebP:

    img/a4   400px, crf32   2.4 MB   serves DPR < 2.5
    img/a6   600px, crf36   3.8 MB   serves DPR >= 2.5
    img/c    original WebP  9.3 MB   AVIF-less browsers, and every full-size viewer open

The lane is chosen at runtime from a 2x2 AVIF decode probe plus `devicePixelRatio`, NOT a
`<picture>` element - the marquee preloads with `new Image()`, which does no type negotiation, so
`<picture>` would have bought nothing. Opening a card still loads the full-size art.

Rebuild the lanes with `scripts/bake_avif.sh` after any change to `img/c`.

**ffmpeg's libaom AVIF encoder silently drops alpha.** The logo went 400 KB -> 32 KB and looked like
a win until `pix_fmt` came back `yuv420p`, which would have put a black box behind the cutout. The
logo is WebP with alpha (96 KB), checked by compositing over white AND black.

---

## THE DNS

**The domain is almost certainly `darksteelforgegames.com`** - found by WHOIS on 2026-10-01, not
told to us, so Matt confirms it before anything is typed. Registered at GoDaddy 2026-04-07, paid to
2029, on GoDaddy's own nameservers (ns09/ns10.domaincontrol.com), currently serving a GoDaddy parked
page. GitHub's IPs verified against GitHub's docs the same day.

### The live zone as it stands, read 2026-10-01

    A      @      13.248.243.5          GoDaddy parking
    A      @      76.223.105.230        GoDaddy parking
    CNAME  www    darksteelforgegames.com.
    MX     @      aspmx.l.google.com (1), alt1/alt2 (5), alt3/alt4 (10)
    TXT    @      google-site-verification=F54E6dd_...
    TXT    @      4843026616
    TXT    @      v=spf1 include:dc-aa8e722993._spfm.darksteelforgegames.com ~all
    NS     @      ns09.domaincontrol.com, ns10.domaincontrol.com

### LEAVE ALONE

**The five MX records and all three TXT records.** This domain has live Google Workspace email on
it. The MX records route it and the SPF TXT is what stops their outgoing mail being marked as spam.
Clearing the zone - the obvious move when repointing a parked domain - kills the client's email.
The NS records are what makes GoDaddy's DNS page work at all.

### DELETE

    A      @      13.248.243.5
    A      @      76.223.105.230

### ADD (or EDIT, for www)

    A      @      185.199.108.153
    A      @      185.199.109.153
    A      @      185.199.110.153
    A      @      185.199.111.153
    AAAA   @      2606:50c0:8000::153
    AAAA   @      2606:50c0:8001::153
    AAAA   @      2606:50c0:8002::153
    AAAA   @      2606:50c0:8003::153
    CNAME  www    zed0minat0r.github.io          (edit the existing www record, do not add a second)

A registrar with `ALIAS`/`ANAME` could use one record at the apex instead of the four A records.
GoDaddy does not offer it, so it is the four.

### THEN, in the repo

Settings -> Pages -> Custom domain -> `darksteelforgegames.com` -> Save. That writes a `CNAME` file
to the repo root. Wait for the certificate, then tick **Enforce HTTPS** - it can take up to 24h to
become available and it is not automatic.

### Verifying it worked

    dig +short A darksteelforgegames.com        # expect the four 185.199.x.153
    dig +short CNAME www.darksteelforgegames.com
    dig +short MX darksteelforgegames.com       # MUST still be the five Google ones
    curl -sI https://darksteelforgegames.com | head -1

The MX check is not optional. It is the one that catches the mistake that actually costs the client
something.

---

## HOSTING: WHY NOT VERCEL, AND WHEN IT CHANGES

Checked both platforms' terms on 2026-10-01 rather than assuming:

- **Vercel Hobby explicitly prohibits commercial use and client work.** This is a paid client
  engagement, so it would be Pro at $20/user/month, and Vercel enforces it. There is nothing a
  static holding page needs that justifies that.
- **GitHub Pages prohibits sites "primarily directed at facilitating commercial transactions".**
  A holding page with an email capture is not that, so it is within the rules.

**The real decision is the next one.** When the full site gets a shop, GitHub Pages bans e-commerce
outright and this has to move - Vercel Pro, or a commerce platform if they want real checkout. Tell
the client that is coming rather than discovering it when it blocks them.

**The two repos are separate and must stay that way** (see the darksteel-forge-site memory): this
one is `darksteel-forge-soon`, the full build is `darksteel-forge`. They go back to the full site
later. Pointing the domain here does not commit them to anything.
