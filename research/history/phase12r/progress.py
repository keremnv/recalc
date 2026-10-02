"""Operator progress only; does not read scores or classify historical evidence."""
import json,os
from pathlib import Path
OUT=Path(__file__).resolve().parent
count=sum(1 for _ in open(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'));manifest=json.loads((OUT/'POPULATION_MANIFEST.json').read_text());print(json.dumps({'committed':count,'eligible':len(manifest['eligible']),'stage_state':json.loads((OUT/'POST_REPLAY_STAGE_STATE.json').read_text()) if (OUT/'POST_REPLAY_STAGE_STATE.json').exists() else 'primary replay active'}))
