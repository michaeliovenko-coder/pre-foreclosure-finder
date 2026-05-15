# Business Idea Log

> Auto-generated every ~4 hours. Each entry decides whether to build on prior ideas or branch off.
> Token budget cap: ~$50 total. Ask user permission before continuing past that threshold.

---

## Idea #1 — 2026-05-15

**Decision: BUILD UPON existing project** — The repo already contains a working Pre-Foreclosure Assumable Mortgage Finder (Streamlit). The fastest path to revenue is packaging what already exists into a paid product rather than starting from scratch.

---

### AssumeAlert — Assumable Mortgage Deal Intelligence, Delivered Daily

**One-liner:** A subscription service that emails real estate investors a curated daily digest of profitable pre-foreclosure listings with assumable mortgages in their target markets.

---

#### Why Now (Market Opportunity)

- Millions of U.S. homes carry 2020–2022 mortgages locked at 3–4%. With 2026 rates still elevated (6–7%), an assumable mortgage can save a buyer $700–$1,500/month vs. new financing.
- Pre-foreclosure inventory is rising as pandemic-era forbearance effects fully unwind.
- Real estate investors on BiggerPockets, Reddit r/realestateinvesting, and Facebook groups are actively hunting assumable deals but have no automated tool.
- The working Streamlit app already does the hard part — data fetching + scoring. The business is a thin wrapper around it.

---

#### Startup Cost Breakdown

| Item | Cost |
|------|------|
| LLC formation (state filing) | $150–$500 |
| Domain + email (Namecheap + Zoho) | $50/yr |
| Hosting — Railway or Render (hobby tier to start) | $0–$25/mo |
| Email delivery — Resend or Mailchimp (free up to 3k/mo) | $0 free tier |
| County record / MLS data access (ATTOM Data API entry tier) | $2,000–$4,000/yr |
| Landing page (Carrd or Framer) | $0–$19/mo |
| Paid marketing — Google/Reddit ads for first 90 days | $2,000 |
| CPA/legal review | $500 |
| **Total** | **~$7,000–$10,000** |

---

#### Revenue Model

- **$79/month** per subscriber (solo investor)
- **$199/month** team plan (small RE firm, 5 users)
- Break-even: ~90 solo subscribers
- Month-6 target: 200 subscribers → ~$15,800 MRR

---

#### Build Path (using existing code)

1. Add a user-selectable region/zip filter to the existing Streamlit fetcher
2. Add a scheduled job (cron on Railway) that runs the analyzer daily and formats top-10 results
3. Pipe output into Resend email template
4. Wire Stripe Checkout for subscriptions
5. Launch on BiggerPockets forums + Reddit r/realestateinvesting

---

#### Risks

- ATTOM/county data costs can spike if volume grows
- MLS data access rules vary by state (may need a licensed agent partner in some markets)
- Market risk: if rates drop sharply, assumable mortgage premium disappears

---

**Estimated time to first paying customer:** 4–6 weeks (code already ~60% done)

---

*Next session will decide: go deeper on AssumeAlert (e.g., add a wholesale deal marketplace layer) or branch off to a new space.*

---

## Token Usage Tracker

| Session | Date | Ideas Generated | Approx Tokens Used |
|---------|------|-----------------|--------------------|
| 1 | 2026-05-15 | Idea #1 | ~2,500 |
| **Total** | | | **~2,500 / ~150,000 cap (~$50)** |
