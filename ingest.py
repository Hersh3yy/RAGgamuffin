#!/usr/bin/env python3
"""RAGgamuffin ingest: upsert concept pages from documents, locally.

One page per concept, forever. A document that mentions a concept the vault
already knows UPDATES that page; it never creates a second one.

Who does what
  judgment   which concepts a document touches, the merged explanation, the
             diagram -> the model (Claude on Thursday, or a local model as a
             weaker preview). It hands this script a JSON file.
  rules      slug resolution and aliases, anchor verification against the
             source text AND the code repo, the rejected list, Mermaid
             validation, frontmatter, changelog, ledger, archive, review note
             -> this script. The model cannot bypass any of it.

Commands
  python3 ingest.py --status                       what is NEW / CHANGED / done
  python3 ingest.py --index                        JSON of known concepts, for the model
  python3 ingest.py --from-json out.json --source FILE    upsert (the Thursday path)
  python3 ingest.py --local --source FILE          preview with the local model
  python3 ingest.py --reject SLUG                  delete page, never recreate
  python3 ingest.py --review                       print today's review note path

Config: kb.json (per project, committed) + kb.local.json (per machine, ignored).
Standard library only.
"""
import argparse, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
KINDS = ["entity", "process", "integration", "concept", "reference"]
STOP = {"the", "a", "an", "of", "and", "for", "de", "het", "een", "van", "en", "system", "systeem"}
NL_EN = {"machtiging": "mandate", "hypotheek": "mortgage", "offerte": "quote", "ondertekening": "signing",
         "aanvraag": "application", "lening": "loan", "pand": "property", "rente": "interest",
         "factuur": "invoice", "klant": "customer", "notaris": "notary", "passeerdatum": "pass-date"}


# ----------------------------------------------------------------- config ---
def load_config():
    cfg = json.loads((HERE / "kb.json").read_text())
    local = HERE / "kb.local.json"
    if local.exists():
        cfg.update(json.loads(local.read_text()))
    def path(p):
        p = pathlib.Path(p).expanduser()
        return p if p.is_absolute() else (HERE / p).resolve()
    cfg["vault"] = path(cfg.get("vault", "./vault"))
    cfg["inbox"] = path(cfg.get("inbox", cfg["vault"] / "01_unprocessed"))
    cfg["archive"] = path(cfg.get("archive", cfg["vault"] / "03_meta" / "archive"))
    cfg["sources"] = [path(s) for s in cfg.get("sources", [])]
    cfg["code_repo"] = path(cfg["code_repo"]) if cfg.get("code_repo") else None
    cfg.setdefault("code_globs", ["*.php"])
    cfg.setdefault("ollama", "http://127.0.0.1:11434")
    cfg.setdefault("model", "qwen3:4b")
    cfg.setdefault("ctx", 4096)
    cfg["concepts"] = cfg["vault"] / "concepts"
    cfg["meta"] = cfg["vault"] / "03_meta"
    cfg["ledger"] = cfg["meta"] / "ledger.json"
    cfg["aliases"] = cfg["meta"] / "aliases.json"
    cfg["reviews"] = cfg["meta"] / "reviews"
    return cfg


def jload(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def jsave(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False))


def today():
    return datetime.date.today().isoformat()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# --------------------------------------------------------------- identity ---
def slugify(name):
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "unnamed"


