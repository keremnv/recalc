#!/usr/bin/env python3
"""Offline TASK → V1 obligation compilation (parsing / specification preservation).

Phases:
  freeze  — persist parser_prompt.txt + parser_schema.json BEFORE any model call
  oracle  — persist ungrounded task-text oracles BEFORE any parser output
  run     — one independent parse per task per model (instruction + prompt only)
  score   — deterministic matching / taxonomy / spec-preservation
  report  — markdown summary
  all     — freeze, oracle, run, score, report

Does not modify LibreCalc, workbooks, or the official scorer. No grounding, no
agent, no LLM judge, no prompt edits after outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from task_obligation_compile import (  # noqa: E402
    KNOWN_SPEC_CHECKS,
    NORMALIZATION_TABLE,
    PARSER_PROMPT,
    PARSER_SCHEMA,
    SCHEMA_NAME,
    V1_FIELDS,
    aggregate_scores,
    build_ungrounded_oracle,
    compare_models,
    complexity_record,
    critical_requirements,
    extract_json_object,
    gate_verdict,
    known_case_analysis,
    normalize_prediction,
    score_task,
)
from task_obligation_shape import family_of  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model/dataset.json"
SHAPE_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-shape-probe"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-compile-probe"
)
ENV_FILE = ROOT / ".env"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GLM_MODEL = "z-ai/glm-5.3-flash"
GPT_MODEL = "openai/gpt-5.6-sol"
MODELS = {
    "glm": {
        "id": GLM_MODEL,
        "label": "z-ai/glm-5.3-flash",
        "reasoning": "low",
        "temperature": 0.0,
        "max_tokens": 8192,
    },
    "gpt": {
        "id": GPT_MODEL,
        "label": "openai/gpt-5.6-sol",
        "reasoning": "medium",
        "temperature": 0.0,
        "max_tokens": 8192,
    },
}


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def _tasks() -> list[dict[str, str]]:
    return json.loads(DATA.read_text())


def _split_map() -> dict[str, str]:
    split = json.loads((SHAPE_OUT / "family_split.json").read_text())
    out = {}
    for fam in split["discovery_families"]:
        out[fam] = "discovery"
    for fam in split["validation_families"]:
        out[fam] = "validation"
    for fam in split["held_out_families"]:
        out[fam] = "held_out"
    return out


def cmd_freeze() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / "parser_prompt.txt"
    schema_path = OUT / "parser_schema.json"
    if prompt_path.exists() or schema_path.exists():
        existing_prompt = prompt_path.read_text() if prompt_path.exists() else ""
        if existing_prompt and existing_prompt != PARSER_PROMPT:
            raise SystemExit("Refusing to overwrite a frozen parser prompt.")
    prompt_path.write_text(PARSER_PROMPT)
    schema_path.write_text(json.dumps(PARSER_SCHEMA, indent=2) + "\n")
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema": SCHEMA_NAME,
        "prompt_sha_len": len(PARSER_PROMPT),
        "normalization_table": NORMALIZATION_TABLE,
        "models": MODELS,
        "prompt_contains_spreadsheetbench_examples": False,
        "tuned_on_outputs": False,
    }
    path = _write("freeze.json", payload)
    print(f"FREEZE {path}", flush=True)
    return payload


def cmd_oracle() -> dict[str, Any]:
    dest = OUT / "oracle_obligations.json"
    if dest.exists():
        payload = json.loads(dest.read_text())
        print(f"ORACLE reuse {dest} n={payload['n_tasks']}", flush=True)
        return payload
    freeze_path = OUT / "parser_prompt.txt"
    if not freeze_path.exists():
        cmd_freeze()
    split = _split_map()
    tasks = []
    by_split: dict[str, list[str]] = defaultdict(list)
    for task in _tasks():
        tid = task["id"]
        instruction = task["instruction"]
        family = family_of(tid)
        obligations = build_ungrounded_oracle(instruction)
        rec = {
            "task": tid,
            "family": family,
            "split": split[family],
            "instruction": instruction,
            "obligations": obligations,
            "critical_requirements": critical_requirements(tid, obligations),
            "complexity": complexity_record(tid, instruction, obligations),
            "contains_target_address": False,
            "contains_golden_formula": False,
        }
        tasks.append(rec)
        by_split[split[family]].append(tid)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": (
            "Constructed from raw SpreadsheetBench Financial_Model task text plus "
            "frozen TASK_OBLIGATION_SHAPE_V1 field definitions and the previous "
            "probe's requirement ledger. No workbook, golden, address, or formula."
        ),
        "schema": SCHEMA_NAME,
        "n_tasks": len(tasks),
        "population": {k: sorted(v) for k, v in by_split.items()},
        "n_by_split": {k: len(v) for k, v in by_split.items()},
        "tasks": tasks,
    }
    path = _write("oracle_obligations.json", payload)
    print(f"ORACLE {path} n={len(tasks)}", flush=True)
    return payload


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content or "")


def openrouter_chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    reasoning: str | None,
    temperature: float | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "librecalc-task-obligation-compile",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"http_ok": True, "payload": payload}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"http_ok": False, "status": exc.code, "detail": detail}
    except urllib.error.URLError as exc:
        return {"http_ok": False, "status": 0, "detail": str(exc.reason)}


def _usage_cost(usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost": usage.get("cost") or (usage.get("total_cost")),
    }


def cmd_run(*, model_key: str | None = None, force: bool = False) -> dict[str, Any]:
    if not (OUT / "parser_prompt.txt").exists():
        cmd_freeze()
    oracle = cmd_oracle()
    prompt = (OUT / "parser_prompt.txt").read_text()
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY must be set in the environment or repo .env")
    keys = [model_key] if model_key else list(MODELS)
    summary: dict[str, Any] = {"models": {}}
    for key in keys:
        spec = MODELS[key]
        raw_path = OUT / f"calls_{key}.jsonl"
        summary_path = OUT / f"parses_{key}.json"
        done: dict[str, dict[str, Any]] = {}
        if summary_path.exists() and not force:
            done = {row["task"]: row for row in json.loads(summary_path.read_text())["calls"]}
        results = list(done.values())
        if force:
            raw_path.write_text("")
            results = []
            done = {}
        OUT.mkdir(parents=True, exist_ok=True)
        jobs = [row for row in oracle["tasks"] if row["task"] not in done]
        with raw_path.open("a", encoding="utf-8") as raw:
            for index, task in enumerate(jobs, 1):
                tid = task["task"]
                user = (
                    "Compile the following task instruction into TASK_OBLIGATION_SHAPE_V1 JSON.\n\n"
                    f"TASK INSTRUCTION:\n{task['instruction']}"
                )
                print(f"CALL {key} {index}/{len(jobs)} {tid}", flush=True)
                started = time.perf_counter()
                attempt = 0
                http: dict[str, Any] = {}
                include_reasoning = True
                temperature: float | None = spec["temperature"]
                while attempt < 8:
                    attempt += 1
                    http = openrouter_chat(
                        api_key=api_key,
                        model=spec["id"],
                        system=prompt,
                        user=user,
                        max_tokens=spec["max_tokens"],
                        reasoning=spec["reasoning"] if include_reasoning else None,
                        temperature=temperature,
                    )
                    if http.get("http_ok"):
                        break
                    status = http.get("status")
                    detail = str(http.get("detail") or "").lower()
                    if status == 400 and include_reasoning and "reasoning" in detail:
                        include_reasoning = False
                        continue
                    if status == 400 and temperature is not None and "temperature" in detail:
                        temperature = None
                        continue
                    if status in {429, 502, 503, 504, 0}:
                        time.sleep(min(30, 2 ** attempt))
                        continue
                    break
                elapsed = round(time.perf_counter() - started, 3)
                record: dict[str, Any] = {
                    "task": tid,
                    "family": task["family"],
                    "split": task["split"],
                    "model": spec["id"],
                    "model_key": key,
                    "elapsed_s": elapsed,
                    "attempts": attempt,
                    "self_corrected": False,
                }
                if not http.get("http_ok"):
                    record.update({"valid": False, "error": http, "obligations": []})
                else:
                    payload = http["payload"]
                    text = _message_text(payload)
                    record["raw_text"] = text
                    record["usage"] = _usage_cost(payload.get("usage"))
                    parsed = extract_json_object(text)
                    obligations = normalize_prediction(parsed)
                    record["valid"] = bool(parsed and isinstance(parsed.get("obligations"), list))
                    record["obligations"] = obligations
                    raw.write(
                        json.dumps(
                            {
                                "task": tid,
                                "model": spec["id"],
                                "elapsed_s": elapsed,
                                "usage": record.get("usage"),
                                "raw_text": text,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    raw.flush()
                results.append(record)
                summary_path.write_text(
                    json.dumps(
                        {
                            "generated_at": datetime.now(UTC).isoformat(),
                            "model": spec,
                            "n": len(results),
                            "calls": results,
                        },
                        indent=2,
                    )
                    + "\n"
                )
        summary["models"][key] = {"n": len(results), "path": str(summary_path)}
        print(f"RUN {key} n={len(results)}", flush=True)
    return summary


def _score_model(key: str, oracle: dict[str, Any]) -> dict[str, Any]:
    path = OUT / f"parses_{key}.json"
    if not path.exists():
        raise SystemExit(f"missing {path}; run first")
    calls = {row["task"]: row for row in json.loads(path.read_text())["calls"]}
    oracles = {row["task"]: row for row in oracle["tasks"]}
    rows = []
    for tid, o_row in oracles.items():
        call = calls.get(tid)
        pred = (call or {}).get("obligations") or []
        valid = bool(call and call.get("valid"))
        scored = score_task(
            task_id=tid,
            instruction=o_row["instruction"],
            oracle=o_row["obligations"],
            pred=pred,
            parse_valid=valid,
        )
        scored["split"] = o_row["split"]
        scored["family"] = o_row["family"]
        scored["evaluable"] = True
        scored["model"] = MODELS[key]["id"]
        scored["usage"] = (call or {}).get("usage")
        scored["elapsed_s"] = (call or {}).get("elapsed_s")
        scored["known_cases"] = known_case_analysis(tid, o_row["instruction"], pred)
        rows.append(scored)
    overall = aggregate_scores(rows)
    by_split = {name: aggregate_scores(rows, name) for name in ("discovery", "validation", "held_out")}
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_comp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[row["complexity"]["obligation_bucket"]].append(row)
        by_comp[row["complexity"]["composition"]].append(row)
    complexity = {
        "obligation_bucket": {
            bucket: {
                "n": len(items),
                "TASK_SPEC_PRESERVATION_RATE": aggregate_scores(items)["TASK_SPEC_PRESERVATION_RATE"],
                "CRITICAL_REQUIREMENT_RECALL": aggregate_scores(items)["CRITICAL_REQUIREMENT_RECALL"],
            }
            for bucket, items in sorted(by_bucket.items())
        },
        "composition": {
            name: {
                "n": len(items),
                "TASK_SPEC_PRESERVATION_RATE": aggregate_scores(items)["TASK_SPEC_PRESERVATION_RATE"],
                "CRITICAL_REQUIREMENT_RECALL": aggregate_scores(items)["CRITICAL_REQUIREMENT_RECALL"],
            }
            for name, items in sorted(by_comp.items())
        },
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": MODELS[key],
        "overall": overall,
        "by_split": by_split,
        "complexity": complexity,
        "tasks": rows,
    }
    _write(f"score_{key}.json", payload)
    return payload


def _cost_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = 0
    cost = 0.0
    n_cost = 0
    for row in rows:
        usage = row.get("usage") or {}
        if usage.get("total_tokens"):
            tokens += int(usage["total_tokens"])
        if usage.get("cost") is not None:
            try:
                cost += float(usage["cost"])
                n_cost += 1
            except (TypeError, ValueError):
                pass
    return {"total_tokens": tokens, "cost": round(cost, 6) if n_cost else None, "n_with_cost": n_cost}


def _examples(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def first(code: str) -> dict[str, Any] | None:
        for row in rows:
            hits = [e for e in row["errors"] if e["code"] == code]
            if hits:
                return {"task": row["task"], "split": row["split"], "error": hits[0]}
        return None

    success = None
    for row in sorted(rows, key=lambda r: r["complexity"]["n_oracle_obligations"], reverse=True):
        if row["task_spec_preserved"] and row["complexity"]["n_oracle_obligations"] >= 4:
            success = {
                "task": row["task"],
                "n_oracle": row["n_oracle"],
                "n_pred": row["n_pred"],
                "then_edges": row["complexity"]["n_then_edges"],
            }
            break
    return {
        "omitted_clause": first("OMITTED_CLAUSE"),
        "omitted_constraint": first("OMITTED_CONSTRAINT"),
        "wrong_attachment": first("WRONG_ATTACHMENT"),
        "unsupported_inference": first("UNSUPPORTED_INFERENCE"),
        "successful_complex_parse": success,
    }


def cmd_score() -> dict[str, Any]:
    oracle = json.loads((OUT / "oracle_obligations.json").read_text())
    glm = _score_model("glm", oracle)
    gpt = _score_model("gpt", oracle) if (OUT / "parses_gpt.json").exists() else None
    comparison = compare_models(glm["tasks"], gpt["tasks"] if gpt else []) if gpt else []
    cats = dict(Counter(row["category"] for row in comparison))
    known = []
    for check in KNOWN_SPEC_CHECKS:
        item = {"id": check["id"], "label": check["label"], "task": check["task"]}
        for key, scored in (("glm", glm), ("gpt", gpt)):
            if not scored:
                continue
            by_t = {row["task"]: row for row in scored["tasks"]}
            row = by_t.get(check["task"])
            hits = [k for k in row["known_cases"] if k["id"] == check["id"]] if row else []
            item[key] = hits[0] if hits else None
        known.append(item)
    n_ambiguous = sum(1 for row in glm["tasks"] if row["evaluation_ambiguous"])
    if gpt:
        n_ambiguous += sum(1 for row in gpt["tasks"] if row["evaluation_ambiguous"])
    verdict = gate_verdict(
        held=glm["by_split"]["held_out"],
        glm_held=glm["by_split"]["held_out"],
        gpt_held=(gpt["by_split"]["held_out"] if gpt else {"invention_tasks": 0}),
        glm_overall=glm["overall"],
        gpt_overall=(gpt["overall"] if gpt else glm["overall"]),
        comparison=comparison,
        n_ambiguous=n_ambiguous,
        n_evaluable=glm["overall"]["n_evaluable"] + (gpt["overall"]["n_evaluable"] if gpt else 0),
    )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "headline": {
            "HELD_OUT_TASK_SPEC_PRESERVATION_RATE_GLM": glm["by_split"]["held_out"]["TASK_SPEC_PRESERVATION_RATE"],
            "HELD_OUT_TASK_SPEC_PRESERVATION_RATE_GPT": (
                gpt["by_split"]["held_out"]["TASK_SPEC_PRESERVATION_RATE"] if gpt else None
            ),
        },
        "glm": {k: glm[k] for k in ("overall", "by_split", "complexity") if k in glm},
        "gpt": {k: gpt[k] for k in ("overall", "by_split", "complexity") if k in gpt} if gpt else None,
        "comparison_counts": cats,
        "comparison": comparison,
        "known_cases": known,
        "examples_glm": _examples(glm["tasks"]),
        "examples_gpt": _examples(gpt["tasks"]) if gpt else None,
        "cost": {
            "glm": _cost_summary(glm["tasks"]),
            "gpt": _cost_summary(gpt["tasks"]) if gpt else None,
        },
        "verdict": verdict,
        "v1_fields": V1_FIELDS,
    }
    path = _write("summary.json", payload)
    print(f"SCORE {path} gate={verdict['gate']}", flush=True)
    return payload


def cmd_report() -> Path:
    summary = json.loads((OUT / "summary.json").read_text())
    oracle = json.loads((OUT / "oracle_obligations.json").read_text())
    freeze = json.loads((OUT / "freeze.json").read_text())
    lines = [
        "# Task → obligation compilation (specification preservation)",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Headline",
        "",
        f"- GLM held-out TASK_SPEC_PRESERVATION_RATE: **{summary['headline']['HELD_OUT_TASK_SPEC_PRESERVATION_RATE_GLM']}**",
        f"- GPT held-out TASK_SPEC_PRESERVATION_RATE: **{summary['headline']['HELD_OUT_TASK_SPEC_PRESERVATION_RATE_GPT']}**",
        f"- Gate: **{summary['verdict']['gate']}**",
        f"- {summary['verdict']['conclusion']}",
        "",
        "## 1. Task population by split",
        "",
        f"- discovery ({oracle['n_by_split'].get('discovery', 0)}): {', '.join(oracle['population']['discovery'])}",
        f"- validation ({oracle['n_by_split'].get('validation', 0)}): {', '.join(oracle['population']['validation'])}",
        f"- held_out ({oracle['n_by_split'].get('held_out', 0)}): {', '.join(oracle['population']['held_out'])}",
        "",
        "## 2. Frozen parser prompt",
        "",
        "Persisted at `parser_prompt.txt`. Schema instructions only; no SpreadsheetBench examples;",
        f"not tuned on outputs (`tuned_on_outputs={freeze['tuned_on_outputs']}`).",
        "",
        "## 3. Output schema",
        "",
        "Persisted at `parser_schema.json` (`TASK_OBLIGATION_SHAPE_V1`).",
        "",
        "## 4. Oracle source",
        "",
        oracle["source"],
        "",
        "## 9–11. Rates",
        "",
    ]
    for key in ("glm", "gpt"):
        block = summary.get(key)
        if not block:
            continue
        lines += [f"### {key.upper()}", ""]
        for split_name, rec in [("overall", block["overall"]), *block["by_split"].items()]:
            if split_name != "overall" and isinstance(rec, dict) is False:
                continue
        for name, rec in [("overall", block["overall"])] + [(k, block["by_split"][k]) for k in ("discovery", "validation", "held_out")]:
            lines.append(
                f"- {name}: spec={rec['TASK_SPEC_PRESERVATION_RATE']} "
                f"crit_recall={rec['CRITICAL_REQUIREMENT_RECALL']} "
                f"all_crit={rec['ALL_CRITICAL_REQUIREMENTS_PRESERVED_RATE']} "
                f"loss_tasks={rec['loss_tasks']} invention_tasks={rec['invention_tasks']}"
            )
        lines.append("")
        lines.append("Error counts (overall):")
        for code, n in sorted(block["overall"]["error_counts"].items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {code}: {n}")
        lines.append("")
        lines.append("Field P/R:")
        for field, pr in block["overall"]["field_pr"].items():
            lines.append(f"- {field}: P={pr['precision']} R={pr['recall']} tp={pr['tp']} fp={pr['fp']} fn={pr['fn']}")
        lines.append("")
        lines.append("Complexity (obligation count):")
        for bucket, rec in block["complexity"]["obligation_bucket"].items():
            lines.append(
                f"- {bucket}: n={rec['n']} spec={rec['TASK_SPEC_PRESERVATION_RATE']} crit={rec['CRITICAL_REQUIREMENT_RECALL']}"
            )
        lines.append("")
        lines.append("Composition:")
        for name, rec in block["complexity"]["composition"].items():
            lines.append(
                f"- {name}: n={rec['n']} spec={rec['TASK_SPEC_PRESERVATION_RATE']} crit={rec['CRITICAL_REQUIREMENT_RECALL']}"
            )
        lines.append("")
        ov = block["overall"]
        lines += [
            f"- boilerplate-as-obligation rate: {ov['boilerplate_as_obligation_rate']}",
            f"- workbook-inference tasks: {ov['workbook_inference_tasks']}",
            f"- exact-span-valid: {ov['span_exact_rate']}",
            f"- normalized-span-valid: {ov['span_normalized_rate']}",
            "",
        ]
    lines += ["## 15. GLM vs GPT", ""]
    for cat, n in sorted(summary.get("comparison_counts", {}).items()):
        lines.append(f"- {cat}: {n}")
    lines += ["", "## 14. Known-case specification checks", ""]
    for row in summary["known_cases"]:
        glm_s = row.get("glm") or {}
        gpt_s = row.get("gpt") or {}
        lines.append(
            f"- {row['label']}: GLM ok={glm_s.get('ok')} missing={glm_s.get('missing')} invented={glm_s.get('invented')}; "
            f"GPT ok={gpt_s.get('ok')} missing={gpt_s.get('missing')} invented={gpt_s.get('invented')}"
        )
    lines += ["", "## 16. Representative errors (GLM)", ""]
    for name, rec in (summary.get("examples_glm") or {}).items():
        lines.append(f"- {name}: {rec}")
    lines += ["", "## 17. Verdict", "", f"**{summary['verdict']['gate']}** — {summary['verdict']['conclusion']}", ""]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    print(f"REPORT {dest}", flush=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd",
        choices=["freeze", "oracle", "run", "score", "report", "all"],
    )
    parser.add_argument("--model", choices=["glm", "gpt"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.cmd == "freeze":
        cmd_freeze()
    elif args.cmd == "oracle":
        cmd_oracle()
    elif args.cmd == "run":
        cmd_run(model_key=args.model, force=args.force)
    elif args.cmd == "score":
        cmd_score()
    elif args.cmd == "report":
        cmd_report()
    else:
        cmd_freeze()
        cmd_oracle()
        cmd_run(model_key=args.model, force=args.force)
        cmd_score()
        cmd_report()


if __name__ == "__main__":
    main()
