import time
import logging
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError

from config import settings

logger = logging.getLogger(__name__)


class NotionService:
    """Handles all Notion API CRUD operations with retry logic."""

    def __init__(self):
        self.client = Client(auth=settings.notion_api_key)
        self.max_retries = 3

    def _retry(self, func, *args, **kwargs) -> Any:
        """Execute a Notion API call with retry logic."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except APIResponseError as e:
                last_error = e
                if e.status == 429 or e.status >= 500:
                    wait = 2 ** attempt
                    logger.warning(
                        f"Notion API error {e.status} (attempt {attempt + 1}/{self.max_retries}), "
                        f"waiting {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Notion API failed after {self.max_retries} retries: {last_error}")

    # ── Property Builders ──────────────────────────────────────────────

    @staticmethod
    def _build_property_schema(prop_type: str, **kwargs) -> dict:
        """Build a Notion database property schema entry."""
        schema: dict[str, Any] = {}

        if prop_type == "title":
            schema["title"] = {}
        elif prop_type == "rich_text":
            schema["rich_text"] = {}
        elif prop_type == "number":
            schema["number"] = {"format": kwargs.get("format", "number")}
        elif prop_type == "select":
            options = [{"name": opt} for opt in kwargs.get("options", [])]
            schema["select"] = {"options": options}
        elif prop_type == "multi_select":
            options = [{"name": opt} for opt in kwargs.get("options", [])]
            schema["multi_select"] = {"options": options}
        elif prop_type == "date":
            schema["date"] = {}
        elif prop_type == "checkbox":
            schema["checkbox"] = {}
        elif prop_type == "url":
            schema["url"] = {}
        elif prop_type == "relation":
            schema["relation"] = {
                "database_id": kwargs["database_id"],
                "single_property": {},
            }
        elif prop_type == "status":
            options = [{"name": opt} for opt in kwargs.get("options", ["Not Started", "In Progress", "Done"])]
            groups = kwargs.get("groups")
            schema["status"] = {"options": options}
            if groups:
                schema["status"]["groups"] = groups
        else:
            raise ValueError(f"Unsupported property type: {prop_type}")

        return schema

    # ── Database Operations ────────────────────────────────────────────

    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties_schema: dict[str, dict],
    ) -> str:
        """Create a Notion database under a parent page.

        Args:
            parent_page_id: The parent page ID.
            title: Database title.
            properties_schema: Dict mapping property name to schema config.
                Each value should have a "type" key and type-specific params.
                Example: {"Name": {"type": "title"}, "Priority": {"type": "select", "options": ["P0","P1"]}}

        Returns:
            The created database ID.
        """
        properties = {}
        for prop_name, prop_config in properties_schema.items():
            prop_type = prop_config.pop("type")
            properties[prop_name] = self._build_property_schema(prop_type, **prop_config)
            prop_config["type"] = prop_type  # restore for caller

        result = self._retry(
            self.client.databases.create,
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=properties,
        )
        db_id = result["id"]
        logger.info(f"Created database '{title}' with ID: {db_id}")
        return db_id

    def query_database(
        self,
        database_id: str,
        filter: dict | None = None,
        sorts: list[dict] | None = None,
    ) -> list[dict]:
        """Query a Notion database with optional filter and sort."""
        kwargs: dict[str, Any] = {"database_id": database_id}
        if filter:
            kwargs["filter"] = filter
        if sorts:
            kwargs["sorts"] = sorts

        result = self._retry(self.client.databases.query, **kwargs)
        return result.get("results", [])

    # ── Page Operations ────────────────────────────────────────────────

    def create_page(
        self,
        parent_id: str,
        properties: dict[str, Any],
        content_blocks: list[dict] | None = None,
        parent_type: str = "database_id",
    ) -> str:
        """Create a page in a database or under a page.

        Args:
            parent_id: Database ID or page ID.
            properties: Notion-formatted property values.
            content_blocks: Optional list of block children.
            parent_type: "database_id" or "page_id".

        Returns:
            The created page ID.
        """
        kwargs: dict[str, Any] = {
            "parent": {"type": parent_type, parent_type: parent_id},
            "properties": properties,
        }
        if content_blocks:
            kwargs["children"] = content_blocks

        result = self._retry(self.client.pages.create, **kwargs)
        return result["id"]

    def get_page(self, page_id: str) -> dict:
        """Retrieve a page by ID."""
        return self._retry(self.client.pages.retrieve, page_id=page_id)

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
        content_blocks: list[dict] | None = None,
    ):
        """Update page properties and optionally append content blocks."""
        self._retry(
            self.client.pages.update,
            page_id=page_id,
            properties=properties,
        )
        if content_blocks:
            self._retry(
                self.client.blocks.children.append,
                block_id=page_id,
                children=content_blocks,
            )

    # ── Block Operations ───────────────────────────────────────────────

    def append_blocks(self, page_id: str, blocks: list[dict]):
        """Append child blocks to a page."""
        self._retry(
            self.client.blocks.children.append,
            block_id=page_id,
            children=blocks,
        )

    def create_linked_database_view(
        self,
        parent_page_id: str,
        database_id: str,
        title: str,
    ):
        """Embed a linked database view in a page."""
        # Notion API uses a "linked database" block (child_database reference)
        # We append a heading + the linked DB block
        blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                },
            },
            {
                "object": "block",
                "type": "link_to_page",
                "link_to_page": {"type": "database_id", "database_id": database_id},
            },
        ]
        self.append_blocks(parent_page_id, blocks)

    # ── Search ─────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """Search across the workspace."""
        result = self._retry(self.client.search, query=query)
        return result.get("results", [])

    # ── Block Helpers ──────────────────────────────────────────────────

    @staticmethod
    def heading_block(text: str, level: int = 1) -> dict:
        """Create a heading block (level 1, 2, or 3)."""
        key = f"heading_{level}"
        return {
            "object": "block",
            "type": key,
            key: {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    @staticmethod
    def paragraph_block(text: str) -> dict:
        """Create a paragraph block."""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            },
        }

    @staticmethod
    def callout_block(text: str, emoji: str = "💡") -> dict:
        """Create a callout block."""
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "icon": {"type": "emoji", "emoji": emoji},
            },
        }

    @staticmethod
    def divider_block() -> dict:
        return {"object": "block", "type": "divider", "divider": {}}

    @staticmethod
    def bulleted_list_block(text: str) -> dict:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            },
        }

    @staticmethod
    def toggle_block(text: str, children: list[dict] | None = None) -> dict:
        block = {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
            },
        }
        if children:
            block["toggle"]["children"] = children
        return block

    # ── Property Value Helpers ─────────────────────────────────────────

    @staticmethod
    def title_property(text: str) -> dict:
        return {"title": [{"text": {"content": text}}]}

    @staticmethod
    def rich_text_property(text: str) -> dict:
        return {"rich_text": [{"text": {"content": text}}]}

    @staticmethod
    def select_property(name: str) -> dict:
        return {"select": {"name": name}}

    @staticmethod
    def multi_select_property(names: list[str]) -> dict:
        return {"multi_select": [{"name": n} for n in names]}

    @staticmethod
    def date_property(start: str, end: str | None = None) -> dict:
        val: dict[str, Any] = {"start": start}
        if end:
            val["end"] = end
        return {"date": val}

    @staticmethod
    def checkbox_property(checked: bool) -> dict:
        return {"checkbox": checked}

    @staticmethod
    def number_property(value: float) -> dict:
        return {"number": value}

    @staticmethod
    def url_property(url: str) -> dict:
        return {"url": url}

    @staticmethod
    def relation_property(page_ids: list[str]) -> dict:
        return {"relation": [{"id": pid} for pid in page_ids]}

    @staticmethod
    def status_property(name: str) -> dict:
        return {"status": {"name": name}}


notion_service = NotionService()
