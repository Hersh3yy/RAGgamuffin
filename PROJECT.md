<!--
  PROJECT.md — the cockpit for this repo. One file to open and know where things stand.
  Maintained by the `project-map` skill. The assessment (status/issues/roadmap) is
  refreshed each session; the Diary at the bottom only grows. App-code changes need a
  green light; the trunk is merged to only when sure.
  Keep the section order and headings identical across every project.
-->

# RAGgamuffin — cockpit

**What it is** · A pipeline that was meant to turn Hiren's portal.mogelijk.nl docs into a concept-level Obsidian knowledge base. Today it is a set of agent prompts plus one lossy 1:1 rewrite of 24 docs.
**Stack** · Markdown prompts (`agents/`), Obsidian vault (`vault/`), Msty Claw playbook (`claw/`), Ollama models on disk. No application code.
**Status** · 🟡 rough — the concept-index rebuild started 2026-09-18 and runs locally end to end; the old 5-agent relay is superseded but not yet removed — the design premise does not match the input, the local pipeline never ran (Claw was pointed at an MLX service that was never installed), and the wiki output is a worse copy of its sources. Hard constraints from Hiren (2026-09-16/17): local models only, no cloud; budget this M1 Pro as a 20 GB machine; the second machine is a fanless M5 Air with 16 GB. So models must fit in roughly 12 GB with context on both.
**Repo** · git@github.com:Hersh3yy/RAGgamuffin.git · trunk is `master` (no `main`); 10 files modified and 13 untracked (23 dirty entries) since the last commit on 2026-06-29. The concept-index redesign was built directly on `master` and sits there uncommitted, not on the planned `concept-index` branch. Nothing is committed yet; the output is not yet judged good enough in Obsidian to merge.
**Hosting** · Local only. Vault opened in Obsidian from `vault/`. Source docs live outside the repo in `~/Herd/documentation`.
**ClickUp** · not linked
**Last assessed** · 2026-10-14

---

## Run it

There is nothing to build or test. "Running" means opening the vault and, in theory, triggering the pipeline.

```bash
python3 ingest.py --status                    # which source docs are new / changed / already done
python3 ingest.py --all                       # ingest everything pending (local model, no cloud)
python3 ingest.py --source ~/Herd/documentation/sepa-mandate-system.md
python3 bench.py                              # model bake-off, writes vault/_bench/<date>/report.md
open -a Obsidian /Users/hirenbudhrani/Herd/RAGgamuffin/vault
```

Local inference on this machine (M1 Pro, 32 GB), measured 2026-09-16:

| Where | What | State |
|---|---|---|
| Ollama 0.14.2, port 11434 | `qwen2.5-coder:7b`, `qwen3:4b`, `llama3`, `nomic-embed-text` | running; Metal; 7B reads 245 tok/s, writes 25 tok/s; speaks the Anthropic `/v1/messages` API |
| Msty Studio 2.8.3 llama.cpp, port 11454 | `Qwen3.6-35B-A3B` Q4 (21 GB), `gemma-4-12B` fine-tune (6.9 GB), `gemma-3-1b` | configured with `"variant": "cpu"` so Metal is off; ctx 8192; unloaded |
| Msty Studio local AI (Ollama fork), port 11964 | `qwen3:0.6b` | running, nothing loaded |
| Msty Claw 0.9.3 | one MLX provider on port 11973, default model `granite-3.3-2b`; 0 bots, 0 skills, 0 playbooks | service `not_installed`; DB last written 2026-07-01 |

Claude Code 2.1.270 can be pointed at Ollama (`ANTHROPIC_BASE_URL=http://localhost:11434`, `ANTHROPIC_AUTH_TOKEN=ollama`) and the agent loop does work locally: with `qwen3:4b-64k` it read a file and answered correctly. But the harness is expensive on a small model. Measured 2026-09-17/18:

