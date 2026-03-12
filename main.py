import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from agents.orchestrator import orchestrator

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
    banner.append(" — AI Startup Operating System\n\n", style="dim")
    banner.append("Commands:\n", style="bold")
    banner.append("  new     ", style="bold green")
    banner.append("— Create a new project workspace\n")
    banner.append("  update  ", style="bold yellow")
    banner.append("— Update existing workspace\n")
    banner.append("  status  ", style="bold blue")
    banner.append("— Show current workspace summary\n")
    banner.append("  plan    ", style="bold magenta")
    banner.append("— Re-plan or adjust priorities\n")
    banner.append("  quit    ", style="bold red")
    banner.append("— Exit")
    console.print(Panel(banner, border_style="cyan"))


def status_callback(emoji: str, message: str):
    """Display status updates with Rich formatting."""
    console.print(f"  {emoji} {message}")


def cmd_new():
    idea = Prompt.ask("\n[bold cyan]Describe your startup idea[/bold cyan]")
    if not idea.strip():
        console.print("[red]Please provide a description.[/red]")
        return

    console.print()
    with console.status("[bold green]Working...[/bold green]", spinner="dots"):
        try:
            config = orchestrator.create_workspace(idea, on_status=status_callback)
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


def cmd_update():
    update_req = Prompt.ask("\n[bold yellow]What would you like to update?[/bold yellow]")
    if not update_req.strip():
        console.print("[red]Please describe the update.[/red]")
        return

    console.print()
    with console.status("[bold green]Working...[/bold green]", spinner="dots"):
        try:
            config = orchestrator.update_workspace(update_req, on_status=status_callback)
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


def cmd_status():
    status = orchestrator.get_status()
    if not status:
        console.print("[yellow]No workspace found. Use 'new' to create one.[/yellow]")
        return

    table = Table(title=f"📊 {status['project_name']}", border_style="blue")
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_row("Features", str(status["features_count"]))
    table.add_row("Feature List", ", ".join(status["feature_names"]))
    table.add_row("Root Page", status["workspace_ids"]["root_page"])
    table.add_row("Features DB", status["workspace_ids"]["features_db"])
    table.add_row("Tasks DB", status["workspace_ids"]["tasks_db"])
    table.add_row("Docs DB", status["workspace_ids"]["docs_db"])
    table.add_row("Dashboard", status["workspace_ids"]["dashboard"])
    console.print(table)


def cmd_plan():
    """Re-plan: essentially alias for update with planning focus."""
    plan_req = Prompt.ask(
        "\n[bold magenta]What changes to the plan?[/bold magenta] "
        "(e.g., 'reprioritize auth to P0' or 'add mobile app support')"
    )
    if not plan_req.strip():
        console.print("[red]Please describe the plan change.[/red]")
        return

    console.print()
    with console.status("[bold green]Re-planning...[/bold green]", spinner="dots"):
        try:
            config = orchestrator.update_workspace(plan_req, on_status=status_callback)
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            logger.exception("Failed to update plan")
            return

    if config:
        console.print("[bold green]Plan updated successfully.[/bold green]")


COMMANDS = {
    "new": cmd_new,
    "update": cmd_update,
    "status": cmd_status,
    "plan": cmd_plan,
}


def main():
    print_banner()

    while True:
        try:
            command = Prompt.ask("\n[bold]>>>[/bold]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            sys.exit(0)

        if command in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        handler = COMMANDS.get(command)
        if handler:
            handler()
        else:
            console.print(
                f"[red]Unknown command:[/red] {command}. "
                f"Try: {', '.join(COMMANDS.keys())}, quit"
            )


if __name__ == "__main__":
    main()
