# Launching the Darksteel Forge coming-soon site on the client's domain

Written 2026-10-01. The site is ALREADY live and hosted - https://zed0minat0r.github.io/darksteel-forge-soon/
This is a DNS job plus two things that have to be fixed before a real domain points at it.

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

## 2. `hello@darksteelforge.gg` is invented

Hardcoded at line ~495 and never verified. If the client's real domain differs it bounces, and even
if it matches, the mailbox has to exist. Replace with a real address before launch.

## 3. Page weight is 10.7 MB

9.3 MB of it is `img/c` card art. This is a DELIBERATE choice - Matt asked for "as high resolution
as possible" on 2026-09-29, which took the page from 4.7 MB to ~10 MB, and the marquee deliberately
does NOT lazy-load because he rejected that in September. It is over this project's own ~4 MB audit
bar. Fine on wifi, slow on a phone. Leave or re-bake at 400px - his call, not a defect.

GitHub Pages' limits are a 1 GB site cap and a 100 GB/month SOFT bandwidth limit, so ~10 MB a visit
is roughly 10,000 visits a month before anyone contacts us. Not a near-term concern.

---

## THE DNS, once the domain is known

Verified against GitHub's own docs 2026-10-01. Substitute the real domain.

**In the repo:** Settings -> Pages -> Custom domain -> enter the domain -> Save. That writes a
`CNAME` file. Then wait for the cert and tick **Enforce HTTPS** (can take up to 24h to become
available - it is not automatic).

**At the registrar**, for the apex (`darksteelforge.com` or whatever it is):

    A     @    185.199.108.153
    A     @    185.199.109.153
    A     @    185.199.110.153
    A     @    185.199.111.153
    AAAA  @    2606:50c0:8000::153
    AAAA  @    2606:50c0:8001::153
    AAAA  @    2606:50c0:8002::153
    AAAA  @    2606:50c0:8003::153

and for www:

    CNAME www  zed0minat0r.github.io.

A registrar that supports `ALIAS`/`ANAME` can use one of those at the apex instead of the four A
records.

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
