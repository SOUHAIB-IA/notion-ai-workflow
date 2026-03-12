from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.orchestrator import orchestrator

app = FastAPI(
    title="FounderOS API",
    description="AI-powered startup operating system",
    version="1.0.0",
)


class CreateWorkspaceRequest(BaseModel):
    description: str


class UpdateWorkspaceRequest(BaseModel):
    update_description: str


class StatusResponse(BaseModel):
    project_name: str
    features_count: int
    feature_names: list[str]
    workspace_ids: dict[str, str]


class WorkspaceResponse(BaseModel):
    project_name: str
    root_page_id: str
    features_count: int
    message: str


@app.post("/workspace", response_model=WorkspaceResponse)
def create_workspace(req: CreateWorkspaceRequest):
    """Create a new project workspace from a startup description."""
    try:
        config = orchestrator.create_workspace(req.description)
        return WorkspaceResponse(
            project_name=config.project_name,
            root_page_id=config.root_page_id,
            features_count=len(config.feature_page_ids),
            message="Workspace created successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/workspace", response_model=WorkspaceResponse)
def update_workspace(req: UpdateWorkspaceRequest):
    """Update an existing workspace with new features."""
    try:
        config = orchestrator.update_workspace(req.update_description)
        if not config:
            raise HTTPException(
                status_code=404,
                detail="No existing workspace found. Create one first with POST /workspace.",
            )
        return WorkspaceResponse(
            project_name=config.project_name,
            root_page_id=config.root_page_id,
            features_count=len(config.feature_page_ids),
            message="Workspace updated successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/status", response_model=StatusResponse)
def workspace_status():
    """Get current workspace summary."""
    status = orchestrator.get_status()
    if not status:
        raise HTTPException(
            status_code=404,
            detail="No workspace found. Create one first with POST /workspace.",
        )
    return StatusResponse(**status)


@app.get("/health")
def health():
    return {"status": "ok"}