| Setup | Time for "reply LOCAL OK" |
|---|---|
| Raw Ollama call, 16-token prompt | 3.9 s |
| Claude Code, full config (MCP + plugins, ~33k-token prompt) | ~5 min, with 500s |
| Claude Code, `--strict-mcp-config --tools Read --exclude-dynamic-system-prompt-sections` | 88 s |
| Same lean config, plus one real file read | 2 min 34 s |

So nearly all the cost is prompt, not generation. Two consequences: the KB pipeline should talk to Ollama directly from a script (no harness tax at all), and if a chat harness is wanted, Msty Claw's much smaller prompt beats Claude Code here. Ollama's default 4096 context silently truncates Claude Code's prompt, so a 64k alias is required: `ollama create qwen3:4b-64k` from a Modelfile with `PARAMETER num_ctx 65536` (created 2026-09-17, no download). It costs 12 GB resident at 64k. Claude Code also warns that it does not recognise custom model names; harmless.

## Status

Built 10 June to 20 July 2026 across four Cursor sessions. The README, prompts, playbook and vault layout are complete and internally consistent. What does not work is the result: 24 finished docs went in, 24 paraphrased docs came out, no concept pages exist, the graph view is doc-to-doc only, and Hiren's own 20 July note says "unprocessed documents pretty much become the same documents in the wiki". The pipeline was designed for messy raw notes and fed polished documentation. The privacy motivation for local models is already spent in practice, since the docs went through Cursor's cloud models. The redesign around concept extraction was then built on 2026-09-18 and runs locally end to end (`ingest.py` + `bench.py`, both stdlib-only, no cloud): it extracted 13 concept pages into `vault/concepts/` on three signing/SEPA sources and recorded 28 sources in `vault/03_meta/ledger.json`. That machinery works; the open problem is output quality, since only about 7 of the 13 concepts are real and only 4 carry a verified anchor. As of 2026-10-14 nothing has moved since that build and none of it is committed.

## Issues

| Sev | Issue | Where |
|---|---|---|
| critical | Unit of work is the file, so tier is assigned per document: 15 of 24 pages are `organism`, zero concept pages. The atom/molecule idea never happened. | `agents/agent2-structurer.md` FRONTMATTER CONTRACT; all of `vault/02_wiki/` |
| critical | Rewrite is lossy. Summary forbids implementation detail and toggles hide code; a 56 KB builder's manual became 9 KB and its toggle says the rest is "preserved in archived source". | `vault/02_wiki/signings-technical-reference.md:231` vs `vault/03_meta/archive/signings-technical-reference.md` |
| critical | Local pipeline never ran. No Claw workspace, no watcher, no local-model output anywhere. The five-hop relay (each agent rewriting the whole doc) paid the paraphrase cost with no privacy benefit. | `claw/playbook.md`; `~/Library/Application Support/MstyClaw/workspaces` is empty |
| warning | Msty Studio llama.cpp: the config says `"variant": "cpu"` but the running server does load `libggml-metal` and runs 50 tok/s vs Ollama's 70 tok/s on the identical 1B GGUF, so the GPU is in use (measured 2026-09-17, idle GPU). Real issues: context 8192 for all models (`models-preset.ini` `c = 8192`), two parallel slots (`np = 2`) halving context per chat, and the Gemma 4 12B entry set to `embedding = true`, `jinja = false`, which breaks chatting with it. | `~/Library/Application Support/MstyStudio/llama-cpp/models-preset.ini` |
| serious | Msty Claw's local AI service is `not_installed` and its default model is a 2B granite over an MLX endpoint that is not running. Nothing Claw-side has ever executed. | `~/Library/Application Support/MstyClaw/msty-claw.db` tables `managed_services`, `settings` |
| serious | `~/.zshrc:216-219` exports `ANTHROPIC_BASE_URL=http://localhost:11434/v1` for every terminal. Claude Code appends `/v1/messages`, so requests hit `/v1/v1/messages` (404). This is the likely reason the earlier Claude Code + Ollama attempt failed. Correct value has no `/v1`. It also silently redirects any terminal `claude` to Ollama. | `~/.zshrc:218` FIXED by Hiren 2026-09-17 |
| serious | Two copies of the truth. `vault/03_meta/archive/` is a July snapshot; `~/Herd/documentation` has 6 newer docs (`cre-quote-signing`, `fund-participation-signing`, `mail-channels`, `account-view-property-linking`, `ticket-unified-signings-cms-webhook`, `unified-signing-dev-map`). Corrections from 16 July went into the wiki, not the source. | `vault/03_meta/backlog.md` "Fixed for you" section |
| serious | Privacy gap: notes at the vault root are not gitignored, so `vault/Property.md`, `GraphQL.md`, `SEPA Direct Debit.md`, `Unified Signing.md` show as untracked and would be committed. They are empty today, but the rule is missing. | `.gitignore` (no `vault/*.md` rule) |
| warning | `diff.txt` (102 KB, a git diff of the repo itself) is committed at the root. Scratch, delete. | `diff.txt` |
| warning | README numbers the agents 1 to 8 with no agent 7, and never states the trunk branch (`master`, no `main`), so a fresh session guesses wrong. | `README.md` |
| warning | Hiren hand-created hub notes (`Property`, `GraphQL`, `SEPA Direct Debit`, `Unified Signing`) at the vault root and hopped between them and wiki pages. That is the pipeline's missing output being made by hand. | `vault/.obsidian/workspace.json` lastOpenFiles |

