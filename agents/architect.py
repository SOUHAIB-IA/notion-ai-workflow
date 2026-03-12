import logging
from pathlib import Path

from models.schemas import ProjectPlan
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "architect.txt"


class ArchitectAgent:
    """Designs technical architecture from a ProjectPlan."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

    def design(self, plan: ProjectPlan) -> str:
        logger.info("Architect agent designing architecture...")
        user_message = (
            f"Project: {plan.project_name}\n"
            f"Description: {plan.description}\n"
            f"Tech Stack: {', '.join(plan.tech_stack)}\n\n"
            f"Features:\n"
        )
        for f in plan.features:
            user_message += f"- [{f.priority}] {f.name} ({f.category}): {f.description}\n"
        user_message += f"\nArchitecture Notes: {plan.architecture_notes}"

        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=user_message,
            json_mode=False,
        )
        logger.info("Architecture document generated.")
        return response
