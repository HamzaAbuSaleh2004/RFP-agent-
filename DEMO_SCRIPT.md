# Manager Demo — Full System Walkthrough
## Scenario: Saudi Arabia Cloud Migration RFP + Bid Evaluation

**Story:** Your company is migrating its infrastructure to the cloud and needs
Saudi Vision 2030-compliant vendors. You will issue an RFP, then evaluate three
real vendor bids — one healthy, one financially distressed, one with unverifiable claims.

**Tools exercised:** Drive search, Drive read, Firecrawl (SDAIA scrape),
FMP (3 vendor checks + 1 issuing company check), PDF generation, Drive upload,
Slack updates / legal / finance, Gmail, Notion, Linear, calculate_pwin, date_time.

---

## STEP 1 — Search past records
**Tools fired:** `gdrive_search`, root agent

Paste this into the chat:
```
Search our Google Drive for any past RFPs or cloud infrastructure documents we have on file.
```

**What to point out:**
- Director agent instantly calls `gdrive_search` without asking questions
- Returns real file names, links, and last-modified dates from your Drive
- Shows the system can retrieve institutional memory before drafting anything new

---

## STEP 2 — Create the RFP
**Tools fired:** `firecrawl_scrape` (SDAIA), `fmp_get_financials` (issuing co),
`gdrive_search`, `gdrive_read_file` (template), `notion_search_pages`,
`date_time`, `create_rfp_pdf`, Drive upload, `slack_post_message` (updates channel)

Paste this into the chat — **all in one message:**
```
I need to create a new RFP. Here are all the details:

- What we are procuring: Cloud infrastructure migration — moving our on-premise
  data center to a hybrid cloud setup (AWS + Azure). Includes storage, compute,
  disaster recovery, and a 24/7 managed services contract.
- Target country: Saudi Arabia (must comply with Vision 2030 and SDAIA data
  residency regulations — data cannot leave Saudi borders)
- Issuing company ticker: MSFT (use this to benchmark our budget expectations)
- Budget range: $2M–$5M USD
- Timeline: Project must be complete within 18 months. RFP submission deadline
  is 45 days from today.
- Vendor qualifications required: ISO 27001 certified, minimum 5 years cloud
  migration experience, local Saudi entity or licensed foreign branch.
- Evaluation weights: Technical 50%, Financial 30%, Legal compliance 20%.
- Point of contact: procurement@ourcompany.com
- Output filename: Saudi_Cloud_Migration_RFP_2026.pdf
```

**What to point out:**
1. **Firecrawl fires first** — agent scrapes the live SDAIA website
   (sdaia.gov.sa) to extract *current* data residency rules, not cached knowledge
2. **FMP fires** — pulls Microsoft's actual financials to benchmark the budget
3. **Drive template** — agent fetches your company template automatically,
   no manual upload needed
4. **PDF generated** — fully formatted with your company branding
5. **Slack fires** — updates channel (C0ASMLBU3TK) gets a message with the
   Drive link the moment upload completes

---

## STEP 3 — Evaluate the three bids
**Tools fired:** `gdrive_read_file` (if bids in Drive), `fmp_get_financials` x3,
`firecrawl_scrape` (vendor website), `calculate_pwin`, `code_execution`,
`slack_alert_legal` (financial distress flag), `slack_notify_finance` (final ranking),
`linear_create_issue`, `airtable_add_vendor_record`

Paste this into the chat — **all in one message:**
```
We received three bids for the Saudi Cloud Migration RFP. Please evaluate them
across all four dimensions (Legal, Commercial, Technical, Financial).

--- BID 1: Accenture ---
Ticker: ACN
Proposed price: $3.8M
Includes: Signed Standard Agreement (no redlines), COI statement attached,
ISO 27001 certificate provided, team of 12 certified cloud architects,
methodology doc attached (agile delivery, phased rollout), dedicated Saudi
Arabia office in Riyadh with 200 local staff.
Website to verify capabilities: https://www.accenture.com/us-en/services/cloud-index

--- BID 2: Unisys ---
Ticker: UIS
Proposed price: $2.1M (lowest bid)
Includes: Signed Standard Agreement, no COI statement, ISO 27001 certificate
provided but issued 2019 (not renewed), team of 4 engineers, no Saudi local
entity — proposes to operate via a third-party reseller. Methodology is generic,
not tailored to Vision 2030 requirements.

--- BID 3: DXC Technology ---
Ticker: DXC
Proposed price: $4.5M
Includes: COI statement attached, claims ISO 27001 + FedRAMP certifications,
team of 9 engineers. However, they request significant redlines to the Standard
Agreement (liability cap reduction from 100% to 10% of contract value, exclusion
of data breach penalties). Methodology is detailed and Vision 2030-aware.
Website to verify certifications: https://dxc.com/us/en/offerings/security

After evaluation, post the final ranking to our finance channel and flag any
legal or financial showstoppers to the legal channel immediately.
```

**What to point out — one beat at a time:**

1. **FMP fires for each vendor (3 calls):**
   - ACN: Healthy — passes financial dimension
   - UIS: Historically high debt load — may show financial risk flag ⚠
   - DXC: Check net margins — has had restructuring charges

2. **Firecrawl fires** — agent reads Accenture's actual cloud services page and
   DXC's security certifications page to cross-reference what they claimed

3. **Slack legal alert fires** — if Unisys triggers the cash-burn flag, a
   🚨 message hits the legal channel (C0ARWKER0G4) *before* the report is done

4. **calculate_pwin fires** — probability of win calculated per vendor

5. **code_execution fires** — weighted scoring model (50/30/20) calculated live

6. **Airtable + Linear fire** — vendor scores stored, tracking issue created

7. **Slack finance fires last** — ranked summary posted to finance channel
   (C0ASMA9B33J) the moment evaluation completes

---

## STEP 4 — Show the Slack channels (split screen or phone)

Open Slack alongside the browser. Show the manager:

| Channel | What landed there |
|---|---|
| #updates (C0ASMLBU3TK) | "RFP uploaded to Drive — link: …" |
| #legal (C0ARWKER0G4) | "🚨 Legal Alert — Unisys financial distress flag" |
| #finance (C0ASMA9B33J) | "💰 Bid ranking: 1. Accenture, 2. DXC, 3. Unisys (FAIL)" |

**Key message to manager:** The system didn't email a PDF and wait for someone
to read it. It routed the right information to the right people in real time —
legal gets the blocker, finance gets the ranking, procurement gets the Drive link.

---

## Talking points per tool

| Tool | What it proves |
|---|---|
| Firecrawl → SDAIA | Live regulatory intelligence, not stale training data |
| FMP → vendor financials | A vendor quoting $2.1M who's burning cash is a hidden risk. System catches it. |
| Drive template → PDF | Zero manual formatting — your branding is applied automatically |
| Slack 3-channel routing | Right information to the right person, not a single blast |
| Linear issue | Every evaluated bid becomes a trackable ticket |
| calculate_pwin | Quantifies win probability so procurement can prioritize negotiation |

---

## If something goes wrong live

| Symptom | Quick fix |
|---|---|
| Firecrawl returns "no content" | Try `https://sdaia.gov.sa/en/` in Step 2 instead; some pages block scrapers |
| FMP returns "No ticker found" | Pass the ticker directly (ACN / UIS / DXC) instead of the full name |
| Slack message not appearing | Check that the bot is invited to all 3 channels: `/invite @your-bot-name` |
| PDF upload fails | Drive link will still be returned locally — show the local PDF instead |
| Agent asks clarifying questions | Add "Do not ask clarifying questions, proceed immediately" to the prompt |
