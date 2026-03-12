import time
import logging
from groq import Groq, APIError, RateLimitError

from config import settings

logger = logging.getLogger(__name__)


class GroqClient:
    """Wrapper around Groq SDK with retry logic."""

    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.max_retries = 3

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request to Groq with retry logic.

        Args:
            system_prompt: The system instruction for the model.
            user_message: The user's message/query.
            json_mode: If True, request JSON-formatted response.

        Returns:
            The model's response text.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except RateLimitError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"Rate limited (attempt {attempt + 1}/{self.max_retries}), waiting {wait}s...")
                time.sleep(wait)
            except APIError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"API error (attempt {attempt + 1}/{self.max_retries}): {e}, waiting {wait}s...")
                time.sleep(wait)

        raise RuntimeError(f"Groq API failed after {self.max_retries} retries: {last_error}")


groq_client = GroqClient()