## Guide

Three folders matter.

`agents/` holds the seven system prompts (1 Verifier, 2 Structurer, 3 Visualizer, 4 Critic, 5 Curator, 6 Consultant, 8 Sentinel). They are the source of truth for the pipeline design and were meant to be pasted into Msty Skills Studio. Agents 1 to 4 form the per-note hot path, each receiving the full document plus a `KB_INDEX` (one line per existing wiki note) and emitting the full document again. Agent 4 splits its output on `=== BACKLOG ===`.

`claw/playbook.md` describes how Msty Claw would chain them: a folder watcher on `vault/01_unprocessed/`, a rescan of `02_wiki/` into `KB_INDEX`, then the four agents, then the Curator adding outbound `[[links]]`, then archive the raw note under `03_meta/archive/`.

`vault/` is the Obsidian vault. `02_wiki/` is the output (24 pages, all with `type` / `tier` / `domain` frontmatter, all wikilinks resolving). `03_meta/backlog.md` is the reading and writing queue in a three-part shape (topic, why, which existing articles it enriches). `_views/*.base` are Obsidian Bases views sliced by tier and domain.

Domain words to keep: `atom` / `molecule` / `organism` (tier, by the zero-prerequisite litmus), `KB_INDEX` (the per-run inventory of the wiki), `hot path` (per-note run) vs `weekly crew` (curator and sentinel sweeps), `enriches:` (the backlog pointer to existing articles).

The actual knowledge is not in this repo. It lives in `~/Herd/documentation` (30 docs, growing) and is grounded in `~/Herd/portal.mogelijk.nl`. This repo should index that knowledge, not copy it.

### The ledger, and why the inbox folder goes away

Hiren moved docs into `01_unprocessed/` to remember which ones had already been
scanned. That works but makes the folder the database, so a re-scan means moving
files back, and a source that CHANGED after ingestion looks identical to one that
never moved.

`vault/03_meta/ledger.json` replaces it. Each source is recorded by absolute path
plus a SHA-256 of its content, the date, the model used, and the concept slugs it
produced. Sources stay where they live in `~/Herd/documentation`. `--status` then
answers three states instead of one: NEW (never seen), CHANGED (hash differs from
the ingested copy, so re-ingest), done. Nothing is ever scanned twice by accident,
and an edited source is picked up automatically.

## Hard parts

### Verify anchors against the source, never trust the model

