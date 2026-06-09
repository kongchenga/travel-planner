"""CLI entry point for testing. Uses DirectLLM + new graph."""
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from src.graph import create_travel_graph
from src.tools.llm import DirectLLM
from src.state import AgentState

load_dotenv()
console = Console()


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]OPENAI_API_KEY not set[/red]")
        sys.exit(1)
    return DirectLLM()


def interactive_input() -> dict:
    console.print(Panel.fit("Travel Planner", border_style="cyan"))
    destination = console.input("[cyan]Destination: [/cyan]").strip()
    origin = console.input("[cyan]From: [/cyan]").strip()
    start_date = console.input("[cyan]Start date: [/cyan]").strip()
    end_date = console.input("[cyan]End date: [/cyan]").strip()
    travelers_str = console.input("[cyan]Travelers (1): [/cyan]").strip()
    travelers = int(travelers_str) if travelers_str.isdigit() else 1
    budget_str = console.input("[cyan]Budget (optional): [/cyan]").strip()
    budget = float(budget_str) if budget_str else None
    interests_str = console.input("[cyan]Interests (comma sep): [/cyan]").strip()
    interests = [i.strip() for i in interests_str.split(",") if i.strip()]
    special = console.input("[cyan]Special requirements: [/cyan]").strip()
    return {
        "destination": destination or None,
        "origin": origin or None,
        "start_date": start_date or None,
        "end_date": end_date or None,
        "travelers": travelers,
        "budget": budget,
        "currency": "CNY",
        "interests": interests if interests else ["观光"],
        "special_requirements": special or None,
    }


def run():
    llm = get_llm()
    graph = create_travel_graph(llm)
    travel_request = interactive_input()

    initial: AgentState = {
        "messages": [],
        "travel_request": travel_request,
        "destination_research": "",
        "flight_options": [],
        "hotel_options": [],
        "dining_recommendations": [],
        "budget_plan": [],
        "itinerary": [],
        "map_data": {},
        "trip_plan": {},
        "completed_agents": [],
        "errors": [],
    }

    console.print("\n[bold]Planning...[/bold]\n")
    for event in graph.stream(initial):
        for node_name, output in event.items():
            if node_name == "finalize":
                tp = output.get("trip_plan", {})
                console.print("\n")
                console.print(Markdown(f"# Plan for {tp.get('destination','')}"))
                console.print(f"Days: {len(tp.get('days',[]))}")
                console.print(f"Hotels: {len(tp.get('hotels',[]))}")
                console.print(f"Restaurants: {len(tp.get('dining',[]))}")

    console.print("\n[bold green]Done![/bold green]")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        console.print("\nCancelled")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
