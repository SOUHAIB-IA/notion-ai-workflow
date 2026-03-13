import json
import logging
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Pin to v1.9.1 — v2.x has a broken create-database endpoint (invalid URL).
MCP_SERVER_PACKAGE = "@notionhq/notion-mcp-server@1.9.1"


class NotionMCPClient:
    """Connects to the Notion MCP server via stdio transport.

    Exposes high-level methods that map to MCP tools for Notion operations.
    All Notion operations go through the MCP protocol instead of direct API calls.

    Uses @notionhq/notion-mcp-server v1.9.1 which provides these tools:
        API-post-page, API-create-a-database, API-post-database-query,
        API-retrieve-a-page, API-patch-page, API-patch-block-children,
        API-update-a-database, API-post-search, API-retrieve-a-database,
        API-create-a-comment, API-retrieve-a-comment, etc.
    """

    def __init__(self):
        self.session: ClientSession | None = None
        self._client_context = None
        self._session_context = None
        self.available_tools: list = []
        self._tool_names: set[str] = set()

    async def connect(self):
        """Start the Notion MCP server subprocess and connect to it."""
        notion_api_key = os.getenv("NOTION_API_KEY")
        if not notion_api_key:
            raise EnvironmentError("NOTION_API_KEY is required for MCP connection")

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", MCP_SERVER_PACKAGE],
            env={
                **os.environ,
                "OPENAPI_MCP_HEADERS": json.dumps({
                    "Authorization": f"Bearer {notion_api_key}",
                    "Notion-Version": "2022-06-28",
                }),
            },
        )

        logger.info("Starting Notion MCP server (%s)...", MCP_SERVER_PACKAGE)
        self._client_context = stdio_client(server_params)
        read_stream, write_stream = await self._client_context.__aenter__()

        self._session_context = ClientSession(read_stream, write_stream)
        self.session = await self._session_context.__aenter__()

        await self.session.initialize()

        # Discover available tools
        tools_result = await self.session.list_tools()
        self.available_tools = tools_result.tools
        self._tool_names = {t.name for t in self.available_tools}

        logger.info(
            "Connected to Notion MCP. %d tools available: %s",
            len(self.available_tools),
            sorted(self._tool_names),
        )

    async def disconnect(self):
        """Clean shutdown of MCP server connection."""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._client_context:
            await self._client_context.__aexit__(None, None, None)
        self.session = None
        logger.info("Disconnected from Notion MCP")

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool by name with given arguments."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.debug("Calling MCP tool: %s with args: %s", tool_name, json.dumps(arguments, default=str)[:500])

        result = await self.session.call_tool(tool_name, arguments)

        if result.content:
            for block in result.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return {"text": block.text}
        return {}

    def list_tool_names(self) -> list[str]:
        """Return sorted list of available MCP tool names."""
        return sorted(self._tool_names)

    def get_tool_schema(self, tool_name: str) -> dict | None:
        """Get the input schema for a specific tool."""
        for tool in self.available_tools:
            if tool.name == tool_name:
                return tool.inputSchema if hasattr(tool, "inputSchema") else None
        return None

    # ── High-Level Notion Operations ───────────────────────────────────
    # Mapped to @notionhq/notion-mcp-server v1.9.1 tool names.

    async def search(self, query: str) -> dict:
        """Search the Notion workspace."""
        return await self.call_tool("API-post-search", {
            "query": query,
        })

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict,
    ) -> dict:
        """Create a new database under a parent page.

        Uses MCP tool: API-create-a-database
        """
        return await self.call_tool("API-create-a-database", {
            "parent": {"page_id": parent_page_id},
            "title": [{"text": {"content": title}}],
            "properties": properties,
        })

    async def query_database(
        self,
        database_id: str,
        filter: dict | None = None,
        sorts: list | None = None,
    ) -> dict:
        """Query a database with optional filter and sorts.

        Uses MCP tool: API-post-database-query
        """
        args: dict = {"database_id": database_id}
        if filter:
            args["filter"] = filter
        if sorts:
            args["sorts"] = sorts
        return await self.call_tool("API-post-database-query", args)

    async def update_database(self, database_id: str, properties: dict) -> dict:
        """Update a database schema (e.g., add new columns).

        Uses MCP tool: API-update-a-database
        """
        return await self.call_tool("API-update-a-database", {
            "database_id": database_id,
            "properties": properties,
        })

    async def create_page(
        self,
        parent_id: str,
        properties: dict,
        children: list | None = None,
        is_database_child: bool = True,
    ) -> dict:
        """Create a page in a database or under a parent page.

        Uses MCP tool: API-post-page
        The parent param uses {"database_id": id} or {"page_id": id}.
        """
        if is_database_child:
            parent = {"database_id": parent_id}
        else:
            parent = {"page_id": parent_id}

        args: dict = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            args["children"] = children
        return await self.call_tool("API-post-page", args)

    async def get_page(self, page_id: str) -> dict:
        """Retrieve a page by ID.

        Uses MCP tool: API-retrieve-a-page
        """
        return await self.call_tool("API-retrieve-a-page", {
            "page_id": page_id,
        })

    async def update_page(self, page_id: str, properties: dict) -> dict:
        """Update page properties.

        Uses MCP tool: API-patch-page
        """
        return await self.call_tool("API-patch-page", {
            "page_id": page_id,
            "properties": properties,
        })

    async def append_blocks(self, page_id: str, children: list) -> dict:
        """Append content blocks to a page.

        Uses MCP tool: API-patch-block-children
        """
        return await self.call_tool("API-patch-block-children", {
            "block_id": page_id,
            "children": children,
        })


# Singleton — initialized once, shared across the app
notion_mcp = NotionMCPClient()
