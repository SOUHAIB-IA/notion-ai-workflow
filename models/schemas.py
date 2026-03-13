from typing import Literal, Optional
from pydantic import BaseModel


class Feature(BaseModel):
    name: str
    description: str
    priority: Literal["P0", "P1", "P2", "P3"]
    category: str  # e.g., "Backend", "Frontend", "Infrastructure"


class Task(BaseModel):
    title: str
    description: str
    feature: str  # links to parent feature name
    priority: Literal["P0", "P1", "P2", "P3"]
    effort: Literal["Small", "Medium", "Large"]
    status: str = "Not Started"


class Document(BaseModel):
    title: str
    doc_type: str  # "PRD", "Architecture", "Guide"
    content: str  # markdown
    feature: Optional[str] = None


class Sprint(BaseModel):
    name: str
    goals: str
    start_date: str  # ISO format: "2026-03-12"
    end_date: str  # ISO format: "2026-03-26"
    task_titles: list[str]  # titles of tasks assigned to this sprint
    status: str = "Planning"


class SprintPlan(BaseModel):
    sprints: list[Sprint]


class FeatureUpdate(BaseModel):
    """An update to an existing feature (change priority, description, etc.)."""
    name: str  # must match an existing feature name exactly
    description: Optional[str] = None
    priority: Optional[Literal["P0", "P1", "P2", "P3"]] = None
    category: Optional[str] = None


class UpdatePlan(BaseModel):
    """AI output for workspace updates — separates new features from updates."""
    new_features: list[Feature] = []
    updated_features: list[FeatureUpdate] = []
    summary: str  # what the AI decided to do


class Decision(BaseModel):
    """A decision extracted from meeting notes."""
    decision: str
    context: str
    status: Literal["Proposed", "Accepted", "Rejected"] = "Accepted"


class ActionItem(BaseModel):
    """An action item extracted from meeting notes."""
    title: str
    description: str
    feature: Optional[str] = None  # linked feature name, if relevant
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    effort: Literal["Small", "Medium", "Large"] = "Medium"


class Blocker(BaseModel):
    """A blocker that affects an existing task."""
    task_title: str  # must match an existing task title exactly
    reason: str


class MeetingExtract(BaseModel):
    """AI-extracted structured data from raw meeting notes."""
    summary: str
    decisions: list[Decision] = []
    action_items: list[ActionItem] = []
    blockers: list[Blocker] = []


class ProjectPlan(BaseModel):
    project_name: str
    description: str
    tech_stack: list[str]
    features: list[Feature]
    architecture_notes: str


class WorkspaceConfig(BaseModel):
    project_name: str
    root_page_id: str
    features_db_id: str
    tasks_db_id: str
    docs_db_id: str
    decisions_db_id: str
    dashboard_page_id: str
    sprints_db_id: str = ""
    # Maps feature name -> Notion page ID for relation linking
    feature_page_ids: dict[str, str] = {}
    # Maps task title -> Notion page ID for sprint linking
    task_page_ids: dict[str, str] = {}
    # Maps sprint name -> Notion page ID
    sprint_page_ids: dict[str, str] = {}
