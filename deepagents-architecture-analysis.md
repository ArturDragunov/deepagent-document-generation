# Deep Agents Architecture Analysis

> Comprehensive analysis of all 5 official examples from `langchain-ai/deepagents` plus the official documentation.

---

## Table of Contents

1. [Framework Overview (from docs)](#1-framework-overview)
2. [Example 1: content-builder-agent](#2-content-builder-agent)
3. [Example 2: deep_research](#3-deep-research)
4. [Example 3: downloading_agents](#4-downloading-agents)
5. [Example 4: ralph_mode](#5-ralph-mode)
6. [Example 5: text-to-sql-agent](#6-text-to-sql-agent)
7. [Cross-Cutting Patterns & Best Practices](#7-cross-cutting-patterns--best-practices)
8. [Tool Definition Patterns](#8-tool-definition-patterns)
9. [Built-in vs Custom Tools](#9-built-in-vs-custom-tools)
10. [Middleware Architecture](#10-middleware-architecture)
11. [Async Patterns](#11-async-patterns)

---

## 1. Framework Overview

**Source:** https://docs.langchain.com/oss/python/deepagents/overview

### What is `deepagents`?

`deepagents` is a standalone library built on top of LangChain's core building blocks. It uses the LangGraph runtime for durable execution, streaming, human-in-the-loop, and other features. It is described as an **"agent harness"** — the same core tool-calling loop as other agent frameworks, but with **built-in tools and capabilities** automatically attached via middleware.

### Core Entry Point: `create_deep_agent()`

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
```

### Automatic Middleware

When you call `create_deep_agent`, three middleware layers are automatically attached:

| Middleware | What it does |
|---|---|
| **TodoListMiddleware** | Provides `write_todos` tool for planning/task decomposition |
| **FilesystemMiddleware** | Provides `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` tools; auto-evicts large tool results to filesystem |
| **SubAgentMiddleware** | Provides `task` tool for spawning ephemeral subagents with isolated context |

### Built-in Tools (Always Available)

| Tool | Description |
|---|---|
| `write_todos` | Break down tasks, track progress with statuses (pending/in_progress/completed) |
| `ls` | List files in a directory with metadata |
| `read_file` | Read file contents with line numbers, offset/limit support |
| `write_file` | Create new files |
| `edit_file` | Exact string replacements in files |
| `glob` | Find files matching patterns |
| `grep` | Search file contents |
| `task` | Spawn a subagent with isolated context |
| `execute` | Run shell commands (sandbox backends only) |

### Key Concepts

- **Memory** (`AGENTS.md`): Persistent context always loaded into system prompt at startup
- **Skills** (`skills/*/SKILL.md`): On-demand capabilities loaded via progressive disclosure — agent reads only the YAML frontmatter, then loads the full skill only when relevant
- **Subagents**: Ephemeral agent instances with isolated context for delegated tasks
- **Backends**: Pluggable storage (StateBackend, FilesystemBackend, StoreBackend, CompositeBackend, Sandbox backends)

### Additional Harness Features

- **Large tool result eviction**: Auto-writes oversized tool results (>20k tokens) to filesystem, replaces with truncated preview + file reference
- **Conversation history summarization**: At 85% of model's max_input_tokens, old messages are summarized
- **Dangling tool call repair**: Fixes message history when tool calls are interrupted
- **Prompt caching (Anthropic)**: Caches repeated system prompt portions across turns
- **Streaming**: Built-in streaming from both main agent and subagents

---

## 2. Content Builder Agent

**Source:** https://github.com/langchain-ai/deepagents/tree/main/examples/content-builder-agent

### File Structure

```
content-builder-agent/
├── AGENTS.md                    # Brand voice & style guide (memory — always loaded)
├── subagents.yaml               # Subagent definitions (custom loader)
├── content_writer.py            # Main agent script + tool definitions
├── pyproject.toml               # Dependencies (deepagents>=0.3.5)
├── uv.lock
├── .gitignore
└── skills/
    ├── blog-post/
    │   └── SKILL.md             # Blog writing workflow (on-demand)
    └── social-media/
        └── SKILL.md             # Social media workflow (on-demand)
```

### How the Agent is Created

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

def create_content_writer():
    return create_deep_agent(
        memory=["./AGENTS.md"],                           # MemoryMiddleware
        skills=["./skills/"],                             # SkillsMiddleware
        tools=[generate_cover, generate_social_image],    # Custom tools
        subagents=load_subagents(EXAMPLE_DIR / "subagents.yaml"),  # Custom helper
        backend=FilesystemBackend(root_dir=EXAMPLE_DIR),  # Real filesystem
    )
```

**Key parameters used:**
- `memory` — list of paths to `AGENTS.md` files (always injected into system prompt)
- `skills` — list of paths to skill directories (progressive disclosure)
- `tools` — list of custom tool functions
- `subagents` — list of subagent dicts (normally defined inline, externalized to YAML here)
- `backend` — `FilesystemBackend` for real disk access

### How Tools are Defined

Tools use the **`@tool` decorator from `langchain_core.tools`**. They are **synchronous** plain functions:

```python
from langchain_core.tools import tool

@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "general",
) -> dict:
    """Search the web for current information.

    Args:
        query: The search query (be specific and detailed)
        max_results: Number of results to return (default: 5)
        topic: "general" for most queries, "news" for current events

    Returns:
        Search results with titles, URLs, and content excerpts.
    """
    # ... implementation using TavilyClient
```

```python
@tool
def generate_cover(prompt: str, slug: str) -> str:
    """Generate a cover image for a blog post.

    Args:
        prompt: Detailed description of the image to generate.
        slug: Blog post slug. Image saves to blogs/<slug>/hero.png
    """
    # ... implementation using google.genai
```

**Pattern notes:**
- All tools are **synchronous** (not async)
- Use **type hints** for all parameters
- Use **Google-style docstrings** with Args/Returns sections — these become the tool descriptions the LLM sees
- Use `Literal` types for constrained string parameters
- Return types are `dict` or `str`

### How Subagents are Defined

Subagents are defined in `subagents.yaml` and loaded with a custom `load_subagents()` helper:

```yaml
# subagents.yaml
researcher:
  description: >
    ALWAYS use this first to research any topic before writing content.
    Searches the web for current information, statistics, and sources.
  model: anthropic:claude-haiku-4-5-20251001
  system_prompt: |
    You are a research assistant. You have access to web_search and write_file tools.
    ## Your Process
    1. Use web_search to find information on the topic
    2. Make 2-3 targeted searches with specific queries
    3. Gather key statistics, quotes, and examples
    4. Save findings to the file path specified in your task
  tools:
    - web_search
```

**Important:** The README explicitly notes that `memory` and `skills` are handled natively by deepagents middleware, but **subagents must be defined in code** as list of dicts. The YAML approach is a custom convenience. Inline definition looks like:

```python
subagents=[
    {
        "name": "researcher",
        "description": "Research topics before writing...",
        "model": "anthropic:claude-haiku-4-5-20251001",
        "system_prompt": "You are a research assistant...",
        "tools": [web_search],
    }
]
```

### Subagent dict structure:
- `name` (str): Identifier
- `description` (str): What the LLM sees to decide when to use this subagent
- `system_prompt` (str): Instructions for the subagent
- `model` (str, optional): Model override (e.g., cheaper model for research)
- `tools` (list, optional): Tools available to the subagent

### How Orchestration Works

1. Agent receives a task (e.g., "Write a blog post about AI agents")
2. Agent reads the relevant **skill** (blog-post or social-media) via progressive disclosure
3. Agent delegates research to the `researcher` **subagent** using the `task` tool
4. Researcher subagent uses `web_search` and `write_file` (built-in) to save findings
5. Main agent reads research findings, writes content using `write_file`
6. Agent generates cover images with `generate_cover` / `generate_social_image`

### AGENTS.md (Memory)

Contains brand voice, writing standards, content pillars, formatting guidelines, and research requirements. Always loaded into system prompt. Instructs the agent to always research first using the `researcher` subagent.

### Skills (Progressive Disclosure)

Each skill has YAML frontmatter with `name` and `description`, followed by detailed workflow instructions. The agent only loads the full SKILL.md when it determines the skill is relevant.

**blog-post/SKILL.md** covers:
- When to use the skill
- Research-first requirement (delegating to researcher subagent)
- Output structure (`blogs/<slug>/post.md` + `blogs/<slug>/hero.png`)
- Blog post structure (hook → context → main content → practical application → CTA)
- Image prompt engineering guide with examples
- SEO considerations and quality checklist

### Async Handling

The main script uses **`asyncio.run(main())`** with **`agent.astream()`** for streaming:

```python
async def main():
    agent = create_content_writer()
    async for chunk in agent.astream(
        {"messages": [("user", task)]},
        config={"configurable": {"thread_id": "content-writer-demo"}},
        stream_mode="values",
    ):
        if "messages" in chunk:
            # Process and display messages
```

- Agent creation itself is synchronous
- Streaming/invocation is async via `astream()`
- Uses `rich` library for terminal UI with spinners and panels
- `thread_id` in config for conversation threading

### Dependencies

```
deepagents>=0.3.5
google-genai>=1.0.0   # Image generation (Gemini)
pillow>=10.0.0
pyyaml>=6.0.0          # For subagents.yaml loading
rich>=13.0.0           # Terminal UI
tavily-python>=0.5.0   # Web search
```

---

## 3. Deep Research

**Source:** https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research

### File Structure

```
deep_research/
├── agent.py                     # Main agent creation (deployed to LangGraph)
├── utils.py                     # Display utilities for Jupyter
├── research_agent/              # Package with prompts and tools
│   ├── __init__.py
│   ├── prompts.py               # Three prompt templates
│   └── tools.py                 # tavily_search and think_tool
├── langgraph.json               # LangGraph deployment config
├── research_agent.ipynb         # Interactive Jupyter notebook
├── pyproject.toml
├── uv.lock
├── .env.example
└── README.md
```

### How the Agent is Created

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from research_agent.prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent.tools import tavily_search, think_tool

# Combine orchestrator instructions
INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS + "\n\n" + "=" * 80 + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=3,
        max_researcher_iterations=3,
    )
)

# Define research sub-agent
research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search, think_tool],
}

# Custom model
model = init_chat_model(model="anthropic:claude-sonnet-4-5-20250929", temperature=0.0)

# Create the agent
agent = create_deep_agent(
    model=model,
    tools=[tavily_search, think_tool],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
)
```

**Key differences from content-builder:**
- Uses `model` parameter with custom model initialization via `init_chat_model()` or `ChatGoogleGenerativeAI()`
- Uses `system_prompt` parameter (string) instead of `memory` (file paths)
- No `skills` or `memory` parameters — all instructions are in code as prompt strings
- No `backend` specified — uses default `StateBackend` (ephemeral in-memory)
- Designed for **LangGraph deployment** (`langgraph.json` config, `agent` variable at module level)

### How Tools are Defined

```python
from langchain_core.tools import InjectedToolArg, tool
from typing_extensions import Annotated, Literal

@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns
    full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """
```

**Advanced patterns used:**
- **`@tool(parse_docstring=True)`** — tells LangChain to parse the Google-style docstring for parameter descriptions
- **`InjectedToolArg`** — marks parameters that are injected at runtime (not exposed to the LLM). The LLM only sees `query`; `max_results` and `topic` are set by the runtime
- **`Annotated[type, InjectedToolArg]`** — standard typing pattern for injected args
- Tools are **synchronous**
- `tavily_search` does NOT just return Tavily summaries — it fetches full webpage content via `httpx` and converts HTML to markdown with `markdownify`. This preserves complete information for the agent.

```python
@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.
    ...
    """
    return f"Reflection recorded: {reflection}"
```

**`think_tool` pattern:** A tool that does nothing computationally — it just returns the input. The purpose is to force the LLM to pause and reason explicitly between search steps. This is a known pattern for improving agent reasoning quality.

### How Subagents/Tasks are Spawned

The orchestrator agent uses the built-in `task` tool to spawn research subagents:

- The orchestrator plans research using `write_todos`
- For each research topic, it calls `task` with the `research-agent` subagent
- Multiple `task` calls in a single response enable **parallel execution** (up to 3 concurrent)
- Each subagent runs independently with its own context window
- Subagents return findings as a single result to the orchestrator

### Prompt Architecture (Three-Layer)

| Prompt | Used By | Purpose |
|---|---|---|
| `RESEARCH_WORKFLOW_INSTRUCTIONS` | Orchestrator | 5-step workflow: save request → plan with TODOs → delegate → synthesize → write report |
| `SUBAGENT_DELEGATION_INSTRUCTIONS` | Orchestrator | Concrete delegation strategies with examples; limits (max 3 concurrent, max 3 rounds) |
| `RESEARCHER_INSTRUCTIONS` | Research subagent | Focused web searches with think_tool reflection; hard limits (2-3 searches simple, max 5 complex) |

### Orchestration Flow

1. Orchestrator receives research question
2. Saves request to `/research_request.md` using `write_file`
3. Creates a plan using `write_todos`
4. Delegates research to subagents via `task` tool (1-3 parallel)
5. Each subagent: searches → thinks → searches → thinks → returns findings with citations
6. Orchestrator synthesizes findings, consolidates citations
7. Writes final report to `/final_report.md`
8. Verifies report addresses all aspects of original request

### LangGraph Deployment

The `agent` variable is exposed at module level for LangGraph server deployment:

```json
// langgraph.json
{
    "agent": "agent:agent"
}
```

Run locally with:
```bash
langgraph dev
```

### Async Handling

- Agent is created synchronously
- Can be invoked with `agent.invoke()` (sync) or streamed with `agent.astream()` (async)
- The Jupyter notebook provides interactive usage
- LangGraph server handles async natively

### Dependencies

```
deepagents>=0.2.6
langchain-anthropic>=1.0.3
langchain-google-genai>=3.1.0
tavily-python>=0.5.0
httpx>=0.28.1          # For fetching full webpage content
markdownify>=1.2.0     # HTML to markdown conversion
rich>=14.0.0
langgraph-cli[inmem]>=0.1.55  # For local LangGraph server
```

---

## 4. Downloading Agents

**Source:** https://github.com/langchain-ai/deepagents/tree/main/examples/downloading_agents

### File Structure

```
downloading_agents/
├── README.md
└── content-writer.zip     # Packaged agent (AGENTS.md + skills/)
```

### Key Concept: Agents Are Just Folders

This example demonstrates that a deepagent is defined entirely by files on disk:

```
.deepagents/
├── AGENTS.md              # Agent memory & instructions
└── skills/
    ├── blog-post/SKILL.md
    └── social-media/SKILL.md
```

**No code required.** The `deepagents-cli` tool reads these files and creates the agent automatically.

### How It Works

```bash
# Install the CLI
uv tool install deepagents-cli==0.0.13

# Download and unzip the agent
curl -L https://...content-writer.zip -o agent.zip
unzip agent.zip -d .deepagents

# Run it
deepagents
```

### Architecture Pattern

- **Agents are portable artifacts** — zip a folder, share it, run it anywhere
- The CLI (`deepagents-cli`) handles all the `create_deep_agent()` wiring internally
- Memory comes from `AGENTS.md`, skills come from `skills/*/SKILL.md`
- No custom tools, no custom code needed for basic agents

### No Custom Agent Creation Code

This example has no `create_deep_agent()` call — the CLI does it automatically based on the folder structure.

---

## 5. Ralph Mode

**Source:** https://github.com/langchain-ai/deepagents/tree/main/examples/ralph_mode

### File Structure

```
ralph_mode/
├── ralph_mode.py           # Autonomous looping script
├── ralph_mode_diagram.png  # Architecture diagram
└── README.md
```

### How the Agent is Created

Uses `deepagents_cli` instead of `deepagents` directly:

```python
from deepagents_cli.agent import create_cli_agent
from deepagents_cli.config import COLORS, SessionState, console, create_model
from deepagents_cli.execution import execute_task
from deepagents_cli.ui import TokenTracker

async def ralph(task: str, max_iterations: int = 0, model_name: str = None):
    work_dir = tempfile.mkdtemp(prefix="ralph-")
    model = create_model(model_name)

    agent, backend = create_cli_agent(
        model=model,
        assistant_id="ralph",
        tools=[],
        auto_approve=True,
    )
```

**Key differences:**
- Uses `create_cli_agent()` from `deepagents_cli.agent` (not `create_deep_agent` from `deepagents`)
- Returns `(agent, backend)` tuple
- `auto_approve=True` — no human-in-the-loop interrupts
- `tools=[]` — no custom tools; relies entirely on built-in filesystem/planning tools
- Uses `execute_task()` helper for running tasks through the agent

### The Ralph Loop Pattern

```python
iteration = 1
while max_iterations == 0 or iteration <= max_iterations:
    prompt = f"""## Iteration {iter_display}

Your previous work is in the filesystem. Check what exists and keep building.

TASK:
{task}

Make progress. You'll be called again."""

    await execute_task(
        prompt,
        agent,
        "ralph",
        session_state,
        token_tracker,
        backend=backend,
    )
    iteration += 1
```

**Core idea:** Each iteration starts with fresh context. The filesystem and git serve as memory between iterations. This is the Python implementation of the viral one-liner:

```bash
while :; do cat PROMPT.md | agent ; done
```

### Architecture Pattern

- **No subagents** — single agent looping
- **No skills or memory files** — prompt is the only instruction
- **Filesystem as memory** — agent reads/writes files to track progress
- **Git as memory** — agent can use git to track changes over time
- **Fresh context each loop** — no conversation history management needed
- **Infinite loop with Ctrl+C** — runs until user stops it
- **Temporary working directory** — `tempfile.mkdtemp()`

### Async Handling

Fully async:

```python
async def ralph(task, max_iterations, model_name):
    # ...
    await execute_task(prompt, agent, ...)

def main():
    asyncio.run(ralph(args.task, args.iterations, args.model))
```

### No Custom Tools

Ralph Mode relies entirely on built-in deepagent tools (filesystem, planning, etc.) and whatever the CLI agent provides by default.

---

## 6. Text-to-SQL Agent

**Source:** https://github.com/langchain-ai/deepagents/tree/main/examples/text-to-sql-agent

### File Structure

```
text-to-sql-agent/
├── agent.py                       # Core agent + CLI
├── AGENTS.md                      # Agent identity & instructions (memory)
├── skills/
│   ├── query-writing/
│   │   └── SKILL.md               # SQL query writing workflow
│   └── schema-exploration/
│       └── SKILL.md               # Database structure discovery
├── chinook.db                     # SQLite sample database (gitignored)
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
└── text-to-sql-langsmith-trace.png
```

### How the Agent is Created

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_anthropic import ChatAnthropic
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase

def create_sql_deep_agent():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Connect to database
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}", sample_rows_in_table_info=3)

    # Initialize model
    model = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)

    # Create SQL toolkit and get tools
    toolkit = SQLDatabaseToolkit(db=db, llm=model)
    sql_tools = toolkit.get_tools()

    agent = create_deep_agent(
        model=model,
        memory=["./AGENTS.md"],
        skills=["./skills/"],
        tools=sql_tools,           # LangChain community SQL tools
        subagents=[],              # Explicitly empty
        backend=FilesystemBackend(root_dir=base_dir),
    )
    return agent
```

**Key differences:**
- Uses **LangChain community tools** (`SQLDatabaseToolkit`) instead of custom `@tool` functions
- **No custom tool definitions** — all tools come from the toolkit
- `subagents=[]` explicitly — no delegation, single agent handles everything
- Uses both `memory` AND `skills` AND `tools` together

### Tools (from SQLDatabaseToolkit)

The SQL toolkit provides these tools automatically:

| Tool | Description |
|---|---|
| `sql_db_list_tables` | List all tables in the database |
| `sql_db_schema` | Get schema (columns, types, sample rows) for specific tables |
| `sql_db_query_checker` | Validate SQL syntax before execution |
| `sql_db_query` | Execute a SQL query and return results |

These are LangChain community tools, not custom `@tool` decorated functions.

### Skills (Progressive Disclosure)

**query-writing/SKILL.md:**
- Workflow for simple queries (single table) vs complex queries (multi-table JOINs)
- Uses `write_todos` for complex query planning
- SQL best practices (LIMIT, aliases, no SELECT *)

**schema-exploration/SKILL.md:**
- Workflow for discovering database structure
- Three patterns: find a table, understand structure, map relationships
- Example explorations with the Chinook database

### AGENTS.md (Memory)

- Agent identity and role
- Step-by-step process (explore → examine → generate → execute → format)
- Query guidelines (LIMIT 5, ORDER BY, no SELECT *)
- Safety rules (READ-ONLY, no INSERT/UPDATE/DELETE/DROP)
- Planning guidance for complex questions using `write_todos`

### Orchestration Flow

1. User asks a natural language question
2. Agent checks skills — loads `query-writing` or `schema-exploration` as relevant
3. For complex queries: uses `write_todos` to plan approach
4. Uses SQL tools to explore schema, write query, validate, execute
5. Uses filesystem tools to save intermediate results if needed
6. Formats and returns answer

### Async Handling

This example is **synchronous** — uses `agent.invoke()` directly:

```python
result = agent.invoke(
    {"messages": [{"role": "user", "content": args.question}]}
)
final_message = result["messages"][-1]
```

No async/streaming — simplest invocation pattern.

### Dependencies

```
deepagents>=0.3.5
langchain>=1.2.3
langchain-anthropic>=1.3.1
langchain-community>=0.3.0   # For SQLDatabaseToolkit
langgraph>=1.0.6
sqlalchemy>=2.0.0             # For SQLDatabase
python-dotenv>=1.0.0
rich>=13.0.0
```

---

## 7. Cross-Cutting Patterns & Best Practices

### Pattern 1: `create_deep_agent()` Parameter Combinations

| Example | model | system_prompt | memory | skills | tools | subagents | backend |
|---|---|---|---|---|---|---|---|
| **content-builder** | default | - | `["./AGENTS.md"]` | `["./skills/"]` | custom @tool | YAML-loaded dicts | FilesystemBackend |
| **deep_research** | `init_chat_model()` | string | - | - | custom @tool | inline dict | default (State) |
| **downloading_agents** | CLI default | - | CLI auto-loads | CLI auto-loads | - | - | CLI default |
| **ralph_mode** | `create_model()` | - | - | - | `[]` | - | CLI default |
| **text-to-sql** | `ChatAnthropic()` | - | `["./AGENTS.md"]` | `["./skills/"]` | toolkit tools | `[]` | FilesystemBackend |

### Pattern 2: Three Ways to Provide Instructions

1. **`system_prompt` parameter** (string) — used by deep_research. Direct, good for programmatic prompt composition.
2. **`memory` parameter** (file paths) — used by content-builder and text-to-sql. References `AGENTS.md` files loaded by MemoryMiddleware. Good for separating instructions from code.
3. **CLI auto-loading** — used by downloading_agents and ralph_mode. The CLI reads `.deepagents/AGENTS.md` automatically.

### Pattern 3: Three Ways to Provide Tools

1. **Custom `@tool` decorated functions** — content-builder, deep_research
2. **LangChain community toolkits** — text-to-sql (`SQLDatabaseToolkit.get_tools()`)
3. **No custom tools** — ralph_mode, downloading_agents (rely on built-in filesystem/planning tools only)

### Pattern 4: Subagent Strategies

1. **Single specialized subagent** — content-builder (researcher only)
2. **Research subagent with parallel execution** — deep_research (1-3 parallel research agents)
3. **No subagents** — text-to-sql, ralph_mode (single agent handles everything)
4. **Default general-purpose subagent** — always available even if not explicitly configured

### Pattern 5: Backend Selection

- **`FilesystemBackend(root_dir=...)`** — when agent needs real disk access (content-builder, text-to-sql)
- **Default `StateBackend`** — ephemeral in-memory, when output is just messages (deep_research)
- **CLI default** — ralph_mode uses the CLI's built-in backend selection

### Pattern 6: Model Configuration

```python
# Option 1: Default (Claude Sonnet 4.5)
agent = create_deep_agent(tools=[...])

# Option 2: init_chat_model with provider prefix
from langchain.chat_models import init_chat_model
model = init_chat_model(model="anthropic:claude-sonnet-4-5-20250929", temperature=0.0)

# Option 3: Direct model class
from langchain_anthropic import ChatAnthropic
model = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)

# Option 4: Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview")

# Option 5: Cheaper model for subagents
subagent = {"model": "anthropic:claude-haiku-4-5-20251001", ...}
```

---

## 8. Tool Definition Patterns

### Pattern A: Basic `@tool` Decorator (Content Builder)

```python
from langchain_core.tools import tool

@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "general",
) -> dict:
    """Search the web for current information.

    Args:
        query: The search query
        max_results: Number of results to return (default: 5)
        topic: "general" or "news"

    Returns:
        Search results with titles, URLs, and content excerpts.
    """
```

- Synchronous function
- All params visible to LLM
- Type hints + docstring for schema generation

### Pattern B: `@tool(parse_docstring=True)` with `InjectedToolArg` (Deep Research)

```python
from langchain_core.tools import InjectedToolArg, tool
from typing_extensions import Annotated

@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Search the web for information on a given query.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return
        topic: Topic filter
    """
```

- `parse_docstring=True` extracts param descriptions from docstring
- `InjectedToolArg` hides params from LLM (set at runtime)
- More control over what the LLM sees vs what's configurable

### Pattern C: "Thinking" Tool (Deep Research)

```python
@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress."""
    return f"Reflection recorded: {reflection}"
```

- Does nothing computationally — forces explicit reasoning
- Improves agent quality by creating deliberate pauses

### Pattern D: LangChain Community Toolkit Tools (Text-to-SQL)

```python
from langchain_community.agent_toolkits import SQLDatabaseToolkit

toolkit = SQLDatabaseToolkit(db=db, llm=model)
sql_tools = toolkit.get_tools()
# Returns: [sql_db_list_tables, sql_db_schema, sql_db_query_checker, sql_db_query]
```

- No custom `@tool` definitions needed
- Tools come pre-built from LangChain's ecosystem
- Pass directly to `create_deep_agent(tools=sql_tools)`

### Pattern E: Plain Functions (Quickstart Docs)

```python
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_deep_agent(tools=[get_weather], ...)
```

- No `@tool` decorator needed for simple cases
- deepagents wraps plain functions automatically
- Docstring still serves as tool description

---

## 9. Built-in vs Custom Tools

### Built-in Tools (from middleware, always available)

| Tool | Middleware | Purpose |
|---|---|---|
| `write_todos` | TodoListMiddleware | Task planning and tracking |
| `ls` | FilesystemMiddleware | List directory contents |
| `read_file` | FilesystemMiddleware | Read file contents |
| `write_file` | FilesystemMiddleware | Create/write files |
| `edit_file` | FilesystemMiddleware | Edit files with string replacement |
| `glob` | FilesystemMiddleware | Pattern-match file names |
| `grep` | FilesystemMiddleware | Search file contents |
| `task` | SubAgentMiddleware | Spawn subagent with isolated context |
| `execute` | Sandbox only | Run shell commands |

### Custom Tools by Example

| Example | Custom Tools | Source |
|---|---|---|
| **content-builder** | `web_search`, `generate_cover`, `generate_social_image` | `@tool` decorated functions |
| **deep_research** | `tavily_search`, `think_tool` | `@tool(parse_docstring=True)` |
| **downloading_agents** | None | CLI only |
| **ralph_mode** | None | Built-in only |
| **text-to-sql** | None custom, but uses `sql_db_*` from toolkit | `SQLDatabaseToolkit.get_tools()` |

### External Services Used

| Service | Used In | Purpose |
|---|---|---|
| **Tavily** | content-builder, deep_research, quickstart | Web search |
| **Google Gemini (genai)** | content-builder | Image generation |
| **Anthropic Claude** | All examples | Primary LLM |
| **SQLite/SQLAlchemy** | text-to-sql | Database access |
| **httpx + markdownify** | deep_research | Fetch and convert web pages |

---

## 10. Middleware Architecture

### How Middleware Works

Each feature is implemented as **separate middleware** attached automatically when you call `create_deep_agent()`:

1. **TodoListMiddleware** — injects `write_todos` tool, persists todo state
2. **FilesystemMiddleware** — injects all file tools, handles large result eviction
3. **SubAgentMiddleware** — injects `task` tool, manages subagent lifecycle
4. **MemoryMiddleware** — loads `AGENTS.md` files into system prompt (when `memory=` is set)
5. **SkillsMiddleware** — provides progressive disclosure of skills (when `skills=` is set)

### Memory Middleware vs Skills Middleware

| Aspect | Memory (`AGENTS.md`) | Skills (`SKILL.md`) |
|---|---|---|
| **Loading** | Always — injected into system prompt at startup | On-demand — only when agent determines relevance |
| **Size impact** | Always uses tokens | Minimal until loaded (only frontmatter description) |
| **Use for** | Always-relevant context (voice, rules, identity) | Task-specific workflows (potentially large) |
| **Layering** | User → project (combined) | User → project (last wins) |

### No Explicit Middleware Configuration

You never configure middleware directly. It's all handled through `create_deep_agent()` parameters:

```python
agent = create_deep_agent(
    memory=["./AGENTS.md"],    # → triggers MemoryMiddleware
    skills=["./skills/"],      # → triggers SkillsMiddleware
    tools=[...],               # → custom tools added alongside built-in tools
    subagents=[...],           # → configures SubAgentMiddleware
    backend=FilesystemBackend(), # → configures FilesystemMiddleware's storage
)
```

---

## 11. Async Patterns

### Three Invocation Patterns Seen

**1. Synchronous `invoke()` (text-to-sql)**
```python
result = agent.invoke(
    {"messages": [{"role": "user", "content": question}]}
)
answer = result["messages"][-1].content
```

**2. Async streaming `astream()` (content-builder)**
```python
async for chunk in agent.astream(
    {"messages": [("user", task)]},
    config={"configurable": {"thread_id": "demo"}},
    stream_mode="values",
):
    # Process streaming chunks
```

**3. Async via CLI helper `execute_task()` (ralph_mode)**
```python
await execute_task(prompt, agent, "ralph", session_state, token_tracker, backend=backend)
```

### Tool Functions Are Always Synchronous

Across all examples, **every custom tool is synchronous** (no `async def`). The framework handles async execution internally — tools are called synchronously within the async agent loop.

### Message Format

Two formats seen:
```python
# Dict format
{"messages": [{"role": "user", "content": "..."}]}

# Tuple format (shorthand)
{"messages": [("user", "...")]}
```

### Thread IDs

Used for conversation persistence:
```python
config={"configurable": {"thread_id": "content-writer-demo"}}
```

---

## Summary of Best Practices

1. **Use `AGENTS.md` for always-on context** (brand voice, safety rules, agent identity)
2. **Use `skills/` for task-specific workflows** to minimize token usage via progressive disclosure
3. **Define tools as synchronous `@tool` decorated functions** with type hints and Google-style docstrings
4. **Use `InjectedToolArg` to hide runtime-configurable params** from the LLM
5. **Use subagents for context isolation** — research tasks, specialized work
6. **Use cheaper models for subagents** (e.g., Haiku for research, Sonnet for orchestration)
7. **Use `FilesystemBackend` when agents need persistent file access**; default `StateBackend` for ephemeral
8. **Use `write_todos` for complex multi-step tasks** — all examples that involve planning use this
9. **Think tool pattern** — a no-op tool that forces deliberate reasoning between actions
10. **Externalize configuration** — prompts, skills, memory as files not code when possible
11. **Agents are portable** — an agent is just `AGENTS.md` + `skills/` directory
12. **LangGraph integration** — agents can be deployed to LangGraph server with `langgraph.json`
13. **Leverage LangChain community toolkits** instead of writing custom tools when available
14. **Stream for UX** — use `astream()` with `rich` for real-time progress display
