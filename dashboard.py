"""
Live terminal dashboard — shows store metrics updating in real time.
Run: py -3.11 dashboard.py
Requires: pip install rich requests
"""
import time, requests
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
from rich import box

API_BASE   = "http://localhost:8000"
STORE_ID   = "store_1076"
REFRESH_HZ = 2  # seconds between updates

console = Console()

def fetch(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=3)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def build_dashboard():
    metrics   = fetch(f"/stores/{STORE_ID}/metrics")
    funnel    = fetch(f"/stores/{STORE_ID}/funnel")
    heatmap   = fetch(f"/stores/{STORE_ID}/heatmap")
    anomalies = fetch(f"/stores/{STORE_ID}/anomalies")
    health    = fetch("/health")

    # ── Metrics panel ─────────────────────────────────────────────────
    metrics_table = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value",  style="green bold")

    if "error" not in metrics:
        metrics_table.add_row("Unique Visitors",   str(metrics.get("unique_visitors", 0)))
        metrics_table.add_row("Conversion Rate",   f"{metrics.get('conversion_rate', 0)*100:.1f}%")
        metrics_table.add_row("Queue Depth",       str(metrics.get("queue_depth", 0)))
        metrics_table.add_row("Avg Wait (sec)",    str(metrics.get("avg_wait_seconds", 0)))
        metrics_table.add_row("Abandonment Rate",  f"{metrics.get('abandonment_rate', 0)*100:.1f}%")
    else:
        metrics_table.add_row("Error", metrics["error"])

    metrics_panel = Panel(metrics_table, title="[bold]Store Metrics[/bold]",
                          border_style="blue", width=35)

    # ── Funnel panel ──────────────────────────────────────────────────
    funnel_table = Table(box=box.SIMPLE, show_header=True, padding=(0,1))
    funnel_table.add_column("Stage",    style="cyan")
    funnel_table.add_column("Visitors", style="green bold", justify="right")
    funnel_table.add_column("Drop %",   style="red",        justify="right")

    if "funnel" in funnel:
        for stage in funnel["funnel"]:
            funnel_table.add_row(
                stage["stage"],
                str(stage["visitors"]),
                f"{stage['drop_off_pct']}%"
            )

    funnel_panel = Panel(funnel_table, title="[bold]Conversion Funnel[/bold]",
                         border_style="magenta", width=45)

    # ── Heatmap panel ─────────────────────────────────────────────────
    heatmap_table = Table(box=box.SIMPLE, show_header=True, padding=(0,1))
    heatmap_table.add_column("Zone",       style="cyan")
    heatmap_table.add_column("Visits",     style="green bold", justify="right")
    heatmap_table.add_column("Heat",       style="yellow",     justify="right")

    if "zones" in heatmap:
        for zone in sorted(heatmap["zones"], key=lambda z: z["visits"], reverse=True):
            bar = "█" * (zone["normalised"] // 10) + "░" * (10 - zone["normalised"] // 10)
            heatmap_table.add_row(
                zone.get("zone_name", zone["zone_id"])[:20],
                str(zone["visits"]),
                bar
            )

    heatmap_panel = Panel(heatmap_table, title="[bold]Zone Heatmap[/bold]",
                          border_style="yellow", width=50)

    # ── Anomalies panel ───────────────────────────────────────────────
    anomaly_table = Table(box=box.SIMPLE, show_header=True, padding=(0,1))
    anomaly_table.add_column("Type",     style="cyan")
    anomaly_table.add_column("Severity", style="bold")
    anomaly_table.add_column("Action",   style="white")

    severity_colors = {"CRITICAL": "red", "WARN": "yellow", "INFO": "blue"}

    if "anomalies" in anomalies and anomalies["anomalies"]:
        for a in anomalies["anomalies"]:
            color = severity_colors.get(a["severity"], "white")
            anomaly_table.add_row(
                a["type"],
                f"[{color}]{a['severity']}[/{color}]",
                a.get("suggested_action", "")[:40]
            )
    else:
        anomaly_table.add_row("No anomalies", "INFO", "All systems normal")

    anomaly_panel = Panel(anomaly_table, title="[bold]Anomalies[/bold]",
                          border_style="red", width=80)

    # ── Health panel ──────────────────────────────────────────────────
    status = health.get("status", "unknown")
    status_color = "green" if status == "ok" else "red"
    health_text = f"[{status_color}]● {status.upper()}[/{status_color}]"

    stores = health.get("stores", {})
    for sid, info in stores.items():
        stale = "⚠ STALE" if info.get("stale_feed") else "✓ LIVE"
        health_text += f"  |  {sid}: {stale}"

    health_panel = Panel(health_text, title="[bold]Health[/bold]",
                         border_style="green", width=80)

    # ── Combine ───────────────────────────────────────────────────────
    from rich.console import Group
    return Group(
        Panel(f"[bold cyan]Store Intelligence Dashboard[/bold cyan]  "
              f"[dim]Store: {STORE_ID}  |  Refreshing every {REFRESH_HZ}s  |  "
              f"{time.strftime('%H:%M:%S')}[/dim]",
              border_style="cyan", width=82),
        Columns([metrics_panel, funnel_panel]),
        heatmap_panel,
        anomaly_panel,
        health_panel,
    )

def main():
    console.print("[bold cyan]Starting Store Intelligence Dashboard...[/bold cyan]")
    console.print(f"Connecting to API at {API_BASE}")
    console.print("Press Ctrl+C to exit\n")

    with Live(build_dashboard(), refresh_per_second=1, screen=True) as live:
        while True:
            time.sleep(REFRESH_HZ)
            live.update(build_dashboard())

if __name__ == "__main__":
    main()