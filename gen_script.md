# LLM Implicit Augmentation — Reproduction Log

Explicit→Implicit hate-speech augmentation for **StereoQueerEval 2027** (EN/IT/NL).
Each `yes_explicit` training comment is rephrased by an LLM into `n_variants` label-preserving
`yes_implicit` (veiled) comments. Outputs are written into the exact 7-column SemEval TSV schema
and an audit JSON registry.

## Scripts

| File | Purpose |
|---|---|
| `gen/llm_implicit_augment.py` | Production script: single-row **and** multi-row batch prompting, Gemini & Groq, rate limiting, resume/checkpointing |
| `scripts/llm_implicit_augment.py` | Simpler English single-variant script (same output schema) |

Both load API keys from `.env` (repo root) via `auto_load_dotenv()`.
`.env` must contain `GEMINI_API_KEY` and `GROQ_API_KEY` (values may be wrapped in double quotes — the loader strips them).

## Environment (2026-09-28, Windows, PowerShell 5.1)

```powershell
python -m pip install google-genai   # verified ==2.25.0
python -m pip install openai         # verified ==3.19.2
```

## Outputs

- `LGBT/outputs.json` — audit registry (`items[]` keyed by `source_id`; contains `original`, `variants`,
  `stereotype`, `target`, `lang`; per-run `api`/`model`/`batch_size` meta).
- `LGBT/SynthImplicit_{LANG}_training.tsv` — corpus-format TSV:
  `StereoQueerEval_id | yt_title | yt_description | yt_comment | stereotype | hate_speech | target`
  with `hate_speech='yes_implicit'`, unquoted, tab-sanitized, deterministic ids `synth_{source_id}_v{n}`.

**IMPORTANT:** always pass `--resume`. A run *without* `--resume` completely replaces the registry
(`load_existing` is short-circuited); this happened once and wiped 113 earlier items (cheap to regenerate).

## Model availability probes (live, 2026-09-28)

| Model | Status |
|---|---|
| `gemini-2.5-flash` | 404 — no longer available to this account |
| `gemini-3.5-flash`, `3.7-flash`, `3.8-flash` | 503 high demand (at probe time) |
| `gemini-3.6-flash` | OK (best when probed) |
| `gemini-3.5-flash-lite` | OK (3/3) — **current Gemini default** |
| `gemini-flash-lite-latest` | OK |
| Groq `llama-3.3-70b-versatile` | 404 model_not_found (catalog changed) |
| Groq `openai/gpt-oss-120b` | OK — **current Groq default** |
| Groq `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` | listed, untested |

## Command log (chronological)

### 1. Gemini single-row era (pre-cooldown)
```powershell
# First smoke test (NL): 3/3 OK, 9 variants
python gen/llm_implicit_augment.py --api gemini --lang NL --limit 3 --n-variants 3

# NL, gemini-3.6-flash, no cooldown: 503 storms → mostly gave_up
# Result: ok=11 / gave_up=89 (42 synth rows)
python gen/llm_implicit_augment.py --api gemini --lang NL --limit 100 --n-variants 3 --resume
```

### 2. Gemini with cooldown (`--delay`, added by user) → clean run
```powershell
# gemini-3.5-flash-lite + 4.3s/request cooldown (~14 RPM): 100/100 OK, 342 synth rows
python -u gen/llm_implicit_augment.py --api gemini --lang NL --limit 100 --n-variants 3 --resume --delay 4.3
```

### 3. Groq switch
```powershell
# Install SDK
python -m pip install openai

# 404 probe (stale default) then working model probe:
python gen/llm_implicit_augment.py --api groq --lang NL --limit 1 --n-variants 3 --max-retries 2
python gen/llm_implicit_augment.py --api groq --model openai/gpt-oss-120b --lang NL --limit 1 --n-variants 3 --max-retries 2

# WARNING: the first of these ran WITHOUT --resume → registry truncated to 1 item.
# (113 Gemini items lost; regenerated in later runs.)

# Full single-row NL on Groq (aborted by user at ~165 requests; ~141 items saved)
python -u gen/llm_implicit_augment.py --api groq --lang NL --n-variants 3 --resume --delay 2.0
```

### 4. Batch prompting rewrite + timeout fix
Batch mode bundles `--batch-size` explicit comments into one API call → `{"results":[{"id":...,"variants":[...]}]}`.

Model defaults re-applied after rewrite: gemini→`gemini-3.5-flash-lite`, groq→`openai/gpt-oss-120b`, `--max-retries` 10.

```powershell
# Batch runs initially STALLED with zero saved rows: the OpenAI call had no request
# timeout, so a slow/queued server response hung forever (no exception ⇒ no retry).
# Fixed: timeout=180.0 on chat.completions.create + per-batch progress lines.

# Verification (1 batch of 5): 5/5 OK
python -u gen/llm_implicit_augment.py --api groq --lang NL --limit 5 --batch-size 5 --n-variants 3 --max-retries 5 --max-concurrency 1 --delay 0 --resume
# → "Total Source Comments Processed: 147" | "Total Synthetic Rows: 410" (NL only)
```

## Current corpus state (complete, 2026-09-28)

| Language | Explicit pool | Synth items | Synth TSV rows | Validation |
|---|---|---|---|---|
| EN | 810 | 810 | 2430 | 100% accepted |
| IT | 659 | 659 | 1977 | 100% accepted |
| NL | 624 | 624 | 1840 | 100% accepted |
| **Total** | **2093** | **2093** | **6247** | **100%** |

