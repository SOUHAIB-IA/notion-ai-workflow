# FounderOS — AI Startup Operating System

AI-powered startup operating system that creates and manages complete project workspaces in Notion from natural language descriptions.

## Setup

1. Install dependencies:
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
- `GET /health` — Health check

## Architecture

- **Agents**: Planner, Architect, Task Generator, Doc Writer, Orchestrator
- **Services**: Groq LLM client, Notion CRUD service, Workspace builder
- **Models**: Pydantic schemas for type-safe data flow
- **Prompts**: Tunable text files for each agent's system prompt
