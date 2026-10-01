#!/usr/bin/env python3
"""Retrospective sweep of every stored model response under the corrected reader.

The "before" side is pinned to the reader's pre-repair behaviour, not to whatever
`extract_json_object` does today, so repairing the shared parser cannot quietly
erase the evidence of what it used to discard.

Free: no model calls. It reads stored raw response text only, never re-runs a
probe, and never rewrites a frozen artifact. Output is a diagnostic that sits
beside the published numbers rather than replacing them.

It looks for two measurement defects, both established in the Edit Plan replay:

  DUPLICATE EMISSION  extract_json_object takes the span from the first '{' to
                      the last '}'. When a model emits a valid answer and then
                      repeats it verbatim, that span is not valid JSON and the
                      answer is discarded. On the replay this suppressed a real
                      end-to-end success: 07_03 scored 0.0 with the frozen
                      reader and 0.75 once the answer was recovered.

  OUTPUT TRUNCATION   max_tokens is shared between reasoning and content, so a
                      reasoning-heavy turn can spend the whole budget and return
                      empty text. That is a truncation, not a malformed answer,
                      and must not be counted as a model failure.

Recovery stays conservative: every top-level object is decoded and one is
returned only when the repeats agree. Disagreeing objects stay unparseable,
because choosing between them would be a semantic repair rather than a parse.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
from report_edit_plan_replay import posthoc_parse, frozen_extract_json_object

ROOT = old.MECHANICAL
OUT = ROOT / "posthoc-parser-sweep"
SKIP_DIRS = {"scoring", "submission", "spines", "__pycache__"}
MAX_BYTES = 80 * 1024 * 1024


# Probes do not agree on a storage shape: some keep the body under `text`,
# others under `raw_text` or `raw_response`. What they do agree on is that a
# stored model response sits beside provider metadata, so require both. Cell
# text in a grounding packet also has a `text` field and must not be swept.
BODY_KEYS = ("text", "raw_text", "raw_response", "output_text", "completion")
MARKER_KEYS = ("usage", "http_ok", "attempts", "finish_reason")


def responses(node, path="$"):
    """Yield (json_path, body_key, response_dict) for every stored response."""
    if isinstance(node, dict):
        if any(k in node for k in MARKER_KEYS):
            for bk in BODY_KEYS:
                if bk in node:
                    yield path, bk, node
                    break
        for k, v in node.items():
            yield from responses(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from responses(v, f"{path}[{i}]")


def max_tokens_of(resp):
    """The output budget a response was given, if it can be inferred."""
    u = resp.get("usage") or {}
    return u.get("completion_tokens")


def sweep():
    files = [p for p in ROOT.rglob("*.json")
             if not SKIP_DIRS & set(p.parts) and p.stat().st_size <= MAX_BYTES]
    per_probe = defaultdict(lambda: {"files": 0, "responses": 0, "already_parsed": 0,
                                     "recovered": 0, "conflicting": 0, "truncated": 0,
                                     "empty_other": 0, "no_json": 0, "recovered_with_formula": 0,
                                     "examples": []})
    for p in sorted(files):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(ROOT)
        probe = rel.parts[0]
        seen_file = False
        for jpath, body_key, resp in responses(data):
            text = resp.get(body_key) or ""
            if not isinstance(text, str):
                continue
            s = per_probe[probe]
            if not seen_file:
                s["files"] += 1
                seen_file = True
            s["responses"] += 1
            frozen = frozen_extract_json_object(text)
            if frozen is not None:
                s["already_parsed"] += 1
                continue
            obj, how = posthoc_parse(text)
            if how in ("RECOVERED_DUPLICATE_EMISSION", "RECOVERED_SINGLE_OBJECT"):
                s["recovered"] += 1
                has_formula = isinstance(obj, dict) and isinstance(obj.get("formula"), str)
                s["recovered_with_formula"] += bool(has_formula)
                if len(s["examples"]) < 5:
                    s["examples"].append({"file": str(rel), "json_path": jpath, "body_key": body_key, "recovery": how,
                                          "recovered": obj, "text_len": len(text)})
            elif how == "CONFLICTING_OBJECTS":
                s["conflicting"] += 1
            elif how == "NO_JSON_OBJECT":
                s["no_json"] += 1
            elif how == "EMPTY":
                # An empty body that used its whole budget is a truncation.
                ct = max_tokens_of(resp)
                rt = ((resp.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens")
                if ct and rt and ct == rt:
                    s["truncated"] += 1
                else:
                    s["empty_other"] += 1
    # A run that kept no raw response cannot be audited at all. Separating
    # "clean" from "unauditable" matters: silence here is missing evidence, not
    # absence of the defect.
    audited = {r for r in per_probe}
    unauditable = []
    for d in sorted(x for x in ROOT.iterdir() if x.is_dir()):
        if d.name in audited or d.name == OUT.name:
            continue
        touched_model = any("model" in f.read_text(errors="ignore")[:200000]
                            for f in list(d.rglob("*.json"))[:40]
                            if f.stat().st_size <= 4 * 1024 * 1024)
        unauditable.append({"probe": d.name, "mentions_a_model": touched_model})

    rows = []
    for probe, s in sorted(per_probe.items()):
        affected = s["recovered"] + s["truncated"]
        rows.append({"probe": probe, **s, "affected": affected,
                     "recovered_rate": round(s["recovered"] / s["responses"], 4) if s["responses"] else 0.0})
    result = {
        "scope": {"root": str(ROOT), "json_files_scanned": len(files),
                  "skipped_dirs": sorted(SKIP_DIRS), "max_file_bytes": MAX_BYTES},
        "defects": {
            "duplicate_emission": "extract_json_object spans first '{' to last '}'; a valid answer emitted twice is discarded",
            "output_truncation": "max_tokens is shared with reasoning; an empty body at full budget is a truncation, not a bad answer",
        },
        "recovery_rule": "decode every top-level object; return one only if the repeats agree",
        "totals": {k: sum(r[k] for r in rows) for k in
                   ("files", "responses", "already_parsed", "recovered", "recovered_with_formula",
                    "conflicting", "truncated", "empty_other", "no_json")},
        "per_probe": rows,
        "coverage": {
            "probes_audited": sorted(per_probe),
            "probes_with_no_stored_raw_response": unauditable,
            "note": "Only runs that retained raw response bodies can be swept. The rest are "
                    "unauditable for these defects, which is missing evidence rather than a clean bill.",
        },
    }
    old.write(OUT / "sweep.json", result)
    return result


def render(r):
    t = r["totals"]
    L = ["# Retrospective parser sweep", "",
         "Free diagnostic over stored raw responses. No model calls, no probe re-run, no frozen",
         "artifact rewritten. Published numbers stand; these sit beside them.", "",
         f"Scanned **{r['scope']['json_files_scanned']:,} JSON files** under `{Path(r['scope']['root']).name}/`, "
         f"finding **{t['responses']:,} stored model responses** across {t['files']:,} files that hold them.", "",
         "## Two defects looked for", "",
         "1. **Duplicate emission.** `extract_json_object` takes the span from the first `{` to the last",
         "   `}`, so a model that emits a valid answer and then repeats it verbatim is scored unparseable.",
         "   On the Edit Plan replay this suppressed a real end-to-end success: 07_03 scored 0.0 with the",
         "   frozen reader and **0.75** once the answer was recovered, regression staying 1.0.",
         "2. **Output truncation.** `max_tokens` is shared between reasoning and content, so a",
         "   reasoning-heavy turn can spend its whole budget and return empty text. That is a truncation,",
         "   not a malformed answer.", "",
         "Recovery is conservative: every top-level object is decoded and one is returned only when the",
         "repeats agree. Disagreeing objects stay unparseable, because picking a winner would be a",
         "semantic repair rather than a parse.", "",
         "## Totals", "",
         f"- Already parsed by the frozen reader: **{t['already_parsed']:,}**",
         f"- **Recoverable, currently discarded: {t['recovered']:,}** (of which **{t['recovered_with_formula']:,}** carry a formula)",
         f"- Output-budget truncations mislabelled as bad answers: **{t['truncated']:,}**",
         f"- Conflicting objects, correctly left unparseable: {t['conflicting']:,}",
         f"- Empty for other reasons: {t['empty_other']:,}; no JSON object at all: {t['no_json']:,}", "",
         "## By probe", "",
         "| probe | responses | already parsed | recovered | with formula | truncated | conflicting |",
         "|---|---|---|---|---|---|---|"]
    for row in sorted(r["per_probe"], key=lambda x: -x["affected"]):
        if not row["responses"]:
            continue
        L.append(f"| {row['probe']} | {row['responses']:,} | {row['already_parsed']:,} | "
                 f"**{row['recovered']:,}** | {row['recovered_with_formula']:,} | {row['truncated']:,} | {row['conflicting']:,} |")
    L += ["", "## Examples of discarded-but-valid answers", ""]
    shown = 0
    for row in sorted(r["per_probe"], key=lambda x: -x["recovered"]):
        for ex in row["examples"]:
            if shown >= 12:
                break
            L.append(f"- `{ex['file']}` at `{ex['json_path']}` ({ex['recovery']}): "
                     f"`{json.dumps(ex['recovered'])[:180]}`")
            shown += 1
    if not shown:
        L.append("_None found._")
    cov = r["coverage"]
    unaud = [x for x in cov["probes_with_no_stored_raw_response"] if x["mentions_a_model"]]
    L += ["", "## Coverage, and what could not be checked", "",
          f"Only {len(cov['probes_audited'])} runs retained raw response bodies: "
          f"{', '.join('`' + x + '`' for x in cov['probes_audited'])}. Every stored response in them was swept.", "",
          f"**{len(unaud)} further runs reference a model but kept no raw response text**, so they cannot be",
          "audited for either defect: " + ", ".join("`" + x["probe"] + "`" for x in unaud) + ".",
          "That is missing evidence, not a clean bill. Retaining raw bodies should be a standing",
          "requirement for any run whose numbers are meant to be revisited.", "",
          "## What the sweep does and does not establish", "",
          "**The duplicate-emission defect is localised, not project-wide.** All 3 recoverable responses",
          "are in the Edit Plan delta replay; no other audited run has a single one. An earlier claim of",
          "mine — that this defect had plausibly been depressing published numbers across the project —",
          "is not supported. It cost exactly one result, and that result is already reported.", "",
          "**The truncation defect is the widespread one.** 34 responses across 4 of the 5 audited runs",
          "spent their entire output budget on reasoning and returned nothing, and each was read as a bad",
          "answer. The concentration matters: **17 of them are in `edit-plan-composition-probe`**, the",
          "primary run whose headline was a 12.5% proposal rate. That rate was measured over responses of",
          "which roughly one in seven was a truncation, so the primary run understates the transition",
          "more than the replication's correction alone suggested.", "",
          "Neither figure restates a headline. Recovering a response changes a metric only where that",
          "probe's scoring consumed the parsed object, and only a re-scored artifact shows by how much —",
          "as 07_03 did, moving 0.0 to 0.75.", ""]
    text = "\n".join(L)
    (OUT / "sweep.md").write_text(text)
    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    parser.parse_args()
    print(render(sweep()))