EN was completed in a second pass (60 rows that had `gave_up` on the first attempt were picked up by `--resume`).

### Final working recipe (Gemini batch mode — successful run)
Groq `gpt-oss-120b` became unusable for batch requests (server-side queuing → 180s timeouts,
~2 requests per 40 min). Gemini `gemini-3.5-flash-lite` is the reliable pipe:
single batch request ≈ 5 s, sustained ~1.2 comments/s with 4 workers.

```powershell
# NL completion (472 rows / 95 requests / ~7 min): 472/472 OK, 0 errors
python -u gen/llm_implicit_augment.py --api gemini --lang NL --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 2.0

# IT (659 rows / 132 requests): 659/659 OK
python -u gen/llm_implicit_augment.py --api gemini --lang IT --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 2.0

# EN first pass: 750/810 OK, 60 gave_up (provider quota tail)
python -u gen/llm_implicit_augment.py --api gemini --lang EN --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 2.0

# EN second pass (completes the 60): 60/60 OK
python -u gen/llm_implicit_augment.py --api gemini --lang EN --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 2.0
```

Script change in this step: `persist_snapshot()` now runs after EVERY completed batch (not only
every 10th), so a Ctrl+C/timeout kill can lose at most the in-flight batch.

## Validation (`gen/validate_synth_data.py`)

Rule-based 5-stage audit (schema, refusals, overt slurs, dupes, language markers), optional
LLM-as-a-Judge stage. Ran after completion — 100% clean on all languages after three fixes:

1. **Quote-leading fields break TSV parsing.** Unquoted TSV fields starting with `"`/`'`
   (incl. source video titles like `"Trans non per…"`) are misread by csv/pandas readers as
   opening quotes → column shift → `target=None`. Fixed in the writer
   (`gen/llm_implicit_augment.py` `write_canonical_tsv`): strip leading quote chars from
   comment/title/description. Regenerated all TSVs from `outputs.json` afterwards.
2. **Slur-list false positives.** `homo` (neutral colloquial in NL/IT), and `pedophile`/
   `groomer`/`abomination` (used AS dog-whistles, i.e. implicit) were rejecting valid samples.
   Removed from the overt-slur list.
3. **Stale LLM-judge defaults**: `gemini-2.5-flash` (404) and `llama-3.3-70b-versatile` (404)
   → replaced with `gemini-3.5-flash-lite` and `openai/gpt-oss-120b`.

```powershell
python -u gen/validate_synth_data.py --data-dir LGBT --report-file LGBT/synth_validation_report.json
# → EN 2430/2430, IT 1977/1977, NL 1840/1840 (exact-dup NL row removed from registry first)
```

### LLM-as-a-Judge stage (batched, Gemini gemini-3.5-flash-lite)
Batched judge evaluates 20 rows/call (313 calls total for the corpus). It ACCEPTs rows
verbatim or REJECTs them; rejected rows are recorded (reason + detected_class) and dropped
from `*_clean.tsv`. Judge feedback is not written into the TSVs themselves.

```powershell
python -u gen/validate_synth_data.py --data-dir LGBT --use-llm-judge --api gemini --judge-batch-size 20 --judge-rpm 0
```

| Language | Input | Deterministic | Judge accepted | Final `_clean.tsv` |
|---|---|---|---|---|
| EN | 2430 | 2430 | 2427 (3 target-fidelity rejects) | 2427 |
| IT | 1977 | 1977 | 1977 | 1977 |
| NL | 1840 | 1840 | 1834 (6 `homo` false positives) | 1840 |

Note: the validator rewrite re-introduced standalone `homo` (plus `pedophile`/`groomer`/
`abomination`) into the EN overt-slur list — dog-whistle/neutral colloquial words that cause
false rejects in NL/IT. Re-removed; NL re-verified 1840/1840.

- All `target`/`stereotype`/titles are inherited verbatim from source rows; id scheme
  `synth_{source_id}_v{n}`.

## Reproduce the full pipeline

```powershell
# Finish NL remainder (~477 rows → ~96 batch requests, Groq serial-to-2, 1s cooldown)
python -u gen/llm_implicit_augment.py --api groq --lang NL --batch-size 5 --n-variants 3 --resume --max-concurrency 2 --delay 1.0

# IT (659 explicit) on Gemini flash-lite w/ ~14 RPM cooldown
python -u gen/llm_implicit_augment.py --api gemini --lang IT --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 4.3

# EN (810 explicit) on Gemini flash-lite w/ ~14 RPM cooldown
python -u gen/llm_implicit_augment.py --api gemini --lang EN --batch-size 5 --n-variants 3 --resume --max-concurrency 4 --delay 4.3
```

### Operational notes
- Use `python -u` when piping: outputs are buffered otherwise and vanish on Ctrl+C.
- Groq free tier: keep `--max-concurrency` low (1-2); concurrent burst requests trigger 429 storms.
- 429/503/500 are retried with exponential backoff honoring `Retry-After` (`--max-retries`, default 10).
- `--rpm N` derives the cooldown as `max(--delay, 60/N)` seconds between requests.
- Resume is idempotent: completed source ids are skipped; empty/failed rows are re-attempted.