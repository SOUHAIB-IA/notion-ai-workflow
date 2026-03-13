import logging

from models.schemas import ProjectPlan, UpdatePlan, Task, Document, WorkspaceConfig
from agents.planner import PlannerAgent
from agents.architect import ArchitectAgent
from agents.task_generator import TaskGeneratorAgent
from agents.doc_writer import DocWriterAgent
from agents.sprint_planner import SprintPlannerAgent
from agents.meeting import MeetingAgent
from services.workspace_builder import WorkspaceBuilder

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main brain that coordinates all agents and the MCP-powered workspace builder."""

    def __init__(self, mcp_client):
        self.mcp = mcp_client
        self.planner = PlannerAgent()
        self.architect = ArchitectAgent()
        self.task_generator = TaskGeneratorAgent()
        self.doc_writer = DocWriterAgent()
        self.sprint_planner = SprintPlannerAgent()
        self.meeting_agent = MeetingAgent()
        self.builder = WorkspaceBuilder(mcp_client)

    async def create_workspace(
        self,
        startup_description: str,
        on_status: callable = None,
    ) -> WorkspaceConfig:
        """Full pipeline: idea -> plan -> architecture -> tasks -> docs -> Notion workspace via MCP."""

        def status(emoji: str, msg: str):
            if on_status:
                on_status(emoji, msg)
            logger.info(msg)

        # Step 1: Plan
        status("🤖", "Planning your startup...")
        plan = self.planner.plan(startup_description)
        status("✅", f"Plan ready: {plan.project_name} with {len(plan.features)} features")

        # Step 2: Architecture
        status("🏗️", "Designing architecture...")
        arch_doc = Document(
            title="Technical Architecture",
            doc_type="Architecture",
            content=self.architect.design(plan),
        )
        status("✅", "Architecture document generated")

        # Step 3: Generate tasks for all features
        status("📋", "Generating tasks for each feature...")
        all_tasks: list[Task] = []
        for feature in plan.features:
            tasks = self.task_generator.generate(feature)
            all_tasks.extend(tasks)
        status("✅", f"Generated {len(all_tasks)} tasks across {len(plan.features)} features")

        # Step 4: Write PRD docs for P0 and P1 features
        status("📄", "Writing documentation for priority features...")
        docs: list[Document] = [arch_doc]
        priority_features = [f for f in plan.features if f.priority in ("P0", "P1")]
        for feature in priority_features:
            content = self.doc_writer.write(plan, feature.name)
            docs.append(Document(
                title=f"PRD: {feature.name}",
                doc_type="PRD",
                content=content,
                feature=feature.name,
            ))
        status("✅", f"Generated {len(docs)} documents")

        # Step 5: Build Notion workspace via MCP
        status("🚀", "Building Notion workspace via MCP...")
        config = await self.builder.build(
            plan=plan,
            tasks=all_tasks,
            docs=docs,
        )
        status(
            "✅",
            f"Workspace created! {len(plan.features)} features, "
            f"{len(all_tasks)} tasks, {len(docs)} documents",
        )

        return config

    async def update_workspace(
        self,
        update_request: str,
        on_status: callable = None,
    ) -> WorkspaceConfig | None:
        """Update an existing workspace: reads live state from Notion via MCP,
        then intelligently adds new features or updates existing ones."""

        def status(emoji: str, msg: str):
            if on_status:
                on_status(emoji, msg)
            logger.info(msg)

        config = self.builder.load_config()
        if not config:
            status("❌", "No existing workspace found. Use 'new' to create one first.")
            return None

        # Step 1: Read ALL features and tasks from Notion via MCP
        status("📖", "Reading current workspace from Notion via MCP...")
        context = await self.builder.build_context_summary(config)
        status("✅", "Workspace state loaded from Notion")

        # Step 2: AI analyzes current state + update request
        status("🤖", "AI is analyzing what to change...")
        update_plan = self.planner.plan_update(context, update_request)

        n_new = len(update_plan.new_features)
        n_upd = len(update_plan.updated_features)
        status("💡", f"AI decision: {update_plan.summary}")

        if n_new == 0 and n_upd == 0:
            status("ℹ️", "No changes needed.")
            return config

        if n_upd > 0:
            status("🔄", f"Updating {n_upd} existing feature(s)...")

        # Step 3: Generate tasks for NEW features only
        new_tasks: list[Task] = []
        if n_new > 0:
            status("📋", f"Generating tasks for {n_new} new feature(s)...")
            for feature in update_plan.new_features:
                tasks = self.task_generator.generate(feature)
                new_tasks.extend(tasks)

        # Step 4: Write docs for new P0/P1 features
        new_docs: list[Document] = []
        priority_new = [f for f in update_plan.new_features if f.priority in ("P0", "P1")]
        if priority_new:
            status("📄", f"Writing docs for {len(priority_new)} priority feature(s)...")
            # Build a temporary ProjectPlan for doc writer context
            temp_plan = ProjectPlan(
                project_name=config.project_name,
                description="",
                tech_stack=[],
                features=update_plan.new_features,
                architecture_notes="",
            )
            for feature in priority_new:
                content = self.doc_writer.write(temp_plan, feature.name)
                new_docs.append(Document(
                    title=f"PRD: {feature.name}",
                    doc_type="PRD",
                    content=content,
                    feature=feature.name,
                ))

        # Step 5: Apply all changes to Notion via MCP
        status("🚀", "Applying changes to Notion via MCP...")
        config = await self.builder.apply_update_plan(
            config, update_plan, new_tasks, new_docs
        )

        parts = []
        if n_upd > 0:
            parts.append(f"updated {n_upd} feature(s)")
        if n_new > 0:
            parts.append(f"added {n_new} feature(s)")
        if new_tasks:
            parts.append(f"{len(new_tasks)} task(s)")
        if new_docs:
            parts.append(f"{len(new_docs)} doc(s)")
        status("✅", f"Done: {', '.join(parts)}")

        return config

    async def process_meeting(
        self,
        meeting_notes: str,
        on_status: callable = None,
    ) -> dict | None:
        """Process meeting notes: extract decisions, action items, blockers
        and write them to Notion via MCP."""

        def status(emoji: str, msg: str):
            if on_status:
                on_status(emoji, msg)
            logger.info(msg)

        config = self.builder.load_config()
        if not config:
            status("❌", "No existing workspace found. Use 'new' to create one first.")
            return None

        # Step 1: Read current state from Notion via MCP
        status("📖", "Reading current workspace from Notion via MCP...")
        context = await self.builder.build_context_summary(config)

        # Step 2: AI extracts structured data from meeting notes
        status("🤖", "AI is analyzing meeting notes...")
        extract = self.meeting_agent.extract(meeting_notes, context)
        status("✅", f"Extracted: {extract.summary}")

        n_dec = len(extract.decisions)
        n_act = len(extract.action_items)
        n_blk = len(extract.blockers)
        status(
            "📊",
            f"Found {n_dec} decision(s), {n_act} action item(s), {n_blk} blocker(s)",
        )

        if n_dec == 0 and n_act == 0 and n_blk == 0:
            status("ℹ️", "Nothing actionable found in meeting notes.")
            return {"decisions_created": 0, "tasks_created": 0, "tasks_blocked": 0}

        # Step 3: Apply everything to Notion via MCP
        status("🚀", "Writing to Notion via MCP...")
        result = await self.builder.apply_meeting_extract(config, extract)

        parts = []
        if result["decisions_created"]:
            parts.append(f"{result['decisions_created']} decision(s)")
        if result["tasks_created"]:
            parts.append(f"{result['tasks_created']} task(s)")
        if result["tasks_blocked"]:
            parts.append(f"{result['tasks_blocked']} task(s) marked blocked")
        status("✅", f"Done: {', '.join(parts)}")

        return result

    async def plan_sprints(
        self,
        on_status: callable = None,
    ) -> WorkspaceConfig | None:
        """Analyze all tasks and create sprint plans in Notion via MCP."""

        def status(emoji: str, msg: str):
            if on_status:
                on_status(emoji, msg)
            logger.info(msg)

        config = self.builder.load_config()
        if not config:
            status("❌", "No existing workspace found. Use 'new' to create one first.")
            return None

        if not config.sprints_db_id:
            status("❌", "Sprints database not found. Recreate workspace with 'new'.")
            return None

        # Read all tasks from Notion via MCP
        status("📖", "Reading tasks from workspace via MCP...")
        tasks = await self.builder.get_all_tasks(config)
        if not tasks:
            status("ℹ️", "No tasks found in workspace.")
            return config

        plannable = [t for t in tasks if t.status in ("Not Started", "In Progress")]
        status("📊", f"Found {len(plannable)} plannable tasks (of {len(tasks)} total)")

        if not plannable:
            status("ℹ️", "All tasks are already completed or in review.")
            return config

        # AI sprint planning
        status("🤖", "AI is analyzing tasks and planning sprints...")
        sprint_plan = self.sprint_planner.plan_sprints(plannable)
        status(
            "✅",
            f"Sprint plan ready: {len(sprint_plan.sprints)} sprints, "
            f"{sum(len(s.task_titles) for s in sprint_plan.sprints)} tasks assigned",
        )

        # Build sprints in Notion via MCP
        status("🏃", "Creating sprints in Notion via MCP...")
        config = await self.builder.build_sprints(config, sprint_plan)

        # Set Sprint 1 to Active
        if sprint_plan.sprints:
            first_sprint = sprint_plan.sprints[0]
            first_sprint_pid = config.sprint_page_ids.get(first_sprint.name)
            if first_sprint_pid:
                await self.mcp.update_page(
                    page_id=first_sprint_pid,
                    properties={"Status": {"select": {"name": "Active"}}},
                )

        status(
            "✅",
            f"Sprints created! {len(sprint_plan.sprints)} sprints in your Notion workspace",
        )

        for sprint in sprint_plan.sprints:
            status(
                "📅",
                f"{sprint.name}: {sprint.start_date} → {sprint.end_date} "
                f"({len(sprint.task_titles)} tasks)",
            )

        return config

    def get_status(self) -> dict | None:
        """Get a summary of the current workspace."""
        config = self.builder.load_config()
        if not config:
            return None
        return {
            "project_name": config.project_name,
            "features_count": len(config.feature_page_ids),
            "feature_names": list(config.feature_page_ids.keys()),
            "sprints_count": len(config.sprint_page_ids),
            "sprint_names": list(config.sprint_page_ids.keys()),
            "workspace_ids": {
                "root_page": config.root_page_id,
                "features_db": config.features_db_id,
                "tasks_db": config.tasks_db_id,
                "docs_db": config.docs_db_id,
                "decisions_db": config.decisions_db_id,
                "sprints_db": config.sprints_db_id,
                "dashboard": config.dashboard_page_id,
            },
        }