def normalise(name):
    """Language- and stopword-insensitive key used as the last-resort match."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    words = [NL_EN.get(w, w) for w in words if w not in STOP]
    words = [w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words]
    return "-".join(sorted(words))


def resolve_slug(concept, cfg, aliases, pages):
    """Existing slug if this is a known concept, else a fresh one.

    Order: slug the model chose (must exist) -> alias table -> normalised
    match on name or aliases -> new. Returns (slug, how).
    """
    wanted = (concept.get("slug") or "").strip()
    if wanted and wanted in pages:
        return wanted, "model"
    names = [concept.get("name", "")] + list(concept.get("aliases") or [])
    for n in names:
        k = normalise(n)
        if k in aliases:
            return aliases[k], "alias"
    norm_to_slug = {normalise(p["name"]): s for s, p in pages.items()}
    for n in names:
        k = normalise(n)
        if k in norm_to_slug:
            return norm_to_slug[k], "normalised"
    return wanted or slugify(concept.get("name", "")), "new"


# ---------------------------------------------------------------- anchors ---
def looks_like_code(a, source):
    if f"`{a}`" in source:
        return True
    if " " in a or a.endswith((".", ",", ":")):
        return False
    return bool(re.search(r"[/_.]|::|\(\)|[a-z][A-Z]|^[A-Z][A-Z0-9_]{2,}$|^[A-Z]{2,}-\d+$", a))


def locate(anchor, cfg):
    """File in the code repo that defines or mentions the anchor, or None."""
    repo = cfg.get("code_repo")
    if not repo or not repo.exists():
        return None
    if "/" in anchor and (repo / anchor).exists():
        return anchor
    needle = anchor.split("::")[0].rstrip("()")
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "grep", "-l", "-F", "--", needle, "--"] + cfg["code_globs"],
            capture_output=True, text=True, timeout=30).stdout.splitlines()
    except Exception:
        return None
    if not out:
        return None
    # prefer the file named after the symbol (its definition), else the first hit
    for f in out:
        if pathlib.Path(f).stem == needle.split("\\")[-1]:
            return f
    return out[0]


def verify_anchors(raw, source_text, cfg):
    """Keep anchors that are verbatim in the source and shaped like code.

    Returns ({anchor: file|None}, dropped_count). A None file means the anchor
    is real in the text but could not be found in the repo: shown as unlocated.
    """
    kept, dropped = {}, 0
    for a in raw or []:
        a = str(a).strip().strip("`")
        if a and a in source_text and looks_like_code(a, source_text):
            kept.setdefault(a, locate(a, cfg))
        elif a:
            dropped += 1
    return kept, dropped


# ---------------------------------------------------------------- mermaid ---
BANNED = re.compile(r"^\s*(style|classDef|linkStyle|click)\b|:::|<br", re.M)


def valid_mermaid(body):
    if not body or not body.strip():
        return False
    first = body.strip().splitlines()[0].strip()
    if not re.match(r"^(flowchart (TD|LR)|sequenceDiagram)$", first):
        return False
    if BANNED.search(body):
        return False
    return body.count("[") == body.count("]") and body.count("(") == body.count(")")


# ----------------------------------------------------------------- render ---
def render(slug, st, pages, batch):
    """Page text from stored state. The page is always a pure function of state."""
    fm = {"kind": st["kind"], "domain": st.get("domain", ""), "aliases": st.get("aliases", []),
          "sources": st["sources"], "created": st["created"], "updated": st["updated"],
          "validated": st.get("validated", ""), "validated_commit": st.get("validated_commit", ""),
          "status": st.get("status", "new")}
    def yaml(v):
        if isinstance(v, list):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) if re.search(r"[:#,\[\]]", x) else x for x in v) + "]"
        return str(v)
    out = ["---"] + [f"{k}: {yaml(v)}" for k, v in fm.items()] + ["---", f"# {st['name']}", "", st["plain"].strip(), ""]
    if st.get("explain"):
        out += ["## Explain like I am new", "", st["explain"].strip(), ""]
    for c in st.get("conflicts", []):
        out += [f"> [!warning] Conflict: {c}", ""]
    if st.get("flow"):
        out += ["## How it flows", "", "```mermaid", st["flow"].strip(), "```", ""]
    out += ["## Where it lives in code", ""]
    if st["anchors"]:
        for a, f in st["anchors"].items():
            if re.match(r"^[A-Z]{2,}-\d+$", a):
                out.append(f"- `{a}` (ticket)")
            elif f == a:
                out.append(f"- `{a}`")
            else:
                out.append(f"- `{a}`" + (f" in `{f}`" if f else "  (not located in repo)"))
    else:
        out.append("- (no code anchors confirmed yet)")
    out.append("")
    if st.get("read_next"):
        out += ["## Read next", ""]
        for r in st["read_next"]:
            out.append(f"- [[{r}]]" if (r in pages or r in batch) else f"- {r} (suggested)")
        out.append("")
    out += ["## Changelog", ""] + [f"- {l}" for l in reversed(st["changelog"])] + [""]
    return "\n".join(out)


# ----------------------------------------------------------------- upsert ---
def upsert(data, source_path, cfg, model_label, source_text):
    led = jload(cfg["ledger"], {"sources": {}, "rejected": [], "pages": {}})
    aliases = jload(cfg["aliases"], {})
    pages = led["pages"]
    source_name = source_path.stem
    report = {"source": source_name, "created": [], "updated": [], "rejected": [], "conflicts": [],
              "dropped_anchors": 0, "unlocated": [], "bad_mermaid": [], "resolved": []}
    batch = set()

    for c in data.get("concepts", []):
        slug, how = resolve_slug(c, cfg, aliases, pages)
        if slug in led["rejected"]:
            report["rejected"].append(slug); continue
        if how != "new":
            report["resolved"].append(f"{c.get('name')} -> {slug} ({how})")
        anchors, dropped = verify_anchors(c.get("anchors"), source_text, cfg)
        report["dropped_anchors"] += dropped
        report["unlocated"] += [f"{slug}: {a}" for a, f in anchors.items()
                                if f is None and not re.match(r"^[A-Z]{2,}-\d+$", a)]
        flow = c.get("flow") or ""
        if flow and not valid_mermaid(flow):
            report["bad_mermaid"].append(slug); flow = ""
        kind = c.get("kind") if c.get("kind") in KINDS else "concept"
        change = (c.get("change") or "updated").strip()

        st = pages.get(slug)
        if st is None:
            st = {"name": c.get("name", slug), "kind": kind, "domain": c.get("domain", ""), "aliases": [],
                  "sources": [], "created": today(), "anchors": {}, "changelog": [], "status": "new"}
            pages[slug] = st
            report["created"].append(slug)
            change = "created"
        else:
            report["updated"].append(f"{slug}: {change}")
        # model-owned body, replaced whole on every upsert. The NAME is sticky:
        # a second source calling it something else adds an alias, not a rename.
        new_name = (c.get("name") or "").strip()
        if new_name and new_name != st["name"] and st["sources"]:
            if new_name not in st["aliases"]:
                st["aliases"].append(new_name)
        elif new_name:
            st["name"] = new_name
        st["kind"] = kind
        st["domain"] = c.get("domain") or st.get("domain", "")
        st["plain"] = c.get("plain") or st.get("plain") or c.get("definition", "")
        st["explain"] = c.get("explain", st.get("explain", ""))
        st["flow"] = flow or st.get("flow", "")
        st["read_next"] = c.get("read_next", st.get("read_next", []))
        st["conflicts"] = c.get("conflicts", [])
        report["conflicts"] += [f"{slug}: {x}" for x in st["conflicts"]]
        # script-owned bookkeeping
        for a, f in anchors.items():
            st["anchors"].setdefault(a, f)
            if f and not st["anchors"][a]:
                st["anchors"][a] = f
        if source_name not in st["sources"]:
            st["sources"].append(source_name)
        for al in [st["name"]] + list(c.get("aliases") or []):
            k = normalise(al)
            if k and k not in aliases:
                aliases[k] = slug
            if al != st["name"] and al not in st["aliases"]:
                st["aliases"].append(al)
        st["updated"] = today()
        st["status"] = "conflict" if st["conflicts"] else st.get("status", "new")
        if data.get("validated"):
            st["validated"] = today()
            st["validated_commit"] = git_head(cfg)
            st["status"] = "conflict" if st["conflicts"] else "ok"
        st["changelog"].append(f"{today()} from `{source_name}`: {change}")
        batch.add(slug)

    cfg["concepts"].mkdir(parents=True, exist_ok=True)
    for slug in batch:
        (cfg["concepts"] / f"{slug}.md").write_text(render(slug, pages[slug], pages, batch))

    led["sources"][str(source_path)] = {"sha256": sha(source_text), "ingested_at": today(),
                                        "model": model_label, "concepts": sorted(batch)}
    jsave(cfg["ledger"], led)
    jsave(cfg["aliases"], aliases)
    write_index(cfg, pages)
    append_log(cfg, f"{today()} ingest `{source_name}` with {model_label}: "
                    f"{len(report['created'])} created, {len(report['updated'])} updated")
    archived = archive(source_path, cfg)
    write_review(cfg, report, archived)
    return report


def git_head(cfg):
    repo = cfg.get("code_repo")
    if not repo:
        return ""
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def archive(source_path, cfg):
    """Inbox files move to the archive after ingest. Other sources stay put."""
    try:
        source_path.resolve().relative_to(cfg["inbox"].resolve())
    except ValueError:
        return None
    cfg["archive"].mkdir(parents=True, exist_ok=True)
    dest = cfg["archive"] / source_path.name
    if dest.exists():
        dest = cfg["archive"] / f"{source_path.stem}-{today()}{source_path.suffix}"
    shutil.move(str(source_path), str(dest))
    return dest


def write_index(cfg, pages):
    """index.md + log.md make the vault a Karpathy-pattern wiki for /understand-knowledge."""
    by_domain = {}
    for slug, st in sorted(pages.items()):
        by_domain.setdefault(st.get("domain") or "unsorted", []).append((slug, st))
    out = ["# Concept index", "", f"{len(pages)} concepts. Generated by ingest.py, do not edit.", ""]
    for d, items in sorted(by_domain.items()):
        out += [f"## {d}", ""]
        for slug, st in items:
            out.append(f"- [[{slug}]] — {st.get('plain', '').strip()}")
        out.append("")
    (cfg["concepts"] / "index.md").write_text("\n".join(out))


def append_log(cfg, line):
    p = cfg["concepts"] / "log.md"
    if not p.exists():
        p.write_text("# Ingest log\n\n")
    with p.open("a") as f:
        f.write(f"- {line}\n")


def write_review(cfg, r, archived):
    cfg["reviews"].mkdir(parents=True, exist_ok=True)
    p = cfg["reviews"] / f"{today()}.md"
    if not p.exists():
        p.write_text(f"# Review {today()}\n\nTick when checked. Delete junk pages, then `python3 ingest.py --reject <slug>` so they stay gone.\n")
    out = [f"\n## {r['source']}" + (f"  (archived)" if archived else ""), ""]
    for s in r["created"]:
        out.append(f"- [ ] NEW [[{s}]]")
    for s in r["updated"]:
        out.append(f"- [ ] UPDATED {s}")
    for s in r["resolved"]:
        out.append(f"- merged into existing: {s}")
    for s in r["conflicts"]:
        out.append(f"- [ ] CONFLICT {s}")
    for s in r["unlocated"]:
        out.append(f"- anchor not found in repo: {s}")
    for s in r["bad_mermaid"]:
        out.append(f"- diagram dropped (invalid Mermaid): {s}")
    for s in r["rejected"]:
        out.append(f"- skipped, on rejected list: {s}")
    out.append(f"- anchors dropped as invented or prose: {r['dropped_anchors']}")
    with p.open("a") as f:
        f.write("\n".join(out) + "\n")
    return p


# ------------------------------------------------------------------ local ---
LOCAL_SCHEMA = {"type": "object", "properties": {"concepts": {"type": "array", "items": {"type": "object",
    "properties": {"name": {"type": "string"}, "kind": {"type": "string", "enum": KINDS},
                   "plain": {"type": "string"}, "anchors": {"type": "array", "items": {"type": "string"}}},
    "required": ["name", "kind", "plain", "anchors"]}}}, "required": ["concepts"]}

LOCAL_SYSTEM = f"""You extract business CONCEPTS from technical documentation: things a colleague would
recognise by name in a meeting (SEPA Mandate, Quick Scan, Signicat Integration). Code is evidence,
never the concept: classes, methods, fields, files go in anchors, copied character for character.
Never translate a Dutch term into a second concept. kind is one of {", ".join(KINDS)}.
plain: one sentence, what it is and why it exists, no code words. Return 1-3 concepts for a section."""


def prose_only(text):
    t = re.sub(r"```.*?```", "", text, flags=re.S)
    return "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("|")).strip()


def chunks(text, target=4000, cap=6000):
    parts, cur = [], []
    for line in text.splitlines(keepends=True):
        if line.startswith("## ") and cur:
            parts.append("".join(cur)); cur = []
        cur.append(line)
    if cur:
        parts.append("".join(cur))
    pieces = []
    for p in parts:
        pieces += [p] if len(p) <= cap else [p[i:i + cap] for i in range(0, len(p), cap)]
    out, buf = [], ""
    for p in pieces:
        if buf and len(buf) + len(p) > target:
            out.append(buf); buf = p
        else:
            buf += p
    if buf.strip():
        out.append(buf)
    return out


def ask_local(cfg, section):
    body = {"model": cfg["model"], "stream": False, "think": False, "format": LOCAL_SCHEMA,
            "keep_alive": "30m", "options": {"num_ctx": cfg["ctx"], "temperature": 0.1},
            "messages": [{"role": "system", "content": LOCAL_SYSTEM},
                         {"role": "user", "content": "Extract the concepts from this section.\n\n" + section}]}
    req = urllib.request.Request(cfg["ollama"].rstrip("/") + "/api/chat", json.dumps(body).encode(),
                                 {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.load(r)
    try:
        return json.loads(d["message"]["content"]).get("concepts", [])
    except json.JSONDecodeError:
        return []


def local_extract(cfg, text):
    found = []
    for i, sec in enumerate(chunks(text), 1):
        prose = prose_only(sec)
        if len(prose) < 200:
            print(f"    chunk {i}: skipped (no prose)"); continue
        raw = ask_local(cfg, prose)
        raw = [c for c in raw if c.get("name") and not looks_like_code(c["name"], text)][:3]
        print(f"    chunk {i}: {len(raw)} concepts")
        found += raw
    return {"concepts": found}


# ----------------------------------------------------------------- status ---
def find_sources(cfg):
    out = []
    for d in cfg["sources"] + [cfg["inbox"]]:
        if d.exists():
            out += sorted(p for p in d.glob("*.md") if p.name.lower() not in ("readme.md", ".gitkeep"))
    return out


def status(cfg, led):
    pending = []
    for p in find_sources(cfg):
        rec = led["sources"].get(str(p))
        where = "inbox" if cfg["inbox"] in p.parents else "source"
        if not rec:
            state = "NEW"; pending.append(p)
        elif rec["sha256"] != sha(p.read_text()):
            state = "CHANGED"; pending.append(p)
        else:
            state = f"done {rec['ingested_at']} ({len(rec['concepts'])} concepts)"
        print(f"  {state:<34} {where:<7} {p.name}")
    print(f"\n  {len(pending)} pending, {len(led['pages'])} concept pages, {len(led['rejected'])} rejected")
    return pending


def index_json(cfg, led):
    return {"concepts": [{"slug": s, "name": st["name"], "kind": st["kind"], "domain": st.get("domain", ""),
                          "aliases": st.get("aliases", []), "plain": st.get("plain", "")}
                         for s, st in sorted(led["pages"].items())],
            "rejected": led["rejected"], "domains": cfg.get("domains", [])}


# ------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--from-json", metavar="FILE")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--source", metavar="FILE")
    ap.add_argument("--reject", metavar="SLUG")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--model", help="override kb.local.json model (local mode)")
    a = ap.parse_args()
    cfg = load_config()
    if a.model:
        cfg["model"] = a.model
    led = jload(cfg["ledger"], {"sources": {}, "rejected": [], "pages": {}})

    if a.index:
        print(json.dumps(index_json(cfg, led), indent=1, ensure_ascii=False)); return 0
    if a.review:
        print(cfg["reviews"] / f"{today()}.md"); return 0
    if a.reject:
        page = cfg["concepts"] / f"{a.reject}.md"
        if page.exists():
            page.unlink()
        led["pages"].pop(a.reject, None)
        if a.reject not in led["rejected"]:
            led["rejected"].append(a.reject)
        jsave(cfg["ledger"], led)
        write_index(cfg, led["pages"])
        print(f"rejected {a.reject}; it will not be recreated"); return 0
    if a.from_json or a.local:
        if not a.source:
            ap.error("--source FILE is required")
        src = pathlib.Path(a.source).expanduser().resolve()
        text = src.read_text()
        if a.from_json:
            data = json.loads(pathlib.Path(a.from_json).read_text())
            label = data.get("model", "claude-code")
        else:
            print(f"  {src.name} with {cfg['model']} (preview quality)")
            data, label = local_extract(cfg, text), cfg["model"]
        r = upsert(data, src, cfg, label, text)
        print(f"  {src.name}: {len(r['created'])} created, {len(r['updated'])} updated, "
              f"{len(r['conflicts'])} conflicts, {r['dropped_anchors']} anchors dropped, "
              f"{len(r['unlocated'])} unlocated")
        print(f"  review: {cfg['reviews'] / (today() + '.md')}")
        return 0
    status(cfg, led)
    return 0


if __name__ == "__main__":
    sys.exit(main())
