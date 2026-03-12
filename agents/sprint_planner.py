import json
import logging
from datetime import date
from pathlib import Path

from models.schemas import Task, Sprint, SprintPlan
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "sprint_planner.txt"


class SprintPlannerAgent:
    """Analyzes tasks by priority/effort and groups them into 2-week sprints."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

    def plan_sprints(self, tasks: list[Task], start_date: str | None = None) -> SprintPlan:
        """Generate a sprint plan from a list of tasks.

        Args:
            tasks: All tasks to organize into sprints.
            start_date: ISO date string for Sprint 1 start. Defaults to today.

        Returns:
            A validated SprintPlan with sprints and task assignments.
        """
        if not start_date:
            start_date = date.today().isoformat()

        logger.info(f"Sprint planner organizing {len(tasks)} tasks starting {start_date}...")

        # Build task summary for the LLM
        task_lines = []
        for t in tasks:
            task_lines.append(
                f"- Title: {t.title} | Feature: {t.feature} | "
                f"Priority: {t.priority} | Effort: {t.effort} | Status: {t.status}"
            )
        task_list_str = "\n".join(task_lines)

        user_message = (
            f"Start date: {start_date}\n"
            f"Total tasks: {len(tasks)}\n\n"
            f"Tasks:\n{task_list_str}"
        )

        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=user_message,
            json_mode=True,
        )

        data = json.loads(response)
        sprint_plan = SprintPlan(**data)

        # Validate that task_titles reference real tasks
        valid_titles = {t.title for t in tasks}
        for sprint in sprint_plan.sprints:
            sprint.task_titles = [t for t in sprint.task_titles if t in valid_titles]

        logger.info(
            f"Sprint plan generated: {len(sprint_plan.sprints)} sprints "
            f"covering {sum(len(s.task_titles) for s in sprint_plan.sprints)} tasks"
        )
        return sprint_plan


sprint_planner_agent = SprintPlannerAgent()
