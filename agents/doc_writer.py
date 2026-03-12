import logging
from pathlib import Path

from models.schemas import ProjectPlan
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "doc_writer.txt"


class DocWriterAgent:
    """Generates PRD documentation for features."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

    def write(self, plan: ProjectPlan, feature_name: str) -> str:
        logger.info(f"Doc writer generating PRD for: {feature_name}")
        feature = next((f for f in plan.features if f.name == feature_name), None)
        if not feature:
            raise ValueError(f"Feature '{feature_name}' not found in plan.")

        user_message = (
            f"Project: {plan.project_name}\n"
            f"Project Description: {plan.description}\n"
            f"Tech Stack: {', '.join(plan.tech_stack)}\n\n"
            f"Feature to document:\n"
            f"- Name: {feature.name}\n"
            f"- Description: {feature.description}\n"
            f"- Priority: {feature.priority}\n"
            f"- Category: {feature.category}\n\n"
            f"Other features in the project (for context):\n"
        )
        for f in plan.features:
            if f.name != feature_name:
                user_message += f"- {f.name}: {f.description}\n"

        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=user_message,
            json_mode=False,
        )
        logger.info(f"PRD generated for {feature_name}")
        return response
