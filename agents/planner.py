import json
import logging
from pathlib import Path

from models.schemas import ProjectPlan
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.txt"


class PlannerAgent:
    """Breaks a startup idea into a structured ProjectPlan."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

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
