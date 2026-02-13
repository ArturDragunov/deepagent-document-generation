# DeepAgents BRD Generation

Async multi-agent pipeline for generating Business Requirement Documents using the [deepagents](https://docs.langchain.com/oss/python/deepagents/overview) framework.

## Architecture

6 flat manager agents (no sub-agents), orchestrated asynchronously:

```
Phase 0:              Drool File Filter (LLM-based, file-by-file relevance check)
Phase 1 (parallel):   Drool Agent  +  Model Agent
Phase 2 (sequential): Outbound -> Transformation -> Inbound (each gets all prior outputs)
Phase 3 (validation): Reviewer Agent -> validates -> generates .docx BRD
```

- Each step receives **all prior agent outputs** (saved under `outputs/agent_outputs/`, read via tools). Reviewer can request reprocess if gaps are detected (max 2 retries).
- **File grouping:** Non-drool files are grouped by workbook (delimiter `FILE_GROUP_DELIMITER`); groups larger than `MAX_FILES_PER_GROUP` are split so each run has bounded context. After multiple batches, an optional **consolidation** step merges sections into one coherent doc using a golden BRD reference.

## Quick Start

```bash
cp .env.example .env
# Set OPENAI_API_KEY and LLM_MODEL in .env (or .env.local for local overrides)

pip install -e ".[dev]"
python -m src.main --query "Create BRD for LC0070 payment authorization"
```

**Outputs:** `outputs/agent_outputs/*.md` (per-agent markdown), `outputs/brd_report.json` (tokens, cost, files, warnings), and the final `.docx` when the Reviewer writes it (e.g. via `execute_python`).

## Configuration

**LLM** — use `provider:model` format:

```bash
LLM_MODEL=openai:gpt-4
# Bedrock: LLM_MODEL=anthropic.claude-3-5-sonnet-20240620-v1:0  LLM_MODEL_PROVIDER=bedrock_converse
# Ollama:  LLM_MODEL=ollama:neural-chat
```

**Paths:** `CORPUS_DIR` (default `example_data/corpus`), `OUTPUT_DIR` (default `outputs`), `GOLDEN_BRD_PATH` (default `example_data/golden_brd.md`) for consolidation reference.

**Scaling / consolidation:** `MAX_FILES_PER_GROUP` (default `8`), `FILE_GROUP_DELIMITER` (default `_sheet`), `CONSOLIDATE_SECTIONS` (default `true`). `REVIEWER_TIMEOUT_SEC` (default `600`), `AGENT_TIMEOUT_SEC` (default `300`).

**Cost:** Token usage is recorded and reported in `brd_report.json` and logs. Optional: `INPUT_COST_PER_1K`, `OUTPUT_COST_PER_1K`, `TRACK_TOKENS`.

## Project Structure

```
src/
  main.py                 CLI entry point
  config.py               Env-based configuration
  models.py               Data models
  orchestrator.py         Async pipeline (grouping, consolidation)
  llm.py                  LLM factory (init_chat_model)
  guardrails.py           Input validation
  logger.py               Structured logging
  execution_logging.py    LLM/tool callback logger
  agents/agent_definitions.py   Flat agent factories
  tools/
    corpus_reader.py      Format-aware reader (JSONL/CSV/Excel/PDF/Word/.drl)
    drool_filter.py       LLM file relevance filter
    agent_output.py       Save/read agent markdown (outputs/agent_outputs)
    token_estimator.py    Token count + cost
    code_executor.py      Python execution (for .docx)
  prompts/prompt_library.py   Agent prompts
```

## How It Works

1. **Drool File Filter** — LLM classifies each .drl file as include/exclude (Pydantic).
2. **Drool / Model** — Run in parallel; Model (and Phase 2 agents) process files in **groups** (workbook + cap), then optional **consolidation** with golden BRD.
3. **Outbound / Transformation / Inbound** — Sequential; each reads prior outputs via `read_agent_output`, processes its file groups, merges and optionally consolidates.
4. **Reviewer** — Reads all manager outputs, validates, generates `.docx` via `execute_python`.

File access: corpus only via `read_corpus_file` (CORPUS_DIR); outputs only in OUTPUT_DIR.

## Supported File Formats

JSONL, JSON, CSV, Excel (.xlsx), PDF, Word (.docx), Drools (.drl), Markdown, plain text.

## Testing

```bash
pytest tests/ -v
```

## License

MIT
