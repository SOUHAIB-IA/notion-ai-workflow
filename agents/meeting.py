import json
import logging
from pathlib import Path

from models.schemas import MeetingExtract
from services.groq_client import groq_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "meeting.txt"


class MeetingAgent:
    """Extracts decisions, action items, and blockers from meeting notes."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text()

    def extract(self, meeting_notes: str, project_context: str) -> MeetingExtract:
        logger.info("Meeting agent extracting structured data from notes...")
        user_message = (
            f"=== PROJECT CONTEXT ===\n{project_context}\n\n"
            f"=== MEETING NOTES ===\n{meeting_notes}"
        )
        response = groq_client.chat(
            system_prompt=self.system_prompt,
            user_message=user_message,
            json_mode=True,
        )
        data = json.loads(response)
        extract = MeetingExtract(**data)
        logger.info(
            f"Extracted: {len(extract.decisions)} decisions, "
            f"{len(extract.action_items)} action items, "
            f"{len(extract.blockers)} blockers"
        )
        return extract
