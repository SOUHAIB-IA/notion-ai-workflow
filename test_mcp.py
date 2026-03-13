"""Test which block types work with the MCP server."""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()


async def test():
    from mcp_client.notion_mcp import NotionMCPClient

    client = NotionMCPClient()
    root_page_id = os.getenv("NOTION_ROOT_PAGE_ID")

    await client.connect()

    # Create test page
    page = await client.create_page(
        parent_id=root_page_id,
        properties={"title": [{"text": {"content": "Block Type Test"}}]},
        is_database_child=False,
    )
    page_id = page["id"]
    print(f"Test page: {page_id}\n")

    # Test various block types one at a time
    block_tests = [
        ("paragraph", {"type": "paragraph", "paragraph": {
            "rich_text": [{"text": {"content": "Test paragraph"}}]
        }}),
        ("bulleted_list_item", {"type": "bulleted_list_item", "bulleted_list_item": {
            "rich_text": [{"text": {"content": "Test bullet"}}]
        }}),
        ("heading_1", {"type": "heading_1", "heading_1": {
            "rich_text": [{"text": {"content": "Heading 1"}}]
        }}),
        ("heading_2", {"type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "Heading 2"}}]
        }}),
        ("heading_3", {"type": "heading_3", "heading_3": {
            "rich_text": [{"text": {"content": "Heading 3"}}]
        }}),
        ("divider", {"type": "divider", "divider": {}}),
        ("callout", {"type": "callout", "callout": {
            "rich_text": [{"text": {"content": "Test callout"}}],
            "icon": {"emoji": "💡"},
        }}),
        ("link_to_page", {"type": "link_to_page", "link_to_page": {
            "type": "page_id", "page_id": page_id
        }}),
    ]

    for name, block in block_tests:
        try:
            result = await client.append_blocks(page_id, [block])
            error = result.get("object") == "error"
            if error:
                print(f"  {name}: FAIL - {result.get('message', '')[:80]}")
            else:
                print(f"  {name}: OK")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")

    # Test page creation with children blocks (callout, heading, bullets)
    print("\nTesting create_page with mixed children blocks...")
    page2 = await client.create_page(
        parent_id=root_page_id,
        properties={"title": [{"text": {"content": "Mixed Block Test"}}]},
        children=[
            {"type": "callout", "callout": {
                "rich_text": [{"text": {"content": "Description"}}],
                "icon": {"emoji": "🎯"},
            }},
            {"type": "heading_2", "heading_2": {
                "rich_text": [{"text": {"content": "Tech Stack"}}]
            }},
            {"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": "Python"}}]
            }},
            {"type": "divider", "divider": {}},
        ],
        is_database_child=False,
    )
    if page2.get("id"):
        print("  OK - page created with mixed blocks")
    else:
        print(f"  FAIL - {page2}")

    # Test database with relation + single_property
    print("\nTesting database creation with relation (single_property)...")
    db1 = await client.create_database(
        parent_page_id=page_id,
        title="Parent DB",
        properties={"Name": {"title": {}}},
    )
    db1_id = db1["id"]
    print(f"  Parent DB: {db1_id}")

    db2 = await client.create_database(
        parent_page_id=page_id,
        title="Child DB",
        properties={
            "Name": {"title": {}},
            "Parent": {"relation": {"database_id": db1_id, "single_property": {}}},
        },
    )
    db2_id = db2.get("id", "MISSING")
    print(f"  Child DB: {db2_id}")

    await client.disconnect()
    print("\nDone! Delete 'Block Type Test' and 'Mixed Block Test' from Notion.")


if __name__ == "__main__":
    asyncio.run(test())
