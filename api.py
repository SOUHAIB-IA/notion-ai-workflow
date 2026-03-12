from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp_client.notion_mcp import notion_mcp
from agents.orchestrator import Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to Notion MCP on startup, disconnect on shutdown."""
    await notion_mcp.connect()
    app.state.orchestrator = Orchestrator(notion_mcp)
    yield
    await notion_mcp.disconnect()


app = FastAPI(
    title="FounderOS API",
    description="AI-powered startup operating system — Powered by Notion MCP",
    version="2.0.0",
    lifespan=lifespan,
)


class CreateWorkspaceRequest(BaseModel):
    description: str


class UpdateWorkspaceRequest(BaseModel):
    update_description: str


class SprintResponse(BaseModel):
    project_name: str
    sprints_count: int
    sprint_names: list[str]
    message: str


class StatusResponse(BaseModel):
    project_name: str
    features_count: int
    feature_names: list[str]
    sprints_count: int = 0
    sprint_names: list[str] = []
    workspace_ids: dict[str, str]


class WorkspaceResponse(BaseModel):
    project_name: str
    root_page_id: str
    features_count: int
    message: str


@app.post("/workspace", response_model=WorkspaceResponse)
async def create_workspace(req: CreateWorkspaceRequest):
    """Create a new project workspace from a startup description via MCP."""
    try:
        config = await app.state.orchestrator.create_workspace(req.description)
        return WorkspaceResponse(
            project_name=config.project_name,
            root_page_id=config.root_page_id,
            features_count=len(config.feature_page_ids),
            message="Workspace created successfully via Notion MCP",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/workspace", response_model=WorkspaceResponse)
async def update_workspace(req: UpdateWorkspaceRequest):
    """Update an existing workspace with new features via MCP."""
    try:
        config = await app.state.orchestrator.update_workspace(req.update_description)
        if not config:
            raise HTTPException(
                status_code=404,
                detail="No existing workspace found. Create one first with POST /workspace.",
            )
        return WorkspaceResponse(
            project_name=config.project_name,
            root_page_id=config.root_page_id,
            features_count=len(config.feature_page_ids),
            message="Workspace updated successfully via Notion MCP",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/status", response_model=StatusResponse)
async def workspace_status():
    """Get current workspace summary."""
    status = app.state.orchestrator.get_status()
    if not status:
        raise HTTPException(
            status_code=404,
            detail="No workspace found. Create one first with POST /workspace.",
        )
    return StatusResponse(**status)


@app.post("/workspace/sprints", response_model=SprintResponse)
async def plan_sprints():
    """Analyze tasks and create sprint plans in Notion via MCP."""
    try:
        config = await app.state.orchestrator.plan_sprints()
        if not config:
            raise HTTPException(
                status_code=404,
                detail="No workspace found. Create one first with POST /workspace.",
            )
        return SprintResponse(
            project_name=config.project_name,
            sprints_count=len(config.sprint_page_ids),
            sprint_names=list(config.sprint_page_ids.keys()),
            message="Sprints created successfully via Notion MCP",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mcp_connected": notion_mcp.session is not None,
        "mcp_tools_count": len(notion_mcp.available_tools),
    }
