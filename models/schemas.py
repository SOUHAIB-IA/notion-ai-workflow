from typing import Literal
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


class Sprint(BaseModel):
    name: str
    goals: str
    start_date: str  # ISO format: "2026-03-12"
    end_date: str  # ISO format: "2026-03-26"
    task_titles: list[str]  # titles of tasks assigned to this sprint
    status: str = "Planning"


class SprintPlan(BaseModel):
    sprints: list[Sprint]


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
