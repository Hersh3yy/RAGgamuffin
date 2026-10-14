#!/usr/bin/env python3
"""RAGgamuffin model bake-off.

Runs ONE task (a system prompt) over the SAME source docs for every model in
MODELS, saves each output, measures speed, and scores what can be scored
without a model. Rerun any time; every run lands in its own dated folder.

    python3 bench.py                      # all models, all docs
    python3 bench.py --models qwen3:4b    # subset
    python3 bench.py --prompt agents/agent2-structurer.md

Endpoints: Ollama (native /api/chat, gives token timings) and any
OpenAI-compatible server such as Msty's llama.cpp on :11454.
Standard library only.
"""
import argparse, datetime, json, pathlib, re, subprocess, sys, time, urllib.request

REPO = pathlib.Path(__file__).resolve().parent
VAULT = REPO / "vault"
BENCH = VAULT / "_bench"

# model id -> endpoint. "ollama" or an OpenAI-compatible base URL.
MODELS = {
    "granite4.2:8b": "ollama",
    "qwen3.5:9b": "ollama",
    "gemma4:12b": "ollama",
    "qwen3:14b": "ollama",
    "qwen3:4b": "ollama",
    "qwen2.5-coder:7b": "ollama",   # no tool support, fine for this prose task
    # Msty llama.cpp models are reachable too, e.g.:
    # "unsloth/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf": "http://127.0.0.1:11454/v1",
}

DOCS = [
    "03_meta/archive/sepa-mandate-system.md",
    "03_meta/archive/property-update-mutation.md",
    "03_meta/archive/invoices-p2p.md",
]

ANCHOR_RE = re.compile(r"`([^`\n]{3,80})`")            # backticked identifiers
PATH_RE = re.compile(r"\b(?:app|config|database|resources|tests)/[\w./-]+\.\w+")
LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def read_prompt(path: pathlib.Path) -> str:
    text = path.read_text()
    return text.split("\n---\n", 1)[1] if "\n---\n" in text else text


