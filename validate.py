#!/usr/bin/env python3
"""RAGgamuffin validate: does the knowledge base still match the code?

Two free levels, run every week before ingest. No model involved.

  level 1  every anchor on every page: does the file still exist, does the
           symbol still appear in the repo?  missing -> status dead-anchor
  level 2  drift: which repo files changed since the last validation, and
           which pages have anchors in those files?  touched -> status stale

Level 3 (a model re-reads a stale page against the current code) is done by
the /ingest-inbox skill on the pages this script flags, within a cap.

    python3 validate.py            run, rewrite pages, print summary
    python3 validate.py --json     machine-readable summary for the skill
    python3 validate.py --dry-run  report only, change nothing
"""
import argparse, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ingest  # noqa: E402  (shares config, ledger, locate, render)


def git(cfg, *args):
    return subprocess.run(["git", "-C", str(cfg["code_repo"])] + list(args),
                          capture_output=True, text=True, timeout=60).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = ingest.load_config()
    led = ingest.jload(cfg["ledger"], {"sources": {}, "rejected": [], "pages": {}})
    pages = led["pages"]
    if not cfg.get("code_repo") or not cfg["code_repo"].exists():
        print("no code_repo in kb.json; nothing to validate against"); return 1

    head = git(cfg, "rev-parse", "--short", "HEAD")
    last = led.get("validated_commit")
    touched = set(git(cfg, "diff", "--name-only", f"{last}..HEAD").splitlines()) if last else set()

    summary = {"head": head, "since": last, "files_changed": len(touched),
               "dead": [], "stale": [], "relocated": [], "ok": 0, "pages": len(pages)}
    for slug, st in pages.items():
        dead, stale = [], []
        for anchor, f in list(st["anchors"].items()):
            if "/" in anchor:                                   # a path anchor
                exists = (cfg["code_repo"] / anchor).exists()
            else:
                needle = anchor.split("::")[0].rstrip("()")
                exists = bool(git(cfg, "grep", "-l", "-F", "--", needle, "--", *cfg["code_globs"]))
            if not exists and not anchor.startswith(("MGT-", "TECH-")):
                dead.append(anchor)
                continue
            if f is None:                                        # try again to locate
                nf = ingest.locate(anchor, cfg)
                if nf:
                    st["anchors"][anchor] = nf
                    summary["relocated"].append(f"{slug}: {anchor} -> {nf}")
                    f = nf
            if f and f in touched:
                stale.append(f)
        if dead:
            st["status"] = "dead-anchor"
            summary["dead"].append({"slug": slug, "anchors": dead})
        elif stale:
            st["status"] = "stale"
            summary["stale"].append({"slug": slug, "files": sorted(set(stale))})
        elif st.get("conflicts"):
            st["status"] = "conflict"
        else:
            st["status"] = "ok"
            st["validated"] = ingest.today()
            st["validated_commit"] = head
            summary["ok"] += 1

    if not a.dry_run:
        led["validated_commit"] = head
        ingest.jsave(cfg["ledger"], led)
        for slug, st in pages.items():
            (cfg["concepts"] / f"{slug}.md").write_text(ingest.render(slug, st, pages, set()))
        ingest.append_log(cfg, f"{ingest.today()} validate against {head}: {summary['ok']} ok, "
                               f"{len(summary['stale'])} stale, {len(summary['dead'])} dead-anchor")
        if summary["dead"] or summary["stale"]:
            rev = cfg["reviews"]; rev.mkdir(parents=True, exist_ok=True)
            with (rev / f"{ingest.today()}.md").open("a") as fh:
                fh.write(f"\n## validate against {head}\n\n")
                for d in summary["dead"]:
                    fh.write(f"- [ ] DEAD ANCHOR [[{d['slug']}]]: {', '.join(d['anchors'])}\n")
                for s in summary["stale"]:
                    fh.write(f"- [ ] STALE [[{s['slug']}]]: {', '.join(s['files'])}\n")

    if a.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"validated {len(pages)} pages against {head}"
              + (f" (changes since {last}: {len(touched)} files)" if last else " (first run, no drift check)"))
        print(f"  ok {summary['ok']}  stale {len(summary['stale'])}  dead-anchor {len(summary['dead'])}"
              f"  relocated {len(summary['relocated'])}")
        for d in summary["dead"]:
            print(f"  DEAD  {d['slug']}: {', '.join(d['anchors'])}")
        for s in summary["stale"]:
            print(f"  STALE {s['slug']}: {', '.join(s['files'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
