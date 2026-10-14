# Knowledge Base Backlog

**What this file is:** your **reading and writing queue** — which wiki articles to open next, which topics still need a first draft, and what needs a human decision outside docs.

**Portal codebase:** `/Users/hirenbudhrani/Herd/portal.mogelijk.nl`

**How to clear `#write-doc` items:** draft a raw note → drop in `01_unprocessed/` → pipeline writes `02_wiki/<name>.md`.

**New entry shape** (Agents 4 and 5 both emit this format — see [agents/agent4-critic.md](../../agents/agent4-critic.md) and [agents/agent5-curator.md](../../agents/agent5-curator.md)):

```
- [ ] **<topic to look up>** — <why to look it up> — enriches: `02_wiki/<stem>.md`[, `02_wiki/<stem>.md`] #<tag>
```

Every gap names 1–3 EXISTING wiki articles it would enrich, so you know where the work lands. Tags: `#read-next` | `#write-doc` | `#decision` | `#code-gap` | `#mis-tier`. Historical entries below may use the older `**Read next:** ...` shape — that's fine, don't rewrite them.

---

## Read next (start here)

Study these **existing** wiki pages in order if you're onboarding to the portal KB:

| Priority | Open in Obsidian | Why |
|----------|------------------|-----|
| 1 | `02_wiki/module-structure.md` | How the Laravel app is organised — read before any module doc |
| 2 | `02_wiki/signing-flows-legacy.md` | Production signing today (four parallel systems) |
| 3 | `02_wiki/signings-technical-reference.md` | UnifiedSigning target architecture + what's built vs planned |
| 4 | `02_wiki/signicat-integration.md` | Signicat paths, service desk, iDIN/handwritten/itsme |
| 5 | `02_wiki/gocredible-mbi-integration.md` | Payment / mandate provider integration |
| 6 | `02_wiki/digital-mandate-system.md` | GoCredible webhook mandate flow |
| 7 | `02_wiki/onfido-integration.md` | KYC / identity verification |
| 8 | `02_wiki/quickscan-lead-approval-flow.md` | QS → VGS approval (common service desk hallway) |
| 9 | `02_wiki/invoices-p2p.md` | P2P brokerage/closing fees → AccountView |
| 10 | `02_wiki/interest-rate-engine.md` | How `interest_quickscanner` vs `interest_to_pay` works |