🔭 **What it does** — the extractor asks a local model for concepts as JSON, and each concept carries `anchors`: the class names, file paths and config keys the text ties to it. Every anchor is then checked for a VERBATIM substring match against the source document, and anything that does not match is dropped and counted. On the first run a 4B model turned `app/Modules/Sepa/Models/Mandate.php` into `app/Modules/Sep:Sepa/Models/Mandate.php`; the check caught it.

⚖️ **Why this way** — the whole point of the rebuild is that code references survive. A model that paraphrases a path is worse than one that omits it, because a wrong path looks authoritative. Deterministic verification costs nothing and turns a trust problem into a counted metric.

🗣️ **Say it to a senior** — "The model proposes anchors, the source disposes. Anything it can't quote verbatim gets dropped and counted, so hallucinated file paths never reach the wiki."

---

### The unit of work decides whether you get a graph

🔭 **What it does**: every prompt takes one file and returns one file, so the output can only ever be a one-to-one mapping of the input. Tier, links and composition are all decided inside a single document's context, which means a concept that appears in six docs never gets its own page and never becomes a node. A knowledge graph needs the concept, not the file, to be the thing that is created and merged.

⚖️ **Why this way**: the 1:1 shape was the right call for the stated input (a messy note about one thing). It broke because the real input was 30 multi-topic reference docs. Fix the unit of work, not the prompts.

🗣️ **Say it to a senior**: "The pipeline was a document polisher wearing a knowledge-graph costume. Nothing in it could create a node that wasn't already a file."

---

### Multi-hop rewriting is a lossy channel

🔭 **What it does**: four agents each rewrote the entire document. Every hop paraphrases, and paraphrase drops specifics first: line numbers, enum string mismatches, the eight manual steps of a flow. The Critic could only repair formatting because by then the information was already gone. Splitting extraction (structured JSON) from rendering (a script) removes the rewrite hops entirely and makes formatting deterministic.

⚖️ **Why this way**: the split was designed around 4B-model context limits. With a capable model or with per-section extraction, the relay buys nothing.

🗣️ **Say it to a senior**: "Each agent was a photocopier of the previous copy. We should extract once into data and render from data."

---

### Obsidian punishes optimistic markdown

🔭 **What it does**: a `[[link]]` to a note that does not exist renders as a valid link and spawns an empty stub the moment anyone clicks it, which is why the prompts gate links on `KB_INDEX` and why the Critic strips unknown stems. A `<details>` block only renders the markdown inside it if there is a blank line after `</summary>` and before `</details>`. Obsidian's Mermaid accepts a restricted subset: no `style`, `classDef` or `<br>`, node ids without spaces or hyphens, quoted labels for anything with punctuation.

⚖️ **Why this way**: these were the right rules to encode. They just belong in a renderer script, where they are guaranteed, rather than in a prompt, where they are hoped for.

🗣️ **Say it to a senior**: "Phantom links, toggle blank lines and the Mermaid subset are all deterministic constraints, so they go in code, not in a prompt."

## Roadmap — near future

Proposed split: the first two are small and safe and can be done in one sitting once green-lit; the rest is the real work.

