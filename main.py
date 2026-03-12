import asyncio
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler("founderos.log"), logging.StreamHandler()],
)
logger = logging.getLogger("founderos")
console = Console()


def print_banner():
    banner = Text()
    banner.append("🚀 FounderOS", style="bold cyan")
    banner.append(" — AI Startup Operating System\n", style="dim")
    banner.append("   Powered by Notion MCP\n\n", style="dim italic")
    banner.append("Commands:\n", style="bold")
    banner.append("  new     ", style="bold green")
    banner.append("— Create a new project workspace\n")
    banner.append("  update  ", style="bold yellow")
    banner.append("— Update existing workspace\n")
    banner.append("  status  ", style="bold blue")
    banner.append("— Show current workspace summary\n")
    banner.append("  sprint  ", style="bold white")
    banner.append("— Plan 2-week sprints from tasks\n")
    banner.append("  plan    ", style="bold magenta")
    banner.append("— Re-plan or adjust priorities\n")
    banner.append("  quit    ", style="bold red")
    banner.append("— Exit")
    console.print(Panel(banner, border_style="cyan"))


def status_callback(emoji: str, message: str):
    console.print(f"  {emoji} {message}")


async def cmd_new(orchestrator):
    idea = Prompt.ask("\n[bold cyan]Describe your startup idea[/bold cyan]")
    if not idea.strip():
        console.print("[red]Please provide a description.[/red]")
        return

    console.print()
    try:
        config = await orchestrator.create_workspace(idea, on_status=status_callback)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to create workspace")
        return

    console.print(
        Panel(
            f"[bold green]Workspace created![/bold green]\n"
            f"Project: {config.project_name}\n"
            f"Features: {len(config.feature_page_ids)}\n"
            f"Root page ID: {config.root_page_id}",
            title="Success",
            border_style="green",
        )
    )


async def cmd_update(orchestrator):
    update_req = Prompt.ask("\n[bold yellow]What would you like to update?[/bold yellow]")
    if not update_req.strip():
        console.print("[red]Please describe the update.[/red]")
        return

    console.print()
    try:
        config = await orchestrator.update_workspace(update_req, on_status=status_callback)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to update workspace")
        return

    if config:
        console.print(
            Panel(
                f"[bold green]Workspace updated![/bold green]\n"
                f"Project: {config.project_name}\n"
                f"Total features: {len(config.feature_page_ids)}",
                title="Success",
                border_style="green",
            )
        )


async def cmd_status(orchestrator):
    status = orchestrator.get_status()
    if not status:
        console.print("[yellow]No workspace found. Use 'new' to create one.[/yellow]")
        return

    table = Table(title=f"📊 {status['project_name']}", border_style="blue")
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_row("Features", str(status["features_count"]))
    table.add_row("Feature List", ", ".join(status["feature_names"]))
    table.add_row("Sprints", str(status["sprints_count"]))
    if status["sprint_names"]:
        table.add_row("Sprint List", ", ".join(status["sprint_names"]))
    table.add_row("Root Page", status["workspace_ids"]["root_page"])
    table.add_row("Features DB", status["workspace_ids"]["features_db"])
    table.add_row("Tasks DB", status["workspace_ids"]["tasks_db"])
    table.add_row("Sprints DB", status["workspace_ids"]["sprints_db"])
    table.add_row("Docs DB", status["workspace_ids"]["docs_db"])
    table.add_row("Dashboard", status["workspace_ids"]["dashboard"])
    console.print(table)


async def cmd_plan(orchestrator):
    plan_req = Prompt.ask(
        "\n[bold magenta]What changes to the plan?[/bold magenta] "
        "(e.g., 'reprioritize auth to P0' or 'add mobile app support')"
    )
    if not plan_req.strip():
        console.print("[red]Please describe the plan change.[/red]")
        return

    console.print()
    try:
        config = await orchestrator.update_workspace(plan_req, on_status=status_callback)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to update plan")
        return

    if config:
        console.print("[bold green]Plan updated successfully.[/bold green]")


async def cmd_sprint(orchestrator):
    console.print(
        "\n[bold white]🏃 Sprint Planning[/bold white] — "
        "AI will analyze all tasks and organize them into 2-week sprints."
    )
    console.print()
    try:
        config = await orchestrator.plan_sprints(on_status=status_callback)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to plan sprints")
        return

    if config and config.sprint_page_ids:
        table = Table(title="🏃 Sprint Plan", border_style="white")
        table.add_column("Sprint", style="bold")
        table.add_column("Tasks", justify="right")
        for name in config.sprint_page_ids:
            table.add_row(name, "—")
        console.print(table)
        console.print(
            Panel(
                f"[bold green]Sprints created![/bold green]\n"
                f"Total sprints: {len(config.sprint_page_ids)}\n"
                f"Sprint 1 set to [bold]Active[/bold]",
                title="Success",
                border_style="green",
            )
        )


COMMANDS = {
    "new": cmd_new,
    "update": cmd_update,
    "status": cmd_status,
    "sprint": cmd_sprint,
    "plan": cmd_plan,
}


async def main():
    print_banner()

    # Initialize MCP connection
    from mcp_client.notion_mcp import notion_mcp
    console.print("[dim]Connecting to Notion MCP server...[/dim]")
    try:
        await notion_mcp.connect()
    except Exception as e:
        console.print(f"[bold red]Failed to connect to Notion MCP:[/bold red] {e}")
        console.print("[dim]Make sure Node.js/npx is installed and NOTION_API_KEY is set.[/dim]")
        sys.exit(1)

    console.print(f"[green]Connected to Notion MCP ({len(notion_mcp.available_tools)} tools available)[/green]\n")

    # Log discovered tool names for debugging
    logger.info(f"MCP tools: {notion_mcp.list_tool_names()}")

    from agents.orchestrator import Orchestrator
    orchestrator = Orchestrator(notion_mcp)

    try:
        while True:
            try:
                command = Prompt.ask("\n[bold]>>>[/bold]").strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if command in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            handler = COMMANDS.get(command)
            if handler:
                await handler(orchestrator)
            else:
                console.print(
                    f"[red]Unknown command:[/red] {command}. "
                    f"Try: {', '.join(COMMANDS.keys())}, quit"
                )
    finally:
        await notion_mcp.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
