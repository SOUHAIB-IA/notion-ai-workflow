import json
import logging
from pathlib import Path

from models.schemas import Feature, Task
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "task_generator.txt"


class TaskGeneratorAgent:
    """Generates granular tasks from a feature."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

    def generate(self, feature: Feature) -> list[Task]:
        logger.info(f"Task generator creating tasks for: {feature.name}")
        user_message = (
            f"Feature: {feature.name}\n"
            f"Description: {feature.description}\n"
            f"Priority: {feature.priority}\n"
            f"Category: {feature.category}"
        )
        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=user_message,
            json_mode=True,
        )
        data = json.loads(response)
        tasks = [Task(**t) for t in data["tasks"]]
        logger.info(f"Generated {len(tasks)} tasks for {feature.name}")
        return tasks