**Signing deep-dive bundle (if you're on Unified Signing work):**  
`signings-research-ticket.md` → `signings-project-plan.md` → `signings-tickets.md` → `sepa-mandate-system.md`

**GoCredible ops bundle:**  
`GoCredible_Consolidated_Documentation.md` → `gocredible-service-desk-runbook.md`

---

## Write next (no wiki page yet)

Author these, then run the pipeline:

| Wiki to create | Start in portal | Read first (context) |
|----------------|-----------------|----------------------|
| **UnifiedSigning overview** | `app/Modules/UnifiedSigning/`, `tests/Modules/UnifiedSigning/` | `signings-technical-reference.md`, `signicat-integration.md` |
| **AccountView integration** | `app/Jobs/AccountView/`, `InvoiceToAv` job | `invoices-p2p.md`, `gocredible-mbi-integration.md` |
| **Authentication & permissions** | GraphQL `@guard`, `@canAccess`, `config/auth.php` | `graphql-guide.md`, `module-structure.md` |
| **Fund registration & KYC gate** | grep `onfido_check`, `FundRegistration` | `onfido-integration.md` |
| **KYC questionnaire** | `KycQuestionnaireService`, Onfido job hooks | `onfido-integration.md` |
| **Document generator / PdfTemplates** | `app/Modules/Documents/` | `sepa-mandate-system.md` (SEPA templates) |
| **Property management overview** | `app/Modules/Properties/`, `PropertyObserver` | `quickscan-lead-approval-flow.md`, `autolane.md` |
| **P2P onboarding signing (System D)** | `app/Modules/Signings/`, `ContextService` | `signing-flows-legacy.md` § System D |

---

## Waiting on you

### Product / legal decisions

- [ ] **SEPA + definitive offer on Signicat** — Replace BTL/CRE canvas signing with bundled Signicat (offer + SEPA)? `#decision`  
  Read: `02_wiki/sepa-mandate-system.md` (Open Vragen), MGT-8185

- [ ] **Send SEPA PDF to bank after CORE signing?** — Should `SepaMandateToBank` run in the new BTL/CRE flow? `#decision`  
  Portal: `app/Mail/People/SepaMandateToBank.php`

- [ ] **Unified Signing cutover vs backfill** — Freeze legacy rows or migrate history? `#decision`  
  Read: `02_wiki/signings-project-plan.md`, `02_wiki/signings-research-ticket.md`

- [ ] **Research ticket matrix sign-off** — Colleague validation still pending. `#decision`  
  Read: `02_wiki/signings-research-ticket.md`

- [ ] **Notary portal pass-date guard** — Confirm when CMS feature ships. `#decision`  
  Read: `02_wiki/NOTARY_PORTAL_TASK.md`

- [ ] **Notary factsheet (MGT-6083)** — External dependency, no vault doc yet. `#write-doc`

- [ ] **MBI API contract** — Lives outside vault (Confluence/vendor). `#write-doc` or link in frontmatter

- [ ] **Investigation-playbook frontmatter type** — Extend pipeline types or map to `reference`? `#decision`  
  Read: `02_wiki/documentation-guidelines.md`

### Code not built (engineering backlog — docs already describe the gap)

- [ ] **P2P invoice auto-credit on claim withdrawal** `#code-gap`  
  Read: `02_wiki/invoices-p2p.md` — `ClaimService::deleteClaim()`, `PropertyObserver::handleInvoices()`

- [ ] **SEPA bundled signing (MGT-8185)** `#code-gap`  
  Read: `02_wiki/sepa-mandate-system.md` — PDF templates exist; `SepaMandateService` / bundling do not

- [ ] **SEPA customer mailable + CMS template** `#code-gap`  
  Read: `02_wiki/sepa-mandate-system.md` roadmap table

- [ ] **Signicat Path B status polling** `#code-gap`  
  Read: `02_wiki/signicat-integration.md` — `SignController`, `CreateSignOrder`

- [ ] **Notary portal GraphQL** `#code-gap`  
  Read: `02_wiki/NOTARY_PORTAL_TASK.md` — schema not in repo yet

- [ ] **UnifiedSigning product adapters** `#code-gap`  
  Core module + `sign_requests` DB exist; `PropertySignableSubject` / `PropertyBundleBuilder` + CMS wiring do not  
  Read: `02_wiki/signings-technical-reference.md`, `02_wiki/signings-tickets.md`

---

## Fixed for you (2026-07-16, continued)

- **All 24 wiki articles** — translated to English; phantom `[[links]]` removed (0 broken links remain). Only cross-links between existing files use `[[filename-stem|Display]]`.
- **Agent 2 / 4 / 5 prompts** — English-only structurer; no phantom links; Curator links by filename stem only.

Wiki corrections applied directly against `portal.mogelijk.nl` — no re-run needed unless you want archive/raw notes synced:

| Wiki | Fix |
|------|-----|
| `digital-mandate-system.md` | Webhook payload → `bo_entity_type` / `bo_entity_id`; route cited; line ref → ~L569; removed stale UNVERIFIED callouts |
| `property-update-mutation.md` | Removed false audit-logging claim; added schema/resolver paths |
| `onfido-integration.md` | Documented `invalidateOverruleIfFailedFlags()` |
| `invoices-p2p.md` | Credit fallback notes trashed-claim guard in `InvoiceService` |
| `sepa-mandate-system.md` | MGT-8185 marked planned (not done); file map labelled planned |
| `signings-technical-reference.md` | `sign_requests` tables exist; product adapters still TODO |
| `signings-tickets.md` / `signings-research-ticket.md` | Same persistence correction |
| `mail-templates-guide.md` | Linked `dragonfly/docs/mail-templates.md` |

**Agent 4 prompt updated:** `agents/agent4-critic.md` — backlog entries must be English, name the next article, use `#read-next` / `#write-doc` / `#decision` / `#code-gap`.

---

## Resolved

- [x] Missing wiki pages from first pipeline run (Signicat, Onfido, Digital Mandate, Module structure, etc.) — all in `02_wiki/` now
- [x] HTML companion files — archived under `03_meta/archive/` (not wiki pages)