- [ ] Housekeeping: gitignore `vault/*.md`, delete `diff.txt`, note the trunk branch and agent numbering in README, commit the 20 July prompt edits so the tree is clean <!-- id:n1 -->
- [ ] Local runtime, no cloud: Msty Claw can take a provider of type `ollama` (schema allows anthropic/openai/openrouter/ollama/mlx) pointed at the running Ollama on 11434, replacing the dead MLX provider; Msty Studio Split Chat with duplication mode for quick side-by-side looks; Claude Code on Ollama as fallback harness. Flip Msty llama.cpp to Metal, raise `Num ctx` to 32k. <!-- id:n7 -->
- [ ] Decide the fate of the 5-agent relay and the Claw playbook: retire or keep as reference in `docs/legacy/` <!-- id:n2 -->
- [x] Prototype the concept index on three sources (signings technical reference, SEPA mandate system, one GoCredible doc): extract concepts to JSON with definition, verbatim code anchors, source sections, related concepts; render to `vault/concepts/<slug>.md` with a script that appends when the concept exists. Judge in Obsidian before going wider. <!-- id:n3 -->
- [ ] Raise grounding: today only 4 of 13 concepts carry an anchor, because the model puts prose in the anchor field and the shape filter drops it. Better: after the model names a concept, find its anchors deterministically from the backticked identifiers in the chunk it came from, instead of asking the model for them <!-- id:n10 -->
- [ ] Improve concept quality: stop section titles becoming concepts, make `kind` meaningful, dedupe near-identical concepts across sources. Prompt work plus a better model; run `bench.py` over the extraction task once the three missing models are downloaded <!-- id:n9 -->
- [ ] Make `~/Herd/documentation` the single source: pull it into the vault verbatim (copy or symlink) and drop `03_meta/archive/` and the paraphrased `02_wiki/` once the concept pages cover them <!-- id:n4 -->
- [ ] Deterministic anchor check: a script that greps every cited path and class in the concept pages against `~/Herd/portal.mogelijk.nl` and flags misses as `#stale` backlog entries <!-- id:n5 -->
- [ ] Run the extraction over all 30 docs with the chosen local model, rebuild the backlog from the graph (concepts cited by 2+ docs with no definition become `#write-doc`) <!-- id:n6 -->

## Roadmap — far future

