import json
import logging
from pathlib import Path

from config import settings
from models.schemas import (
    Feature, FeatureUpdate, Task, Document, Sprint, SprintPlan,
    ProjectPlan, UpdatePlan, WorkspaceConfig,
)

logger = logging.getLogger(__name__)


class WorkspaceBuilder:
    """Orchestrates Notion workspace creation via MCP client.

    ALL Notion operations go through the MCP client — no direct API calls.
    """

    def __init__(self, mcp_client):
        self.mcp = mcp_client
        self.config_path = Path(settings.workspace_config_path)

    def save_config(self, config: WorkspaceConfig):
        self.config_path.write_text(config.model_dump_json(indent=2))
        logger.info(f"Workspace config saved to {self.config_path}")

    def load_config(self) -> WorkspaceConfig | None:
        if not self.config_path.exists():
            return None
        data = json.loads(self.config_path.read_text())
        return WorkspaceConfig(**data)

    # ── Full Workspace Build ───────────────────────────────────────────

    async def build(
        self,
        plan: ProjectPlan,
        tasks: list[Task],
        docs: list[Document],
    ) -> WorkspaceConfig:
        """Create the complete Notion workspace via MCP.

        Args:
            plan: The project plan with features.
            tasks: All generated tasks.
            docs: Architecture doc + feature PRDs.

        Returns:
            WorkspaceConfig with all created resource IDs.
        """
        root_page_id = settings.notion_root_page_id

        # Step 1: Create root project page
        logger.info("Creating root project page via MCP...")
        project_page = await self.mcp.create_page(
            parent_id=root_page_id,
            properties={
                "title": [{"text": {"content": f"🚀 {plan.project_name} — FounderOS"}}],
            },
            children=[
                {
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"text": {"content": plan.description}}],
                        "icon": {"emoji": "🎯"},
                    },
                },
                {
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Tech Stack"}}],
                    },
                },
                *[
                    {
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"text": {"content": tech}}],
                        },
                    }
                    for tech in plan.tech_stack
                ],
                {"type": "divider", "divider": {}},
            ],
            is_database_child=False,
        )
        project_page_id = project_page["id"]

        # Step 2: Create databases via MCP
        logger.info("Creating Features database via MCP...")
        features_db = await self.mcp.create_database(
            parent_page_id=project_page_id,
            title="📋 Features",
            properties={
                "Name": {"title": {}},
                "Description": {"rich_text": {}},
                "Priority": {"select": {"options": [
                    {"name": "P0", "color": "red"},
                    {"name": "P1", "color": "orange"},
                    {"name": "P2", "color": "yellow"},
                    {"name": "P3", "color": "gray"},
                ]}},
                "Category": {"select": {"options": [
                    {"name": "Backend"}, {"name": "Frontend"},
                    {"name": "Infrastructure"}, {"name": "Data"},
                    {"name": "DevOps"}, {"name": "Design"}, {"name": "Mobile"},
                ]}},
                "Status": {"status": {}},
            },
        )
        features_db_id = features_db["id"]

        logger.info("Creating Tasks database via MCP...")
        tasks_db = await self.mcp.create_database(
            parent_page_id=project_page_id,
            title="✅ Tasks",
            properties={
                "Title": {"title": {}},
                "Description": {"rich_text": {}},
                "Feature": {"relation": {"database_id": features_db_id, "single_property": {}}},
                "Priority": {"select": {"options": [
                    {"name": "P0", "color": "red"},
                    {"name": "P1", "color": "orange"},
                    {"name": "P2", "color": "yellow"},
                    {"name": "P3", "color": "gray"},
                ]}},
                "Effort": {"select": {"options": [
                    {"name": "Small", "color": "green"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "Large", "color": "red"},
                ]}},
                "Status": {"status": {}},
                "Assignee": {"rich_text": {}},
            },
        )
        tasks_db_id = tasks_db["id"]

        logger.info("Creating Documents database via MCP...")
        docs_db = await self.mcp.create_database(
            parent_page_id=project_page_id,
            title="📄 Documents",
            properties={
                "Title": {"title": {}},
                "Type": {"select": {"options": [
                    {"name": "PRD"}, {"name": "Architecture"},
                    {"name": "Guide"}, {"name": "Meeting Notes"},
                ]}},
                "Feature": {"relation": {"database_id": features_db_id, "single_property": {}}},
                "Status": {"status": {}},
            },
        )
        docs_db_id = docs_db["id"]

        logger.info("Creating Decisions database via MCP...")
        decisions_db = await self.mcp.create_database(
            parent_page_id=project_page_id,
            title="🎯 Decisions",
            properties={
                "Decision": {"title": {}},
                "Context": {"rich_text": {}},
                "Date": {"date": {}},
                "Status": {"select": {"options": [
                    {"name": "Proposed"}, {"name": "Accepted"}, {"name": "Rejected"},
                ]}},
            },
        )
        decisions_db_id = decisions_db["id"]

        logger.info("Creating Sprints database via MCP...")
        sprints_db = await self.mcp.create_database(
            parent_page_id=project_page_id,
            title="🏃 Sprints",
            properties={
                "Sprint Name": {"title": {}},
                "Goals": {"rich_text": {}},
                "Start Date": {"date": {}},
                "End Date": {"date": {}},
                "Status": {"select": {"options": [
                    {"name": "Planning"}, {"name": "Active"},
                    {"name": "Completed"}, {"name": "Cancelled"},
                ]}},
            },
        )
        sprints_db_id = sprints_db["id"]

        # Step 3: Populate features
        logger.info("Populating features via MCP...")
        feature_page_ids = {}
        for feature in plan.features:
            page = await self.mcp.create_page(
                parent_id=features_db_id,
                properties={
                    "Name": {"title": [{"text": {"content": feature.name}}]},
                    "Description": {"rich_text": [{"text": {"content": feature.description}}]},
                    "Priority": {"select": {"name": feature.priority}},
                    "Category": {"select": {"name": feature.category}},
                },
            )
            feature_page_ids[feature.name] = page["id"]

        # Step 4: Populate tasks with feature relations
        logger.info("Populating tasks via MCP...")
        task_page_ids = {}
        for task in tasks:
            props = {
                "Title": {"title": [{"text": {"content": task.title}}]},
                "Description": {"rich_text": [{"text": {"content": task.description}}]},
                "Priority": {"select": {"name": task.priority}},
                "Effort": {"select": {"name": task.effort}},
            }
            feature_id = feature_page_ids.get(task.feature)
            if feature_id:
                props["Feature"] = {"relation": [{"id": feature_id}]}
            page = await self.mcp.create_page(parent_id=tasks_db_id, properties=props)
            task_page_ids[task.title] = page["id"]

        # Step 5: Create document pages with content blocks
        logger.info("Creating documents via MCP...")
        for doc in docs:
            props = {
                "Title": {"title": [{"text": {"content": doc.title}}]},
                "Type": {"select": {"name": doc.doc_type}},
            }
            feature_id = feature_page_ids.get(doc.feature) if doc.feature else None
            if feature_id:
                props["Feature"] = {"relation": [{"id": feature_id}]}
            content_blocks = self._markdown_to_blocks(doc.content)
            await self.mcp.create_page(
                parent_id=docs_db_id,
                properties=props,
                children=content_blocks,
            )

        # Step 6: Create dashboard page
        logger.info("Creating dashboard via MCP...")
        dashboard_blocks = [
            {"type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": "Project Dashboard"}}]}},
            {"type": "callout", "callout": {
                "rich_text": [{"text": {"content": plan.description}}],
                "icon": {"emoji": "📌"},
            }},
            {"type": "divider", "divider": {}},
            {"type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Tech Stack"}}]}},
            *[{"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": t}}],
            }} for t in plan.tech_stack],
            {"type": "divider", "divider": {}},
        ]
        dashboard_page = await self.mcp.create_page(
            parent_id=project_page_id,
            properties={
                "title": [{"text": {"content": "📊 Dashboard"}}],
            },
            children=dashboard_blocks,
            is_database_child=False,
        )
        dashboard_page_id = dashboard_page["id"]

        # Add linked database views to dashboard
        await self._add_linked_db_view(dashboard_page_id, sprints_db_id, "Sprint Board")
        await self._add_linked_db_view(dashboard_page_id, features_db_id, "Features Overview")
        await self._add_linked_db_view(dashboard_page_id, tasks_db_id, "Priority Tasks")

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

    # ── Update Support ─────────────────────────────────────────────────

    async def add_features(
        self,
        config: WorkspaceConfig,
        new_features: list[Feature],
        new_tasks: list[Task],
        new_docs: list[Document] | None = None,
    ) -> WorkspaceConfig:
        """Add new features, tasks, and docs to an existing workspace via MCP."""
        for feature in new_features:
            page = await self.mcp.create_page(
                parent_id=config.features_db_id,
                properties={
                    "Name": {"title": [{"text": {"content": feature.name}}]},
                    "Description": {"rich_text": [{"text": {"content": feature.description}}]},
                    "Priority": {"select": {"name": feature.priority}},
                    "Category": {"select": {"name": feature.category}},
                },
            )
            config.feature_page_ids[feature.name] = page["id"]

        for task in new_tasks:
            props = {
                "Title": {"title": [{"text": {"content": task.title}}]},
                "Description": {"rich_text": [{"text": {"content": task.description}}]},
                "Priority": {"select": {"name": task.priority}},
                "Effort": {"select": {"name": task.effort}},
            }
            feature_id = config.feature_page_ids.get(task.feature)
            if feature_id:
                props["Feature"] = {"relation": [{"id": feature_id}]}
            page = await self.mcp.create_page(parent_id=config.tasks_db_id, properties=props)
            config.task_page_ids[task.title] = page["id"]

        if new_docs:
            for doc in new_docs:
                props = {
                    "Title": {"title": [{"text": {"content": doc.title}}]},
                    "Type": {"select": {"name": doc.doc_type}},
                }
                feature_id = config.feature_page_ids.get(doc.feature) if doc.feature else None
                if feature_id:
                    props["Feature"] = {"relation": [{"id": feature_id}]}
                content_blocks = self._markdown_to_blocks(doc.content)
                await self.mcp.create_page(
                    parent_id=config.docs_db_id,
                    properties=props,
                    children=content_blocks,
                )

        self.save_config(config)
        return config

    async def get_all_features(self, config: WorkspaceConfig) -> list[Feature]:
        """Query all features from the Notion Features database via MCP."""
        result = await self.mcp.query_database(config.features_db_id)
        pages = result.get("results", []) if isinstance(result, dict) else []
        features = []
        for page in pages:
            props = page.get("properties", {})
            name = self._extract_title(props.get("Name", {}))
            description = self._extract_rich_text(props.get("Description", {}))
            priority = self._extract_select(props.get("Priority", {}))
            category = self._extract_select(props.get("Category", {}))
            status = self._extract_status(props.get("Status", {}))

            if name and priority:
                features.append(Feature(
                    name=name,
                    description=description or "",
                    priority=priority,
                    category=category or "Backend",
                ))
                # Sync config with live Notion page IDs
                config.feature_page_ids[name] = page["id"]
        return features

    async def build_context_summary(self, config: WorkspaceConfig) -> str:
        """Build a rich context string from live Notion data via MCP."""
        features = await self.get_all_features(config)
        tasks = await self.get_all_tasks(config)

        lines = [f"Project: {config.project_name}", ""]

        lines.append(f"=== FEATURES ({len(features)}) ===")
        for f in features:
            lines.append(f"- {f.name} [{f.priority}] ({f.category}): {f.description}")

        lines.append(f"\n=== TASKS ({len(tasks)}) ===")
        for t in tasks:
            lines.append(
                f"- {t.title} [{t.priority}, {t.effort}] (status: {t.status}) "
                f"[feature: {t.feature or 'unlinked'}]"
            )

        return "\n".join(lines)

    async def apply_update_plan(
        self,
        config: WorkspaceConfig,
        update_plan: UpdatePlan,
        new_tasks: list[Task],
        new_docs: list[Document] | None = None,
    ) -> WorkspaceConfig:
        """Apply an UpdatePlan: create new features and update existing ones via MCP."""
        # 1. Update existing features
        for fu in update_plan.updated_features:
            page_id = config.feature_page_ids.get(fu.name)
            if not page_id:
                logger.warning(f"Cannot update feature '{fu.name}': not found in config")
                continue
            props = {}
            if fu.description is not None:
                props["Description"] = {"rich_text": [{"text": {"content": fu.description}}]}
            if fu.priority is not None:
                props["Priority"] = {"select": {"name": fu.priority}}
            if fu.category is not None:
                props["Category"] = {"select": {"name": fu.category}}
            if props:
                await self.mcp.update_page(page_id=page_id, properties=props)
                logger.info(f"Updated feature '{fu.name}' via MCP")

        # 2. Add new features, tasks, docs
        if update_plan.new_features or new_tasks or new_docs:
            config = await self.add_features(
                config, update_plan.new_features, new_tasks, new_docs
            )

        self.save_config(config)
        return config

    # ── Meeting Support ────────────────────────────────────────────────

    async def apply_meeting_extract(
        self,
        config: WorkspaceConfig,
        extract: "MeetingExtract",
    ) -> dict:
        """Write decisions, action-item tasks, and blocker updates to Notion via MCP.

        Returns a summary dict with counts of what was created/updated.
        """
        from models.schemas import MeetingExtract  # deferred to avoid circular

        decisions_created = 0
        tasks_created = 0
        tasks_blocked = 0
        today = __import__("datetime").date.today().isoformat()

        # 1. Create decision entries in the Decisions database
        for d in extract.decisions:
            await self.mcp.create_page(
                parent_id=config.decisions_db_id,
                properties={
                    "Decision": {"title": [{"text": {"content": d.decision}}]},
                    "Context": {"rich_text": [{"text": {"content": d.context}}]},
                    "Date": {"date": {"start": today}},
                    "Status": {"select": {"name": d.status}},
                },
            )
            decisions_created += 1

        # 2. Create action-item tasks in the Tasks database
        for ai in extract.action_items:
            props = {
                "Title": {"title": [{"text": {"content": ai.title}}]},
                "Description": {"rich_text": [{"text": {"content": ai.description}}]},
                "Priority": {"select": {"name": ai.priority}},
                "Effort": {"select": {"name": ai.effort}},
            }
            feature_id = config.feature_page_ids.get(ai.feature) if ai.feature else None
            if feature_id:
                props["Feature"] = {"relation": [{"id": feature_id}]}
            page = await self.mcp.create_page(
                parent_id=config.tasks_db_id, properties=props
            )
            config.task_page_ids[ai.title] = page["id"]
            tasks_created += 1

        # 3. Mark blocked tasks — update their status via MCP
        for b in extract.blockers:
            task_pid = config.task_page_ids.get(b.task_title)
            if not task_pid:
                logger.warning(f"Blocker: task '{b.task_title}' not found, skipping")
                continue
            # Append a blocker note to the task's description and change status
            # Notion status "Blocked" may not exist, so we add a callout block instead
            await self.mcp.append_blocks(task_pid, [
                {"type": "callout", "callout": {
                    "rich_text": [{"text": {"content": f"BLOCKED: {b.reason}"}}],
                    "icon": {"emoji": "🚫"},
                }},
            ])
            tasks_blocked += 1

        # 4. Store meeting notes page in Documents database
        content_lines = [f"## Meeting Summary", extract.summary, ""]
        if extract.decisions:
            content_lines.append("## Decisions")
            for d in extract.decisions:
                content_lines.append(f"- [{d.status}] {d.decision} — {d.context}")
            content_lines.append("")
        if extract.action_items:
            content_lines.append("## Action Items")
            for ai in extract.action_items:
                feat = f" ({ai.feature})" if ai.feature else ""
                content_lines.append(f"- [{ai.priority}] {ai.title}{feat}")
            content_lines.append("")
        if extract.blockers:
            content_lines.append("## Blockers")
            for b in extract.blockers:
                content_lines.append(f"- {b.task_title}: {b.reason}")

        content_blocks = self._markdown_to_blocks("\n".join(content_lines))
        await self.mcp.create_page(
            parent_id=config.docs_db_id,
            properties={
                "Title": {"title": [{"text": {"content": f"Meeting Notes — {today}"}}]},
                "Type": {"select": {"name": "Meeting Notes"}},
            },
            children=content_blocks,
        )

        self.save_config(config)
        return {
            "decisions_created": decisions_created,
            "tasks_created": tasks_created,
            "tasks_blocked": tasks_blocked,
        }

    # ── Sprint Support ─────────────────────────────────────────────────

    async def build_sprints(
        self,
        config: WorkspaceConfig,
        sprint_plan: SprintPlan,
    ) -> WorkspaceConfig:
        """Create sprint pages and link tasks to them via MCP."""
        if not config.sprints_db_id:
            raise ValueError("Sprints database not found. Recreate workspace with 'new'.")

        # Add Sprint relation column to Tasks DB
        await self._add_sprint_relation_to_tasks(config.tasks_db_id, config.sprints_db_id)

        for sprint in sprint_plan.sprints:
            # Create sprint page
            sprint_pid = await self._create_sprint_page(config.sprints_db_id, sprint)
            config.sprint_page_ids[sprint.name] = sprint_pid

            # Link tasks to this sprint
            for task_title in sprint.task_titles:
                task_pid = config.task_page_ids.get(task_title)
                if task_pid:
                    await self.mcp.update_page(
                        page_id=task_pid,
                        properties={
                            "Sprint": {"relation": [{"id": sprint_pid}]},
                        },
                    )

        # Add sprint board view to dashboard
        await self.mcp.append_blocks(config.dashboard_page_id, [
            {"type": "divider", "divider": {}},
        ])
        await self._add_linked_db_view(
            config.dashboard_page_id, config.sprints_db_id, "Sprint Board"
        )

        self.save_config(config)
        return config

    async def _add_sprint_relation_to_tasks(self, tasks_db_id: str, sprints_db_id: str):
        """Add a Sprint relation column to the Tasks database via MCP."""
        try:
            await self.mcp.update_database(
                database_id=tasks_db_id,
                properties={
                    "Sprint": {
                        "relation": {
                            "database_id": sprints_db_id,
                            "single_property": {},
                        },
                    },
                },
            )
            logger.info("Added Sprint relation column to Tasks database via MCP")
        except Exception as e:
            logger.warning(f"Could not add Sprint relation (may already exist): {e}")

    async def _create_sprint_page(self, db_id: str, sprint: Sprint) -> str:
        """Create a single sprint page in the Sprints database via MCP."""
        content_blocks = [
            {"type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Sprint Goals"}}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": sprint.goals}}]}},
            {"type": "divider", "divider": {}},
            {"type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Tasks"}}]}},
            *[{"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": title}}],
            }} for title in sprint.task_titles],
        ]
        page = await self.mcp.create_page(
            parent_id=db_id,
            properties={
                "Sprint Name": {"title": [{"text": {"content": sprint.name}}]},
                "Goals": {"rich_text": [{"text": {"content": sprint.goals}}]},
                "Start Date": {"date": {"start": sprint.start_date}},
                "End Date": {"date": {"start": sprint.end_date}},
                "Status": {"select": {"name": sprint.status}},
            },
            children=content_blocks,
        )
        return page["id"]

    async def get_all_tasks(self, config: WorkspaceConfig) -> list[Task]:
        """Query all tasks from the Notion Tasks database via MCP."""
        result = await self.mcp.query_database(config.tasks_db_id)
        pages = result.get("results", []) if isinstance(result, dict) else []
        tasks = []
        for page in pages:
            props = page.get("properties", {})
            title = self._extract_title(props.get("Title", {}))
            description = self._extract_rich_text(props.get("Description", {}))
            priority = self._extract_select(props.get("Priority", {}))
            effort = self._extract_select(props.get("Effort", {}))
            status = self._extract_status(props.get("Status", {}))

            if title and priority and effort:
                tasks.append(Task(
                    title=title,
                    description=description or "",
                    feature="",
                    priority=priority,
                    effort=effort,
                    status=status or "Not Started",
                ))
                config.task_page_ids[title] = page["id"]
        return tasks

    # ── Helpers ────────────────────────────────────────────────────────

    async def _add_linked_db_view(self, page_id: str, db_id: str, title: str):
        """Embed a linked database view on a page via MCP."""
        await self.mcp.append_blocks(page_id, [
            {"type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": title}}]}},
            {"type": "link_to_page", "link_to_page": {"type": "database_id", "database_id": db_id}},
        ])

    @staticmethod
    def _markdown_to_blocks(markdown: str) -> list[dict]:
        """Convert simplified markdown to Notion blocks."""
        blocks = []
        for line in markdown.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("### "):
                blocks.append({"type": "heading_3", "heading_3": {
                    "rich_text": [{"text": {"content": stripped[4:]}}],
                }})
            elif stripped.startswith("## "):
                blocks.append({"type": "heading_2", "heading_2": {
                    "rich_text": [{"text": {"content": stripped[3:]}}],
                }})
            elif stripped.startswith("# "):
                blocks.append({"type": "heading_1", "heading_1": {
                    "rich_text": [{"text": {"content": stripped[2:]}}],
                }})
            elif stripped.startswith("- ") or stripped.startswith("* "):
                blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {
                    "rich_text": [{"text": {"content": stripped[2:]}}],
                }})
            else:
                blocks.append({"type": "paragraph", "paragraph": {
                    "rich_text": [{"text": {"content": stripped}}],
                }})
        return blocks[:100]

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
