#!/usr/bin/env python3
"""Seed the inbox from an understand-anything graph.

`/understand` leaves a 23k-node map in `<repo>/.ua/`. Most node summaries are
boilerplate ("Class X in X.php with 5 methods"), but two parts of it are real
teaching material written at business level:

  tour[]          a guided walkthrough, one step per architectural area
  domain-graph    domains, their flows, and the steps inside each flow

This script turns those into inbox documents, one per domain and one per tour
step, with the file paths the graph knows about listed as anchors. No model is
involved. The weekly ingest then upserts them into concept pages like any other
document, so the machine map feeds the notebook without the dashboard.

    python3 seed_from_ua.py                 # uses code_repo from kb.json
    python3 seed_from_ua.py ~/Herd/mogelijk-mbi
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ingest  # noqa: E402

CODEISH = re.compile(r"\b(?:[A-Za-z0-9_]+/[A-Za-z0-9_./-]+\.[a-z]+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+(?:::[a-zA-Z_]+)?(?:\(\))?|[A-Z][A-Z0-9_]{3,}|[a-zA-Z_]+\.[a-z_]+\.php)\b")


def anchors_in(text):
    seen, out = set(), []
    for m in CODEISH.findall(text):
        m = m.rstrip(".")
        if m not in seen and not m.endswith(("Signicat", "Laravel")) and m not in ("Vue", "Blade"):
            seen.add(m); out.append(m)
    return out


def main():
    cfg = ingest.load_config()
    repo = pathlib.Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else cfg["code_repo"]
    ua = repo / (".understand-anything" if (repo / ".understand-anything").exists() else ".ua")
    kg_path, dg_path = ua / "knowledge-graph.json", ua / "domain-graph.json"
    if not kg_path.exists():
        print(f"no knowledge-graph.json in {ua}; run /understand there first"); return 1
    kg = json.loads(kg_path.read_text())
    by_id = {n["id"]: n for n in kg["nodes"]}
    project = kg.get("project", {}).get("name", repo.name)
    stamp = kg.get("project", {}).get("analyzedAt", "")[:10] or "unknown-date"
    inbox = cfg["inbox"]; inbox.mkdir(parents=True, exist_ok=True)
    written = []

    def write(name, lines):
        p = inbox / f"ua-{name}.md"
        p.write_text("\n".join(lines).rstrip() + "\n")
        written.append(p.name)

    # --- tour steps: one document each ---
    for t in kg.get("tour", []):
        files = [by_id[i].get("filePath") for i in t.get("nodeIds", []) if i in by_id and by_id[i].get("filePath")]
        slug = ingest.slugify(t["title"])
        lines = [f"# {t['title']}", "", f"_From the `/understand` tour of {project}, step {t.get('order')}, graph of {stamp}._", "",
                 t.get("description", "").strip(), ""]
        if files:
            lines += ["## Files the tour points at", ""] + [f"- `{f}`" for f in files] + [""]
        extra = [a for a in anchors_in(t.get("description", "")) if a not in files]
        if extra:
            lines += ["## Identifiers mentioned", ""] + [f"- `{a}`" for a in extra] + [""]
        write(f"tour-{t.get('order', 0):02d}-{slug}", lines)

    # --- domain graph: one document per domain with its flows and steps ---
    if dg_path.exists():
        dg = json.loads(dg_path.read_text())
        nodes = {n["id"]: n for n in dg["nodes"]}
        flows_of, steps_of = {}, {}
        for e in dg["edges"]:
            if e["type"] == "contains_flow":
                flows_of.setdefault(e["source"], []).append(e["target"])
            elif e["type"] == "flow_step":
                steps_of.setdefault(e["source"], []).append(e["target"])
        dproj = dg.get("project", {}).get("name", project)
        for did, d in nodes.items():
            if d["type"] != "domain":
                continue
            lines = [f"# {d['name']}", "", f"_From the `/understand-domain` graph of {dproj}, {stamp}._", "",
                     d.get("summary", "").strip(), ""]
            if d.get("tags"):
                lines += ["Tags: " + ", ".join(d["tags"]), ""]
            for fid in flows_of.get(did, []):
                f = nodes[fid]
                lines += [f"## Flow: {f['name']}", "", f.get("summary", "").strip(), ""]
                for sid in steps_of.get(fid, []):
                    s = nodes[sid]
                    lines += [f"- **{s['name']}**: {s.get('summary', '').strip()}"]
                lines.append("")
            text = "\n".join(lines)
            found = anchors_in(text)
            if found:
                lines += ["## Identifiers mentioned", ""] + [f"- `{a}`" for a in found] + [""]
            write(f"domain-{ingest.slugify(d['name'])}", lines)

    print(f"seeded {len(written)} documents into {inbox}:")
    for w in written:
        print("  ", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
