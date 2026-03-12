import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.groq_api_key = self._require("GROQ_API_KEY")
        self.notion_api_key = self._require("NOTION_API_KEY")
        self.notion_root_page_id = self._require("NOTION_ROOT_PAGE_ID")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.workspace_config_path = os.getenv("WORKSPACE_CONFIG_PATH", "workspace_config.json")

    @staticmethod
    def _require(var_name: str) -> str:
        value = os.getenv(var_name)
        if not value:
            raise EnvironmentError(
                f"Missing required environment variable: {var_name}. "
                f"Copy .env.example to .env and fill in your keys."
            )
        return value


settings = Settings()
