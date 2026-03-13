import json
import logging
from pathlib import Path

from models.schemas import ProjectPlan, UpdatePlan
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PlannerAgent:
    """Breaks a startup idea into a structured ProjectPlan."""

    def __init__(self):
        self.system_prompt = (PROMPTS_DIR / "planner.txt").read_text()
        self.update_prompt = (PROMPTS_DIR / "update_planner.txt").read_text()

    def plan(self, startup_description: str) -> ProjectPlan:
        logger.info("Planner agent generating project plan...")
        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=startup_description,
            json_mode=True,
        )
        data = json.loads(response)
        plan = ProjectPlan(**data)
        logger.info(f"Plan generated: {plan.project_name} with {len(plan.features)} features")
        return plan

    def plan_update(self, context: str, update_request: str) -> UpdatePlan:
        """Generate an update plan given current workspace state and user request."""
        logger.info("Planner agent generating update plan...")
        user_message = (
            f"=== CURRENT PROJECT STATE ===\n{context}\n\n"
            f"=== UPDATE REQUEST ===\n{update_request}"
        )
        response = groq_client.chat(
            system_prompt=self.update_prompt,
            user_message=user_message,
            json_mode=True,
        )
        data = json.loads(response)
        update_plan = UpdatePlan(**data)
        logger.info(
            f"Update plan: {len(update_plan.new_features)} new, "
            f"{len(update_plan.updated_features)} updated. {update_plan.summary}"
        )
        return update_plan