- [ ] Sentinel v2: on portal git diff, flag concept pages whose anchored files changed instead of prose-diffing the wiki <!-- id:f1 -->
- [x] Model bake-off (the "compare over and over" feature): a script that runs one task over the same 3 source docs for N local models via Ollama (and optionally Msty's llama.cpp on 11454), writes outputs to `vault/_bench/<date>/<model>/`, records tok/s and deterministic scores (anchor retention, JSON/frontmatter validity, mermaid validity, phantom links, length ratio), and a `report.md` plus an Obsidian Base so Hiren can add a 1 to 5 human rating and rerun any time <!-- id:n8 -->
- [ ] Model shortlist within a 12 GB budget (all Ollama, all tool-capable unless noted): `gemma4:12b`, `qwen3:14b`, `qwen3.5:9b`, `granite4.2:8b`, `phi4-mini` (3.8B), `phi4:14b` (9.1 GB, no tools, text only). Already on disk without download: `gemma-4-12B` community fine-tune GGUF (6.9 GB, Msty), `qwen3:4b`, `qwen2.5-coder:7b` (no tools). Too big for the budget: `Qwen3.6-35B-A3B` (21 GB, on disk), `gemma3:27b`, `qwen3-coder:30b`, `granite4.2:30b`, `gpt-oss:20b` (14 GB, borderline). Kimi K2.6 is 1T parameters, cloud-only on Ollama, not runnable on any laptop. Downloads need Hiren's go. <!-- id:f2 -->
- [ ] Evaluate Magnitude (`npm i -g @magnitudedev/cli`, Rust on llama.cpp, profiles hardware, claims Claude Code integration via a background service). Unverified here; docs give no API or model details. <!-- id:f7 -->
- [ ] Next-version skills over the portal codebase, local model plus codebase-memory / Serena graph: design-pattern usage map, improvement areas with effort estimate, learning plans per area for newcomers and seniors <!-- id:f8 -->
- [ ] Consultant (agent 6) over the concept pages plus verbatim sources, via Msty Knowledge Stack or the filesystem MCP for Cursor described in the README <!-- id:f3 -->
- [ ] Obsidian Bases views by concept type and by number of grounding sources (thin pages surface first) <!-- id:f4 -->
- [ ] Decide where corrections live: fix the source doc in `~/Herd/documentation`, never the derived page <!-- id:f5 -->
- [ ] Mirror this roadmap to ClickUp if Hiren wants it <!-- id:f6 -->

---

## Diary

<!-- Newest first. One entry per working session. Terse, factual, honest. Append only. -->

### 2026-10-14 — reassessment; no change since the 09-18 build
- Update-mode pass, no app code touched. Nothing in the tree is newer than 2026-09-18; the concept-index pipeline built that day is exactly as it was left.
- Confirmed the redesign DID land as working code: `ingest.py` and `bench.py` are pure stdlib (urllib, no requirements.txt), both `py_compile` clean; `vault/concepts/` holds 13 pages, `_bench/2026-09-18_0822/` holds the bake-off run, `ledger.json` tracks 28 sources. It all sits uncommitted on `master`, not on the planned `concept-index` branch.
- Reconciled stale fields: the `## Status` prose still said the redesign was "proposed and not started" (it is built); Repo count was "8 untracked" (now 13, 23 dirty entries); `Last assessed` was never bumped past 09-16.
- Housekeeping n1 is still NOT done: `diff.txt` (102 KB) is still committed at root, README still names no trunk branch, and `vault/*.md` root notes are still not gitignored, so `GraphQL.md` / `Property.md` / `SEPA Direct Debit.md` / `Unified Signing.md` still show as untracked.
- The work is coherent (a deliberate, documented redesign), not random WIP, but it is a large uncommitted mix of generated vault output + two scripts + prompt/playbook edits. Recommendation if committing: split it — scripts + prompt/playbook edits on the `concept-index` branch, generated `vault/concepts` and `_bench` output gated by the n1 gitignore fixes first so the four empty root hub notes and `diff.txt` do not get committed.
- Hiren: no downloads (on a train), start building. Three of four bake-off models never downloaded (connection reset overnight); working with granite4.2:8b, granite4.1:8b, qwen3:4b, qwen2.5-coder:7b.
- Built `ingest.py`: sections -> local model -> schema-constrained JSON -> anchor verification -> merged concept pages in `vault/concepts/` -> ledger. Runs end to end.
- Built the ledger (`vault/03_meta/ledger.json`) per Hiren's point that moving files into `01_unprocessed/` was his "already scanned" marker. Sources now stay in `~/Herd/documentation`; NEW / CHANGED / done comes from a content hash. 28 sources tracked.
- Four of my own bugs found and fixed by testing, not by reading: split shredded a 3.8 KB doc into 10 fragments so models invented concepts to fill them (now packs to ~4k chunks); a code-SHARE skip silently skipped whole documents (now skips only chunks with under 200 chars of prose); an over-strict prompt made the model return nothing (added a worked example); anchors arrived as prose (added a shape filter, unit-tested).
- Measured on `sepa-mandate-system.md` (18 KB) with granite4.2:8b, same doc each time: prompt-only = 28 concepts (a roadmap TABLE gave 11, one per row); tables stripped = 46 and WORSE (class names became concepts); three deterministic gates = 13 concepts, of which roughly 7 are real. Grounding is the weak spot: only 4 of 13 carry a verified anchor.
- Conclusion: judgment belongs in code, not the prompt. Gates now enforced in `verify()`: a concept whose NAME looks like code is rejected, anchors must be verbatim AND identifier-shaped, max 3 concepts per chunk preferring grounded ones. A better model improves output without touching the gates; a worse one cannot poison the wiki.
- Model quality is the open problem, not the machinery. qwen3:4b returns exactly what the prompt forbids (classes, methods, input types). granite4.2:8b is better but still emits section titles as concepts and tags everything `entity`.
- Machine health: 12-15 GB swap in use, under 1 GB free; one section took 419 s purely on model load. Found real waste: Ollama was loading at 32k context (7.8 GB) when chunks are ~1.2k tokens; default is now 4096 (3.5 GB).
- Nothing committed. `ingest.py`, `bench.py`, `vault/concepts/`, `vault/03_meta/ledger.json` all untracked.

### 2026-09-18 — local harness proven; harness overhead measured
- Hiren fixed the `/v1` in `~/.zshrc`. Confirmed Claude Code now reaches Ollama.
- Local agent loop WORKS: `qwen3:4b-64k` read a file through Claude Code and answered correctly.
- Measured the real cost: harness prompt dominates (3.9 s raw vs 88 s lean vs ~5 min full config). Recorded as a table under Run it.
- Found and fixed the second blocker: Ollama's 4096 default truncated Claude Code's ~33k-token prompt. Created a 64k alias, no download.
- Corrected yesterday's Metal claim: Msty's llama.cpp does use the GPU (50 tok/s vs Ollama 70 on the same 1B file). Its real faults are the 8k preset context, 2 parallel slots, and the Gemma 4 12B entry flagged as embedding-only.
- Drafted the bake-off script (scratchpad, not yet in repo). Awaiting go on the four model downloads.

### 2026-09-17 — model bake-off brief; 20 GB budget; M5 Air
- Hiren wants to compare Kimi, Granite, Phi, Gemma and Qwen repeatedly, preferably inside Msty Studio or Claw. Budget: treat this M1 Pro as 20 GB; the Air is M5, 16 GB, fanless.
- Grounded the candidates on the Ollama library (sizes, tool support). Kimi K2.6 is cloud-only at 1T params. Gemma 4 exists (12b/26b/31b, tools). Granite 4.2 (3b/8b/30b, tools, thinking). Phi 4 has tools only in the mini variant.
- Read the Claw playbook and guide; Claw's DB accepts an `ollama` provider type, so it can drive the already-running Ollama. Msty Studio Split Chat confirmed for interactive comparison.
- Added roadmap n8 (bake-off script) and rewrote f2 (shortlist within 12 GB). No changes outside this file.

### 2026-09-16 (evening) — local-only constraint; audit of Msty Studio, Msty Claw, Ollama
- Hiren: no cloud models, respectfully. Constraint recorded at the top.
- Found why local never worked: Msty llama.cpp on `cpu` variant, 8k ctx; Claw pointing at an uninstalled MLX service with a 2B default model.
- Verified Ollama's Anthropic-compatible API works locally and that `qwen3:4b` emits real tool calls; `qwen2.5-coder:7b` does not. Measured 245 tok/s prompt, 25 tok/s generation on the 7B coder (Metal).
- Read Magnitude docs: local inference engine (Rust on llama.cpp) with hardware profiling, not an agent framework; Claude Code integration claimed, details thin.
- No downloads, no config changes, no code changes. Only this file.

### 2026-09-16 — first map; diagnosis of why the wiki disappointed
- Read README, all agent prompts, playbook, backlog, logs, all 24 wiki pages' structure, one raw-vs-wiki pair in full, the four Cursor transcripts and the Msty Claw app state.
- Findings: 1:1 document rewrite instead of concept graph; lossy compression (56 KB to 9 KB with file:line traces dropped); local pipeline never ran, Cursor did the 16 July run; source docs in `~/Herd/documentation` have drifted 6 docs ahead of the vault archive; vault-root notes not gitignored.
- Proposed redesign: keep sources verbatim, extract concepts to JSON, render and merge with a script, verify anchors by grep, derive the backlog from the graph. Not started, awaiting green light.
- No code or prompt changes made. Only this file was written.

### 2026-06-10 to 2026-07-20 — reconstructed from Cursor transcripts, not a live session
- 10 Jun: repo created; docs in `~/Herd/documentation`; Msty Studio installed, models still to download.
- 1 Jul: "want to start using this today"; Msty endpoint and agent setup; first vault layout; Visualizer agent added.
- 16 Jul: local models still not connecting; Cursor asked to run the pipeline by hand over `01_unprocessed/`; 24 wiki pages produced; corrections applied against the portal codebase and written into the wiki.
- 20 Jul: Hiren notes the wiki equals the input; "KB placement on every ingest" plan implemented (KB_INDEX, Composition rules, three-part backlog). These prompt edits are still uncommitted.
