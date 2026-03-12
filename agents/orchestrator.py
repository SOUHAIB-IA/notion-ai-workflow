import logging

from models.schemas import ProjectPlan, Task, Feature, WorkspaceConfig
from agents.planner import planner_agent
from agents.architect import architect_agent
from agents.task_generator import task_generator_agent
from agents.doc_writer import doc_writer_agent
from agents.sprint_planner import sprint_planner_agent
from services.workspace_builder import workspace_builder

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main brain that coordinates all agents and builds the workspace."""

    def __init__(self):
        self.planner = planner_agent
        self.architect = architect_agent
        self.task_generator = task_generator_agent
        self.doc_writer = doc_writer_agent
        self.sprint_planner = sprint_planner_agent
        self.builder = workspace_builder

    def create_workspace(
        self,
        startup_description: str,
        on_status: callable = None,
    ) -> WorkspaceConfig:
        """Full pipeline: idea -> plan -> architecture -> tasks -> docs -> Notion workspace.

        Args:
            startup_description: User's natural language startup idea.
            on_status: Optional callback for status updates, receives (emoji, message).

        Returns:
            WorkspaceConfig with all created Notion resource IDs.
        """

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
        architecture_doc = self.architect.design(plan)
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
        feature_docs: dict[str, str] = {}
        priority_features = [f for f in plan.features if f.priority in ("P0", "P1")]
        for feature in priority_features:
            doc = self.doc_writer.write(plan, feature.name)
            feature_docs[feature.name] = doc
        status("✅", f"Generated {len(feature_docs)} PRD documents")

        # Step 5: Build Notion workspace
        status("🚀", "Building Notion workspace...")
        config = self.builder.build_workspace(
            plan=plan,
            tasks=all_tasks,
            architecture_doc=architecture_doc,
            feature_docs=feature_docs,
        )
        status(
            "✅",
            f"Workspace created! {len(plan.features)} features, "
            f"{len(all_tasks)} tasks, {len(feature_docs)} documents",
        )

        return config

    def update_workspace(
        self,
        update_request: str,
        on_status: callable = None,
    ) -> WorkspaceConfig | None:
        """Update an existing workspace with new features/tasks.

        Args:
            update_request: Natural language description of what to add/change.
            on_status: Optional callback for status updates.

        Returns:
            Updated WorkspaceConfig, or None if no workspace exists.
        """

        def status(emoji: str, msg: str):
            if on_status:
                on_status(emoji, msg)
            logger.info(msg)

        config = self.builder.load_config()
        if not config:
            status("❌", "No existing workspace found. Use 'new' to create one first.")
            return None

        # Use planner to generate new features from the update request
        status("🤖", "Analyzing update request...")
        context = (
            f"Existing project: {config.project_name}\n"
            f"Existing features: {', '.join(config.feature_page_ids.keys())}\n\n"
            f"Update request: {update_request}\n\n"
            f"Generate ONLY the new features to add. Do not duplicate existing features. "
            f"Keep the same project name and description. Focus on the update request."
        )
        plan = self.planner.plan(context)

        # Filter out any features that already exist
        existing_names = set(config.feature_page_ids.keys())
        new_features = [f for f in plan.features if f.name not in existing_names]

        if not new_features:
            status("ℹ️", "No new features to add.")
            return config

        # Generate tasks for new features
        status("📋", f"Generating tasks for {len(new_features)} new features...")
        new_tasks: list[Task] = []
        for feature in new_features:
            tasks = self.task_generator.generate(feature)
            new_tasks.extend(tasks)

        # Generate docs for P0/P1 new features
        new_docs: dict[str, str] = {}
        priority_new = [f for f in new_features if f.priority in ("P0", "P1")]
        if priority_new:
            status("📄", "Writing docs for new priority features...")
            for feature in priority_new:
                plan.features = new_features  # context for doc writer
                doc = self.doc_writer.write(plan, feature.name)
                new_docs[feature.name] = doc

        # Add to Notion
        status("🚀", "Adding to Notion workspace...")
        config = self.builder.add_features(config, new_features, new_tasks, new_docs)
        status(
            "✅",
            f"Added {len(new_features)} features, {len(new_tasks)} tasks, "
            f"{len(new_docs)} documents",
        )

        return config

    def plan_sprints(
        self,
        on_status: callable = None,
    ) -> WorkspaceConfig | None:
        """Analyze all tasks and create sprint plans in Notion.

        Reads current tasks from the workspace, uses AI to organize them
        into 2-week sprints, creates Sprint pages, and links tasks.

        Args:
            on_status: Optional callback for status updates.

        Returns:
            Updated WorkspaceConfig, or None if no workspace exists.
        """

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

        # Read all tasks from Notion
        status("📖", "Reading tasks from workspace...")
        tasks = self.builder.get_all_tasks(config)
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
            f"{sum(len(s.task_titles) for s in sprint_plan.sprints)} tasks assigned"
        )

        # Build sprints in Notion
        status("🏃", "Creating sprints in Notion...")
        config = self.builder.build_sprints(config, sprint_plan)

        # Set Sprint 1 to Active
        if sprint_plan.sprints:
            first_sprint = sprint_plan.sprints[0]
            first_sprint_pid = config.sprint_page_ids.get(first_sprint.name)
            if first_sprint_pid:
                from services.notion_service import notion_service
                notion_service.update_page(
                    first_sprint_pid,
                    {"Status": notion_service.select_property("Active")},
                )

        status(
            "✅",
            f"Sprints created! {len(sprint_plan.sprints)} sprints in your Notion workspace"
        )

        # Print sprint summary
        for sprint in sprint_plan.sprints:
            status(
                "📅",
                f"{sprint.name}: {sprint.start_date} → {sprint.end_date} "
                f"({len(sprint.task_titles)} tasks)"
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


orchestrator = Orchestrator()
