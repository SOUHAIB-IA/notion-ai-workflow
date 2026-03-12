# FounderOS — AI Startup Operating System

AI-powered startup operating system that creates and manages complete project workspaces in Notion from natural language descriptions.

**Built with Notion MCP** — All Notion operations go through the Model Context Protocol, giving AI agents direct agency over your Notion workspace.

## How It Works

1. You describe your startup idea in plain English
2. AI agents (powered by Groq/Llama) plan features, design architecture, generate tasks, and write docs
3. The Notion MCP server (`@notionhq/notion-mcp-server`) creates everything in Notion automatically
4. Sprint planning AI organizes tasks into 2-week sprints

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the Notion MCP server via npx)

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

You need:
- **GROQ_API_KEY**: Get from [console.groq.com](https://console.groq.com)
- **NOTION_API_KEY**: Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
- **NOTION_ROOT_PAGE_ID**: The Notion page ID where workspaces will be created (share the page with your integration)

## Usage

### CLI
```bash
python main.py
```

Commands:
- `new` — Create a new project workspace from a startup idea
- `update` — Add features to an existing workspace
- `status` — Show workspace summary
- `sprint` — Plan 2-week sprints from tasks
- `plan` — Re-plan or adjust priorities
- `quit` — Exit

### API
```bash
uvicorn api:app --reload
```

Endpoints:
- `POST /workspace` — Create workspace `{"description": "your startup idea"}`
- `PUT /workspace` — Update workspace `{"update_description": "add payment system"}`
- `GET /workspace/status` — Get workspace summary
- `POST /workspace/sprints` — Generate sprint plans
- `GET /health` — Health check (includes MCP connection status)

## Architecture

```
User Input → Orchestrator → AI Agents (Groq/Llama) → Workspace Builder → Notion MCP Server → Notion
```

- **MCP Client** (`mcp_client/`): Connects to `@notionhq/notion-mcp-server` via stdio transport
- **AI Agents** (`agents/`): Planner, Architect, Task Generator, Doc Writer, Sprint Planner, Orchestrator
- **Services** (`services/`): Groq LLM client with retry, MCP-powered workspace builder
- **Models** (`models/`): Pydantic schemas for type-safe data flow
- **Prompts** (`prompts/`): Tunable text files for each agent's system prompt

## Notion MCP Integration

The project uses the Model Context Protocol to interact with Notion:
- The MCP server runs as a subprocess via `npx -y @notionhq/notion-mcp-server`
- Python connects to it using the `mcp` SDK's stdio transport
- Available MCP tools are discovered at startup and logged
- All database/page/block operations go through MCP tool calls
