# DeepAgents BRD Generation System

Production-ready Business Requirement Document (BRD) generation system using **DeepAgents** and native subagent support. Generates comprehensive BRDs from source files using a 6-manager async pipeline.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your LLM credentials (OpenAI, Bedrock, Ollama, etc.)

python -m src.main --query "Create BRD for user authentication system"
```

## Features

- **6-Manager Pipeline**: Drool, Model, Outbound, Transformation, Inbound, Reviewer
- **Native DeepAgents Subagents**: Automatic orchestration (Analysis → Synthesis → Writer → Review)
- **Async Execution**: Phase 1 (Drool+Model parallel), Phase 2 (sequential cascade), Phase 3 (validation)
- **Multi-LLM Support**: OpenAI, AWS Bedrock, Ollama, or any LangChain provider
- **Multi-Format Files**: JSON, JSONL, CSV, Excel, PDF, Word, Markdown, .drl files
- **Token Tracking**: Cost estimation and usage accounting
- **Feedback Loop**: Reviewer validates; requests reruns if gaps detected (max 2 retries)

## Configuration

Set your LLM provider in `.env`:

```bash
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=sk-...

# AWS Bedrock
LLM_PROVIDER=bedrock
LLM_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1

# Ollama (local)
LLM_PROVIDER=ollama
LLM_MODEL=neural-chat
LLM_BASE_URL=http://localhost:11434
```

Other options in `.env.example`.

## Usage

```bash
# Basic
python -m src.main --query "Your BRD query"

# Custom corpus
python -m src.main --query "..." --corpus ./my_corpus

# Debug logging
python -m src.main --query "..." --log-level DEBUG

# Dry run (validation only)
python -m src.main --query "..." --dry-run
```

## Architecture

```
Phase 1 (Parallel):       Phase 2 (Sequential):     Phase 3 (Validation):
Drool Manager             Outbound Manager          Reviewer Supervisor
├─ File Filter            ├─ Analysis               ├─ Writer
├─ Analysis               ├─ Synthesis              └─ Review
├─ Synthesis              ├─ Writer
├─ Writer                 └─ Review
└─ Review                              & 2 more managers (Transformation, Inbound)
     ↓
Model Manager
├─ Analysis
├─ Synthesis
├─ Writer
└─ Review
```

All subagent orchestration handled by DeepAgents natively—no manual coordination needed.

## Project Structure

```
src/
├── main.py                    # CLI entry point
├── config.py                  # Configuration (generic LLM support)
├── models.py                  # Data models
├── orchestrator.py            # Async pipeline orchestrator
├── guardrails.py              # Input validation
├── agents/
│   └── agent_definitions.py   # Agent & subagent factories
├── tools/
│   ├── file_reader.py         # Multi-format file reading
│   ├── regex_tool.py          # Pattern matching
│   ├── token_estimator.py     # Token counting & cost
│   ├── llm_client.py          # Multi-provider LLM wrapper
│   └── docx_writer.py         # Word document generation
└── prompts/
    └── prompt_library.py      # All agent prompts

example_data/corpus/           # Sample corpus files
```

## Supported File Formats

- Data: JSON, JSONL, CSV, Excel (.xlsx)
- Documents: PDF, Word (.docx), Markdown (.md)
- Code: .drl (Drools), text files

## Multi-LLM Support

Works with any LangChain provider:
- OpenAI (GPT-4, GPT-3.5, etc.)
- AWS Bedrock (Claude, Llama, etc.)
- Ollama (local models)
- Custom endpoints via LangChain

Just configure `LLM_PROVIDER` and `LLM_MODEL` in `.env`.

## Testing

```bash
pytest tests/
pytest tests/ -v --cov=src
```

## Documentation

- **IMPLEMENTATION_SUMMARY.md** - Architecture & design
- **DEEPAGENTS_QUICK_REFERENCE.md** - How to use & customize subagents
- **REFACTORING_SUMMARY.md** - DeepAgents native subagent details

## Extending

### Add a Tool
```python
# In src/tools/my_tool.py
async def my_tool(param: str) -> str:
    """Description shown to agent."""
    return result

# In src/agents/agent_definitions.py
tools=[my_tool, ...]
```

### Customize Prompts
```python
# In src/prompts/prompt_library.py
def get_subagent_prompt(domain, sub_type):
    return "Your custom prompt..."
```

### Change LLM Provider
Edit `.env`:
```bash
LLM_PROVIDER=bedrock
LLM_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
```

That's it—no code changes needed!

## Performance

- **Execution**: 2-5 minutes (depending on corpus size)
- **Token usage**: ~50,000-150,000 tokens per BRD
- **Cost**: $0.10 - $0.50 per BRD (varies by model & provider)

## License

MIT
