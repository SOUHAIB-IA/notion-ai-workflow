import json
import logging
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class NotionMCPClient:
    """Connects to the Notion MCP server via stdio transport.

    Exposes high-level methods that map to MCP tools for Notion operations.
    All Notion operations go through the MCP protocol instead of direct API calls.
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
            args=["-y", "@notionhq/notion-mcp-server"],
            env={
                **os.environ,
                "OPENAPI_MCP_HEADERS": json.dumps({
                    "Authorization": f"Bearer {notion_api_key}",
                    "Notion-Version": "2022-06-28",
                }),
            },
        )

        logger.info("Starting Notion MCP server...")
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
            f"Connected to Notion MCP. {len(self.available_tools)} tools available: "
            f"{sorted(self._tool_names)}"
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
        """Call an MCP tool by name with given arguments.

        Args:
            tool_name: The MCP tool name to invoke.
            arguments: Dict of arguments for the tool.

        Returns:
            Parsed JSON response from the tool, or {"text": raw_text} if not JSON.
        """
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.debug(f"Calling MCP tool: {tool_name} with args: {json.dumps(arguments, default=str)[:200]}")

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
    # These wrap the MCP tools with a clean Python interface.
    # Tool names are discovered at connect() time; these use the standard
    # @notionhq/notion-mcp-server naming convention.

    async def search(self, query: str) -> dict:
        """Search the Notion workspace."""
        return await self.call_tool("notion_search", {
            "query": query,
        })

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict,
    ) -> dict:
        """Create a new database under a parent page.

        Args:
            parent_page_id: The parent page ID.
            title: Database title.
            properties: Notion API properties schema dict.

        Returns:
            Created database response with "id" field.
        """
        return await self.call_tool("notion_create_database", {
            "parent_page_id": parent_page_id,
            "title": title,
            "properties": properties,
        })

    async def query_database(
        self,
        database_id: str,
        filter: dict | None = None,
        sorts: list | None = None,
    ) -> dict:
        """Query a database with optional filter and sorts."""
        args: dict = {"database_id": database_id}
        if filter:
            args["filter"] = filter
        if sorts:
            args["sorts"] = sorts
        return await self.call_tool("notion_query_database", args)

    async def update_database(self, database_id: str, properties: dict) -> dict:
        """Update a database schema (e.g., add new columns)."""
        return await self.call_tool("notion_update_database", {
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

        Args:
            parent_id: Database ID or page ID.
            properties: Notion-formatted property values.
            children: Optional list of content blocks.
            is_database_child: If True, parent is a database. If False, parent is a page.

        Returns:
            Created page response with "id" field.
        """
        args: dict = {"properties": properties}
        if is_database_child:
            args["database_id"] = parent_id
        else:
            args["parent_page_id"] = parent_id
        if children:
            args["children"] = children
        return await self.call_tool("notion_create_page", args)

    async def get_page(self, page_id: str) -> dict:
        """Retrieve a page by ID."""
        return await self.call_tool("notion_retrieve_page", {
            "page_id": page_id,
        })

    async def update_page(self, page_id: str, properties: dict) -> dict:
        """Update page properties."""
        return await self.call_tool("notion_update_page", {
            "page_id": page_id,
            "properties": properties,
        })

    async def append_blocks(self, page_id: str, children: list) -> dict:
        """Append content blocks to a page."""
        return await self.call_tool("notion_append_block_children", {
            "block_id": page_id,
            "children": children,
        })


# Singleton — initialized once, shared across the app
notion_mcp = NotionMCPClient()
