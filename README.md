# DeepAgents BRD Generation

Async multi-agent pipeline for generating Business Requirement Documents using the [deepagents](https://docs.langchain.com/oss/python/deepagents/overview) framework.

## Architecture

6 manager agents, each with specialized sub-agents (Analysis, Synthesis, Writer, Review):

```
Phase 1 (parallel):   Drool Agent (5 sub-agents)  +  Model Agent (4 sub-agents)
Phase 2 (sequential): Outbound -> Transformation -> Inbound (4 sub-agents each)
Phase 3 (validation): Reviewer Agent (Writer + Review) -> .docx output
```

The Reviewer can request managers to reprocess sections if gaps are detected (max 2 retries).

## Quick Start

```bash
cp .env.example .env
# Set your LLM_MODEL and API keys in .env

pip install -e ".[dev]"
python -m src.main --query "Create BRD for LC0070 payment authorization"
```

## Configuration

Set `LLM_MODEL` in `.env` using the `provider:model` format:

```bash
# OpenAI
LLM_MODEL=openai:gpt-4

# AWS Bedrock
LLM_MODEL=anthropic.claude-3-5-sonnet-20240620-v1:0
LLM_MODEL_PROVIDER=bedrock_converse

# Ollama (local)
LLM_MODEL=ollama:neural-chat
```

See `.env.example` for all options.

## Project Structure

```
src/
  main.py                 CLI entry point
  config.py               Configuration (env-based)
  models.py               Data models
  orchestrator.py          Async pipeline orchestrator
  guardrails.py            Input validation
  logger.py                Structured logging (structlog)
  agents/
    agent_definitions.py   Agent + sub-agent factories
  tools/
    corpus_reader.py       Format-aware file reader (JSONL/CSV/Excel/PDF/Word/.drl)
    keyword_extractor.py   Query keyword extraction
    token_estimator.py     Token counting + cost estimation
    code_executor.py       Python code execution (for .docx generation)
  prompts/
    prompt_library.py      All agent prompts
```

## How It Works

1. **Drool Agent** identifies relevant files via keyword/regex filtering, extracts business rules
2. **Model Agent** parses JSON/JSONL model specs for entities and relationships
3. **Outbound/Transformation/Inbound Agents** process workbook JSONL sheets sequentially
4. **Reviewer Agent** synthesizes all outputs, validates completeness, generates `.docx` via code execution

Custom tools supplement deepagents' built-in tools (`ls`, `glob`, `grep`, `read_file`, `write_file`, `write_todos`, `task`).

## Supported File Formats

JSONL, JSON, CSV, Excel (.xlsx), PDF, Word (.docx), Drools (.drl), Markdown, plain text.

## Testing

```bash
pytest tests/ -v
```

## License

MIT
