# DeepAgents BRD Generation

Async multi-agent pipeline for generating Business Requirement Documents using the [deepagents](https://docs.langchain.com/oss/python/deepagents/overview) framework.

## Architecture

6 flat manager agents (no sub-agents), orchestrated asynchronously:

```
Phase 0:              Drool File Filter (LLM-based, file-by-file relevance check)
Phase 1 (parallel):   Drool Agent  +  Model Agent
Phase 2 (sequential): Outbound Agent
                       Transformation Agent (gets drool + model + outbound outputs)
                       Inbound Agent (gets all prior outputs)
Phase 3 (validation): Reviewer Agent -> validates -> generates .docx BRD
```

Each sequential step receives ALL prior agent outputs as context. The Reviewer can request managers to reprocess if gaps are detected (max 2 retries).

## Quick Start

```bash
cp .env.example .env
# Set OPENAI_API_KEY and LLM_MODEL in .env (or .env.local for local overrides)

pip install -e ".[dev]"
python -m src.main --query "Create BRD for LC0070 payment authorization"
```

## Configuration

Set `LLM_MODEL` using the `provider:model` format:

```bash
# OpenAI
LLM_MODEL=openai:gpt-4

# AWS Bedrock
LLM_MODEL=anthropic.claude-3-5-sonnet-20240620-v1:0
LLM_MODEL_PROVIDER=bedrock_converse

# Ollama (local)
LLM_MODEL=ollama:neural-chat
```

## Project Structure

```
src/
  main.py                 CLI entry point
  config.py               Configuration (env-based)
  models.py               Data models
  orchestrator.py          Async pipeline orchestrator
  llm.py                  Generic LLM factory (init_chat_model)
  guardrails.py            Input validation
  logger.py                Structured logging (structlog)
  execution_logging.py     LLM/tool call callback logger
  agents/
    agent_definitions.py   Flat agent factories (no sub-agents)
  tools/
    corpus_reader.py       Format-aware file reader (JSONL/CSV/Excel/PDF/Word/.drl)
    drool_filter.py        LLM-based file relevance filter (Pydantic structured output)
    token_estimator.py     Token counting + cost estimation
    code_executor.py       Python code execution (for .docx generation)
  prompts/
    prompt_library.py      All agent prompts
```

## How It Works

1. **Drool File Filter** classifies corpus files by relevance via LLM calls (file-by-file, Pydantic structured output)
2. **Drool Agent** reads filtered files, extracts business rules and requirements
3. **Model Agent** (parallel with Drool) parses JSON/JSONL model specs for entities and relationships
4. **Outbound Agent** processes workbook JSONL sheets for outbound integration data
5. **Transformation Agent** documents transformation rules, mappings, and validation logic
6. **Inbound Agent** analyzes inbound data sources and ingestion requirements
7. **Reviewer Agent** synthesizes all outputs, validates completeness, generates `.docx` via code execution

File access is restricted: agents read corpus files ONLY through `read_corpus_file` (enforces `CORPUS_DIR`). No unrestricted filesystem access.

## Supported File Formats

JSONL, JSON, CSV, Excel (.xlsx), PDF, Word (.docx), Drools (.drl), Markdown, plain text.

## Testing

```bash
pytest tests/ -v
```

## License

MIT