def call_ollama(model, system, user, num_ctx):
    body = {"model": model, "stream": False, "think": False,
            "options": {"num_ctx": num_ctx, "temperature": 0.2},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(),
                                 {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.load(r)
    out = d["message"]["content"]
    ev, pe = d.get("eval_duration", 1), d.get("prompt_eval_duration", 1)
    return out, {"prompt_tokens": d.get("prompt_eval_count"), "out_tokens": d.get("eval_count"),
                 "prompt_tok_s": round(d.get("prompt_eval_count", 0) / (pe / 1e9), 1),
                 "gen_tok_s": round(d.get("eval_count", 0) / (ev / 1e9), 1),
                 "total_s": round(d.get("total_duration", 0) / 1e9, 1)}


def call_openai(base, model, system, user, num_ctx):
    body = {"model": model, "temperature": 0.2, "max_tokens": 6000,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 {"content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.load(r)
    out = d["choices"][0]["message"]["content"]
    t = d.get("timings", {})
    return out, {"prompt_tokens": t.get("prompt_n"), "out_tokens": t.get("predicted_n"),
                 "prompt_tok_s": round(t.get("prompt_per_second", 0), 1),
                 "gen_tok_s": round(t.get("predicted_per_second", 0), 1),
                 "total_s": round(time.time() - t0, 1)}


def score(source: str, out: str, wiki_stems: set) -> dict:
    src_anchors = set(ANCHOR_RE.findall(source)) | set(PATH_RE.findall(source))
    kept = [a for a in src_anchors if a in out]
    fm_ok = bool(re.match(r"^---\n(?:.*\n)*?---\n#", out))
    fm = re.match(r"^---\n(.*?)\n---", out, re.S)
    fields = dict(l.split(":", 1) for l in fm.group(1).splitlines() if ":" in l) if fm else {}
    mermaid = re.findall(r"```mermaid\n(.*?)```", out, re.S)
    mermaid_ok = sum(1 for m in mermaid if re.match(r"\s*(flowchart (TD|LR)|sequenceDiagram)", m))
    links = LINK_RE.findall(out)
    phantom = [l for l in links if l.strip() not in wiki_stems]
    preamble = not out.lstrip().startswith("---")
    return {
        "anchor_retention": round(len(kept) / len(src_anchors), 2) if src_anchors else None,
        "anchors_src": len(src_anchors), "anchors_kept": len(kept),
        "frontmatter_ok": fm_ok, "type": fields.get("type", "").strip(), "tier": fields.get("tier", "").strip(),
        "mermaid_blocks": len(mermaid), "mermaid_ok": mermaid_ok,
        "links": len(links), "phantom_links": len(phantom),
        "length_ratio": round(len(out) / len(source), 2), "preamble": preamble,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--prompt", default="agents/agent2-structurer.md")
    ap.add_argument("--ctx", type=int, default=32768)
    a = ap.parse_args()

    models = {m: MODELS[m] for m in (a.models or MODELS)}
    docs = a.docs or DOCS
    system = read_prompt(REPO / a.prompt)
    stems = {p.stem for p in (VAULT / "02_wiki").glob("*.md")}
    index = "\n".join(sorted(stems)) or "(empty)"
    run = BENCH / datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    run.mkdir(parents=True, exist_ok=True)
    results = []

    for model, ep in models.items():
        for doc in docs:
            src = (VAULT / doc).read_text()
            user = f"=== KB_INDEX ===\n{index}\n=== NOTE ===\n{src}"
            print(f"[{model}] {doc} ...", end=" ", flush=True)
            try:
                out, timing = (call_ollama(model, system, user, a.ctx) if ep == "ollama"
                               else call_openai(ep, model, system, user, a.ctx))
            except Exception as e:  # keep going, record the failure
                print("FAILED", e); results.append({"model": model, "doc": doc, "error": str(e)}); continue
            safe = re.sub(r"[^\w.-]+", "_", model)
            outp = run / safe / (pathlib.Path(doc).stem + ".md")
            outp.parent.mkdir(parents=True, exist_ok=True)
            sc = score(src, out, stems)
            fm = "\n".join(f"{k}: {v}" for k, v in {**sc, **timing, "bench_model": model,
                           "bench_doc": doc, "human_rating": ""}.items())
            outp.write_text(f"---\nbench: true\n{fm}\n---\n\n{out}")
            results.append({"model": model, "doc": doc, **sc, **timing})
            print(f"{timing['total_s']}s  gen {timing['gen_tok_s']} tok/s  anchors {sc['anchor_retention']}  "
                  f"fm {'ok' if sc['frontmatter_ok'] else 'BAD'}  mermaid {sc['mermaid_ok']}/{sc['mermaid_blocks']}")
        if ep == "ollama":  # unload before the next model: 20 GB budget
            subprocess.run(["ollama", "stop", model], capture_output=True)

    # baseline: what the July 2026 cloud-run pipeline scored on the same docs
    baseline = []
    for doc in docs:
        stem = pathlib.Path(doc).stem
        old = VAULT / "02_wiki" / f"{stem}.md"
        if old.exists():
            baseline.append({"doc": stem, **score((VAULT / doc).read_text(), old.read_text(), stems)})

    (run / "results.json").write_text(json.dumps({"runs": results, "baseline_july": baseline}, indent=1))
    rows = ["| model | doc | total s | gen tok/s | anchors kept | frontmatter | mermaid ok | phantom | len ratio |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "error" in r:
            rows.append(f"| {r['model']} | {pathlib.Path(r['doc']).stem} | FAILED | | | | | | {r['error'][:40]} |"); continue
        rows.append(f"| {r['model']} | {pathlib.Path(r['doc']).stem} | {r['total_s']} | {r['gen_tok_s']} | "
                    f"{r['anchor_retention']} ({r['anchors_kept']}/{r['anchors_src']}) | {'ok' if r['frontmatter_ok'] else 'bad'} | "
                    f"{r['mermaid_ok']}/{r['mermaid_blocks']} | {r['phantom_links']} | {r['length_ratio']} |")
    brows = ["", "## Baseline — the July 2026 run (what we are trying to beat)", "",
             "| doc | anchors kept | mermaid ok | len ratio |", "|---|---|---|---|"]
    for r in baseline:
        brows.append(f"| {r['doc']} | {r['anchor_retention']} ({r['anchors_kept']}/{r['anchors_src']}) | "
                     f"{r['mermaid_ok']}/{r['mermaid_blocks']} | {r['length_ratio']} |")
    brows += ["", "`anchors kept` = share of the source's backticked identifiers and file paths that survive.",
              "Low retention with a low length ratio is the lossy-paraphrase failure. Add your own 1-5 score",
              "in each output's `human_rating` frontmatter field, then open the folder in Obsidian."]
    (run / "report.md").write_text(f"# Bench {run.name}\n\nprompt: `{a.prompt}` · ctx {a.ctx}\n\n"
                                   + "\n".join(rows) + "\n" + "\n".join(brows) + "\n")
    print(f"\nreport: {run / 'report.md'}")


if __name__ == "__main__":
    sys.exit(main())
