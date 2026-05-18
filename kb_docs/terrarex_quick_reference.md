# Terra Rex Energy — Quick Reference (Authoritative Numbers)

This file is the single source of truth for every quantitative answer
the chatbot is allowed to give. If a price, percentage, timeline, or
warranty period is not listed here (or in the main training docs),
the bot must say "let me check with our team" rather than guess.

---

## 1. Panel pricing (3 kW base, Terra Rex official)

| Brand | On-Grid (3 kW) | Hybrid (3 kW) | Per-kW On-Grid | Per-kW Hybrid |
|---|---|---|---|---|
| Tata Solar | ₹1,90,000 | ₹2,60,000 | ₹63,333 | ₹86,667 |
| Waaree | ₹1,80,000 | ₹2,40,000 | ₹60,000 | ₹80,000 |
| Loom Solar | ₹1,60,000 | ₹2,00,000 | ₹53,333 | ₹66,667 |

Price formula for sizes > 3 kW: `(per-kW rate) × required kW`.

## 2. Subsidy slabs (PM Surya Ghar + state)

| Size | Central | State | Total | Eligible system |
|---|---|---|---|---|
| 1 kW | ₹30,000 | ₹15,000 | ₹45,000 | On-Grid, Hybrid |
| 2 kW | ₹60,000 | ₹30,000 | ₹90,000 | On-Grid, Hybrid |
| 3 kW + | ₹78,000 | ₹30,000 | ₹1,08,000 | On-Grid, Hybrid |

- Cap: ₹1,08,000 for all systems ≥ 3 kW (same for 5 kW, 10 kW, etc.).
- Off-Grid: zero subsidy.
- Disbursal: within 30 days of installation, directly to the bank
  account on file.

## 3. Recommended size by monthly bill

| Monthly bill | Size | Est. monthly savings |
|---|---|---|
| ₹500 – 1,500 | 1 kW | ₹800 – 1,200 |
| ₹1,500 – 3,000 | 2 kW | ₹1,500 – 2,500 |
| ₹3,000 – 5,000 | 3 kW | ₹2,500 – 4,000 |
| ₹5,000 – 8,000 | 4–5 kW | ₹4,000 – 6,500 |
| ₹8,000 – 15,000 | 6–8 kW | ₹6,000 – 12,000 |
| ₹15,000+ | 10 kW+ | ₹12,000+ |

DISCOM rule: plant size capped at the customer's Sanctioned Load.

## 4. Financing

| Feature | Value |
|---|---|
| Zero Down Payment | Available on systems up to ₹2,00,000 |
| Banking partners | SBI, HDFC, Bajaj Finserv |
| Loan disbursal | Within 48 hours |
| EMI starts at | ₹899/month (10-year tenure) |
| Loan paperwork | Free, handled by Terra Rex |

## 5. AMC plans

| Plan | Annual fee | Preventive visits | Monitoring | Uptime |
|---|---|---|---|---|
| Basic | ₹2,500 | 2/yr | — | — |
| Standard | ₹4,500 | 4/yr | Yes | — |
| Premium | ₹7,500 | Unlimited | 24×7 | 98%+ |

First year's maintenance is usually bundled with the install package.

## 6. Warranty

- Panels: 25-year performance (≥80% output at year 25).
- Inverter: 5 years.
- Mounting structure: 5–10 years.
- Installation workmanship: 1 year.
- Plus 5 years of free service from Terra Rex.

## 7. System-type decision matrix

| Situation | Recommendation |
|---|---|
| Cuts < 2 hrs/day, stable grid | On-Grid |
| Cuts 3–4+ hrs/day | Hybrid |
| Office/business, downtime hurts | Hybrid |
| Very tight budget | On-Grid + Loom Solar |
| Remote, no grid | Off-Grid (no subsidy) |
| Max savings, subsidy-eligible | On-Grid + Waaree |

## 8. Required documents

For subsidy (5 items):
1. Aadhaar card
2. PAN card
3. Latest electricity bill (DISCOM)
4. Bank passbook
5. GPS-tagged rooftop photo

For loan (5 items):
1. Aadhaar card
2. PAN card
3. Last 3 months' salary slips or ITR
4. 6-month bank statement
5. Latest electricity bill

## 9. Pre-calculated examples

| System | Gross | Subsidy | Net | EMI (10y) |
|---|---|---|---|---|
| 3 kW On-Grid Tata | ₹1,90,000 | ₹1,08,000 | ₹82,000 | ~₹800/mo |
| 3 kW Hybrid Waaree | ₹2,40,000 | ₹1,08,000 | ₹1,32,000 | ~₹1,300/mo |
| 5 kW On-Grid Tata | ₹3,16,665 | ₹1,08,000 | ₹2,08,665 | ~₹2,100/mo |
| 5 kW Hybrid Waaree | ₹4,00,000 | ₹1,08,000 | ₹2,92,000 | ~₹2,900/mo |
| 7 kW Hybrid Waaree | ₹5,60,000 | ₹1,08,000 | ₹4,52,000 | ~₹4,500/mo |
| 10 kW On-Grid Loom | ₹5,33,330 | ₹1,08,000 | ₹4,25,330 | ~₹4,200/mo |

EMI figures are indicative; final EMI depends on bank, tenure, and
applicant profile.
