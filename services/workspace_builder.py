import json
import logging
from pathlib import Path

from config import settings
from models.schemas import Feature, Task, Sprint, SprintPlan, ProjectPlan, WorkspaceConfig
from services.notion_service import notion_service as notion

logger = logging.getLogger(__name__)


class WorkspaceBuilder:
    """Orchestrates the creation of a full Notion workspace from a ProjectPlan."""

    def __init__(self):
        self.notion = notion
        self.config_path = Path(settings.workspace_config_path)

    def save_config(self, config: WorkspaceConfig):
        """Persist workspace config to local JSON file."""
        self.config_path.write_text(config.model_dump_json(indent=2))
        logger.info(f"Workspace config saved to {self.config_path}")

    def load_config(self) -> WorkspaceConfig | None:
        """Load workspace config from local JSON file."""
        if not self.config_path.exists():
            return None
        data = json.loads(self.config_path.read_text())
        return WorkspaceConfig(**data)

    def build_workspace(
        self,
        plan: ProjectPlan,
        tasks: list[Task],
        architecture_doc: str,
        feature_docs: dict[str, str],
    ) -> WorkspaceConfig:
        """Create the full Notion workspace.

        Args:
            plan: The project plan with features.
            tasks: All generated tasks.
            architecture_doc: Markdown architecture document.
            feature_docs: Dict mapping feature name -> PRD markdown content.

        Returns:
            WorkspaceConfig with all created resource IDs.
        """
        root_page_id = settings.notion_root_page_id

        # Step 1: Create root project page
        logger.info("Creating root project page...")
        project_page_id = self.notion.create_page(
            parent_id=root_page_id,
            properties=self.notion.title_property(f"🚀 {plan.project_name} — FounderOS"),
            content_blocks=[
                self.notion.callout_block(plan.description, "🚀"),
                self.notion.divider_block(),
            ],
            parent_type="page_id",
        )

        # Step 2: Create databases
        logger.info("Creating Features database...")
        features_db_id = self._create_features_db(project_page_id)

        logger.info("Creating Tasks database...")
        tasks_db_id = self._create_tasks_db(project_page_id, features_db_id)

        logger.info("Creating Documents database...")
        docs_db_id = self._create_docs_db(project_page_id, features_db_id)

        logger.info("Creating Decisions database...")
        decisions_db_id = self._create_decisions_db(project_page_id)

        logger.info("Creating Sprints database...")
        sprints_db_id = self._create_sprints_db(project_page_id)

        # Step 3: Populate Features
        logger.info("Populating features...")
        feature_page_ids = {}
        for feature in plan.features:
            page_id = self._create_feature_page(features_db_id, feature)
            feature_page_ids[feature.name] = page_id

        # Step 4: Populate Tasks (track page IDs for sprint linking)
        logger.info("Populating tasks...")
        task_page_ids = {}
        for task in tasks:
            feature_pid = feature_page_ids.get(task.feature)
            task_pid = self._create_task_page(tasks_db_id, task, feature_pid)
            task_page_ids[task.title] = task_pid

        # Step 5: Create architecture doc
        logger.info("Creating architecture document...")
        self._create_doc_page(docs_db_id, "Technical Architecture", "Architecture", architecture_doc)

        # Step 6: Create feature PRD docs
        logger.info("Creating feature PRD documents...")
        for feature_name, doc_content in feature_docs.items():
            feature_pid = feature_page_ids.get(feature_name)
            self._create_doc_page(
                docs_db_id, f"PRD: {feature_name}", "PRD", doc_content, feature_pid
            )

        # Step 7: Create Dashboard page
        logger.info("Creating dashboard page...")
        dashboard_page_id = self._create_dashboard(
            project_page_id, plan, features_db_id, tasks_db_id, sprints_db_id
        )

        config = WorkspaceConfig(
            project_name=plan.project_name,
            root_page_id=project_page_id,
            features_db_id=features_db_id,
            tasks_db_id=tasks_db_id,
            docs_db_id=docs_db_id,
            decisions_db_id=decisions_db_id,
            sprints_db_id=sprints_db_id,
            dashboard_page_id=dashboard_page_id,
            feature_page_ids=feature_page_ids,
            task_page_ids=task_page_ids,
        )
        self.save_config(config)
        return config

    # ── Database Creation ──────────────────────────────────────────────

    def _create_features_db(self, parent_page_id: str) -> str:
        return self.notion.create_database(
            parent_page_id=parent_page_id,
            title="📋 Features",
            properties_schema={
                "Name": {"type": "title"},
                "Description": {"type": "rich_text"},
                "Priority": {"type": "select", "options": ["P0", "P1", "P2", "P3"]},
                "Category": {"type": "select", "options": [
                    "Backend", "Frontend", "Infrastructure", "Data", "DevOps", "Design", "Mobile"
                ]},
                "Status": {"type": "status", "options": [
                    "Not Started", "In Progress", "Done"
                ]},
            },
        )

    def _create_tasks_db(self, parent_page_id: str, features_db_id: str) -> str:
        return self.notion.create_database(
            parent_page_id=parent_page_id,
            title="✅ Tasks",
            properties_schema={
                "Title": {"type": "title"},
                "Description": {"type": "rich_text"},
                "Feature": {"type": "relation", "database_id": features_db_id},
                "Priority": {"type": "select", "options": ["P0", "P1", "P2", "P3"]},
                "Effort": {"type": "select", "options": ["Small", "Medium", "Large"]},
                "Status": {"type": "status", "options": [
                    "Not Started", "In Progress", "In Review", "Done"
                ]},
                "Assignee": {"type": "rich_text"},
            },
        )

    def _create_docs_db(self, parent_page_id: str, features_db_id: str) -> str:
        return self.notion.create_database(
            parent_page_id=parent_page_id,
            title="📄 Documents",
            properties_schema={
                "Title": {"type": "title"},
                "Type": {"type": "select", "options": [
                    "PRD", "Architecture", "Guide", "Meeting Notes"
                ]},
                "Feature": {"type": "relation", "database_id": features_db_id},
                "Status": {"type": "status", "options": ["Draft", "Review", "Final"]},
            },
        )

    def _create_decisions_db(self, parent_page_id: str) -> str:
        return self.notion.create_database(
            parent_page_id=parent_page_id,
            title="🎯 Decisions",
            properties_schema={
                "Decision": {"type": "title"},
                "Context": {"type": "rich_text"},
                "Date": {"type": "date"},
                "Status": {"type": "select", "options": [
                    "Proposed", "Accepted", "Rejected"
                ]},
            },
        )

    def _create_sprints_db(self, parent_page_id: str) -> str:
        return self.notion.create_database(
            parent_page_id=parent_page_id,
            title="🏃 Sprints",
            properties_schema={
                "Sprint Name": {"type": "title"},
                "Goals": {"type": "rich_text"},
                "Start Date": {"type": "date"},
                "End Date": {"type": "date"},
                "Status": {"type": "select", "options": [
                    "Planning", "Active", "Completed", "Cancelled"
                ]},
            },
        )

    # ── Page Creation ──────────────────────────────────────────────────

    def _create_feature_page(self, db_id: str, feature: Feature) -> str:
        properties = {
            "Name": self.notion.title_property(feature.name),
            "Description": self.notion.rich_text_property(feature.description),
            "Priority": self.notion.select_property(feature.priority),
            "Category": self.notion.select_property(feature.category),
            "Status": self.notion.status_property("Not Started"),
        }
        return self.notion.create_page(db_id, properties)

    def _create_task_page(self, db_id: str, task: Task, feature_page_id: str | None) -> str:
        properties = {
            "Title": self.notion.title_property(task.title),
            "Description": self.notion.rich_text_property(task.description),
            "Priority": self.notion.select_property(task.priority),
            "Effort": self.notion.select_property(task.effort),
            "Status": self.notion.status_property("Not Started"),
        }
        if feature_page_id:
            properties["Feature"] = self.notion.relation_property([feature_page_id])
        return self.notion.create_page(db_id, properties)

    def _create_doc_page(
        self,
        db_id: str,
        title: str,
        doc_type: str,
        content: str,
        feature_page_id: str | None = None,
    ) -> str:
        properties = {
            "Title": self.notion.title_property(title),
            "Type": self.notion.select_property(doc_type),
            "Status": self.notion.status_property("Draft"),
        }
        if feature_page_id:
            properties["Feature"] = self.notion.relation_property([feature_page_id])

        # Convert markdown content to Notion blocks (simplified)
        content_blocks = self._markdown_to_blocks(content)
        return self.notion.create_page(db_id, properties, content_blocks)

    def _create_dashboard(
        self,
        parent_page_id: str,
        plan: ProjectPlan,
        features_db_id: str,
        tasks_db_id: str,
        sprints_db_id: str = "",
    ) -> str:
        blocks = [
            self.notion.heading_block("Project Dashboard", level=1),
            self.notion.callout_block(plan.description, "📌"),
            self.notion.divider_block(),
            self.notion.heading_block("Tech Stack", level=2),
        ]
        for tech in plan.tech_stack:
            blocks.append(self.notion.bulleted_list_block(tech))

        blocks.append(self.notion.divider_block())

        dashboard_page_id = self.notion.create_page(
            parent_id=parent_page_id,
            properties=self.notion.title_property("📊 Dashboard"),
            content_blocks=blocks,
            parent_type="page_id",
        )

        # Add linked database views
        if sprints_db_id:
            self.notion.create_linked_database_view(dashboard_page_id, sprints_db_id, "Sprint Board")
        self.notion.create_linked_database_view(dashboard_page_id, features_db_id, "Features Overview")
        self.notion.create_linked_database_view(dashboard_page_id, tasks_db_id, "Priority Tasks")

        return dashboard_page_id

    # ── Update Support ─────────────────────────────────────────────────

    def add_features(
        self,
        config: WorkspaceConfig,
        new_features: list[Feature],
        new_tasks: list[Task],
        new_docs: dict[str, str] | None = None,
    ) -> WorkspaceConfig:
        """Add new features, tasks, and docs to an existing workspace."""
        for feature in new_features:
            page_id = self._create_feature_page(config.features_db_id, feature)
            config.feature_page_ids[feature.name] = page_id

        for task in new_tasks:
            feature_pid = config.feature_page_ids.get(task.feature)
            self._create_task_page(config.tasks_db_id, task, feature_pid)

        if new_docs:
            for feature_name, doc_content in new_docs.items():
                feature_pid = config.feature_page_ids.get(feature_name)
                self._create_doc_page(
                    config.docs_db_id, f"PRD: {feature_name}", "PRD", doc_content, feature_pid
                )

        self.save_config(config)
        return config

    # ── Sprint Support ──────────────────────────────────────────────────

    def build_sprints(
        self,
        config: WorkspaceConfig,
        sprint_plan: SprintPlan,
    ) -> WorkspaceConfig:
        """Create sprint pages and link tasks to them via relation.

        Args:
            config: Current workspace config with task_page_ids.
            sprint_plan: AI-generated sprint plan.

        Returns:
            Updated WorkspaceConfig with sprint_page_ids.
        """
        if not config.sprints_db_id:
            raise ValueError("Sprints database not found. Recreate workspace with 'new' command.")

        # Add Sprint relation column to Tasks DB if not already present
        self._add_sprint_relation_to_tasks(config.tasks_db_id, config.sprints_db_id)

        for sprint in sprint_plan.sprints:
            # Create the sprint page
            sprint_pid = self._create_sprint_page(config.sprints_db_id, sprint)
            config.sprint_page_ids[sprint.name] = sprint_pid

            # Link tasks to this sprint via relation
            for task_title in sprint.task_titles:
                task_pid = config.task_page_ids.get(task_title)
                if task_pid:
                    self.notion.update_page(
                        page_id=task_pid,
                        properties={
                            "Sprint": self.notion.relation_property([sprint_pid]),
                        },
                    )

        # Update dashboard with sprint board view
        self._add_sprint_view_to_dashboard(config.dashboard_page_id, config.sprints_db_id)

        self.save_config(config)
        return config

    def _add_sprint_relation_to_tasks(self, tasks_db_id: str, sprints_db_id: str):
        """Add a Sprint relation column to the Tasks database."""
        try:
            self.notion._retry(
                self.notion.client.databases.update,
                database_id=tasks_db_id,
                properties={
                    "Sprint": {
                        "relation": {
                            "database_id": sprints_db_id,
                            "single_property": {},
                        }
                    }
                },
            )
            logger.info("Added Sprint relation column to Tasks database")
        except Exception as e:
            # Column may already exist from a previous sprint run
            logger.warning(f"Could not add Sprint relation (may already exist): {e}")

    def _create_sprint_page(self, db_id: str, sprint: Sprint) -> str:
        """Create a single sprint page in the Sprints database."""
        properties = {
            "Sprint Name": self.notion.title_property(sprint.name),
            "Goals": self.notion.rich_text_property(sprint.goals),
            "Start Date": self.notion.date_property(sprint.start_date),
            "End Date": self.notion.date_property(sprint.end_date),
            "Status": self.notion.select_property(sprint.status),
        }
        content_blocks = [
            self.notion.heading_block("Sprint Goals", level=2),
            self.notion.paragraph_block(sprint.goals),
            self.notion.divider_block(),
            self.notion.heading_block("Tasks", level=2),
        ]
        for task_title in sprint.task_titles:
            content_blocks.append(self.notion.bulleted_list_block(task_title))

        return self.notion.create_page(db_id, properties, content_blocks)

    def _add_sprint_view_to_dashboard(self, dashboard_page_id: str, sprints_db_id: str):
        """Append a sprint board view to the existing dashboard."""
        self.notion.append_blocks(dashboard_page_id, [
            self.notion.divider_block(),
        ])
        self.notion.create_linked_database_view(
            dashboard_page_id, sprints_db_id, "Sprint Board"
        )

    def get_all_tasks(self, config: WorkspaceConfig) -> list[Task]:
        """Query all tasks from the Notion Tasks database and return as Task models."""
        pages = self.notion.query_database(config.tasks_db_id)
        tasks = []
        for page in pages:
            props = page.get("properties", {})
            title = self._extract_title(props.get("Title", {}))
            description = self._extract_rich_text(props.get("Description", {}))
            priority = self._extract_select(props.get("Priority", {}))
            effort = self._extract_select(props.get("Effort", {}))
            status = self._extract_status(props.get("Status", {}))
            feature = self._extract_relation_title(props.get("Feature", {}))

            if title and priority and effort:
                tasks.append(Task(
                    title=title,
                    description=description or "",
                    feature=feature or "",
                    priority=priority,
                    effort=effort,
                    status=status or "Not Started",
                ))
                # Ensure task_page_ids stays in sync
                config.task_page_ids[title] = page["id"]
        return tasks

    # ── Notion Property Extractors ─────────────────────────────────────

    @staticmethod
    def _extract_title(prop: dict) -> str:
        items = prop.get("title", [])
        return items[0].get("plain_text", "") if items else ""

    @staticmethod
    def _extract_rich_text(prop: dict) -> str:
        items = prop.get("rich_text", [])
        return items[0].get("plain_text", "") if items else ""

    @staticmethod
    def _extract_select(prop: dict) -> str:
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""

    @staticmethod
    def _extract_status(prop: dict) -> str:
        st = prop.get("status")
        return st.get("name", "") if st else ""

    @staticmethod
    def _extract_relation_title(prop: dict) -> str:
        relations = prop.get("relation", [])
        return relations[0].get("id", "") if relations else ""

    # ── Markdown to Blocks Converter ───────────────────────────────────

    @staticmethod
    def _markdown_to_blocks(markdown: str) -> list[dict]:
        """Convert simplified markdown to Notion blocks.

        Handles: headings (#, ##, ###), bullet lists (-), plain paragraphs.
        Notion API limits children to 100 blocks per request.
        """
        blocks = []
        for line in markdown.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]
                    },
                })
            elif stripped.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]
                    },
                })
            elif stripped.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                    },
                })
            elif stripped.startswith("- ") or stripped.startswith("* "):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                    },
                })
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": stripped}}]
                    },
                })

        # Notion limits to 100 blocks per append
        return blocks[:100]


workspace_builder = WorkspaceBuilder()
