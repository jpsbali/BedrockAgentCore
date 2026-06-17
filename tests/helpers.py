"""Shared test utilities for workshop module tests."""

import json
import os
import subprocess
import sys
import time

import boto3
from botocore.config import Config
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

# --- Mode detection ---


def get_mode() -> str:
    """Return 'remote' if terraform outputs exist, else 'local'."""
    if os.environ.get("TEST_MODE", "").lower() == "local":
        return "local"
    if os.environ.get("TEST_MODE", "").lower() == "remote":
        return "remote"
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True,
            text=True,
            cwd=_terraform_dir(),
        )
        if result.returncode == 0 and json.loads(result.stdout):
            return "remote"
    except Exception:
        pass
    return "local"


def _terraform_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "terraform")


def get_terraform_outputs() -> dict:
    """Parse terraform outputs into a flat dict."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True,
        text=True,
        cwd=_terraform_dir(),
    )
    raw = json.loads(result.stdout)
    return {k: v["value"] for k, v in raw.items()}


# --- Agent invocation ---


def get_agentcore_client():
    region = os.environ.get(
        "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
    return boto3.client(
        "bedrock-agentcore", region_name=region, config=Config(read_timeout=300)
    )


def invoke_agent(
    client, arn: str, payload: dict, runtime_user_id: str = None, session_id: str = None
) -> tuple[dict, str]:
    kwargs = dict(
        agentRuntimeArn=arn, qualifier="DEFAULT", payload=json.dumps(payload).encode()
    )
    if runtime_user_id:
        kwargs["runtimeUserId"] = runtime_user_id
    if session_id:
        kwargs["runtimeSessionId"] = session_id
    resp = client.invoke_agent_runtime(**kwargs)
    return json.loads(resp["response"].read()), resp.get("runtimeSessionId", "")


# --- Local server management ---


def start_local_server(
    module_dir: str, module_name: str, port: int = 8080
) -> subprocess.Popen:
    """Start a local uvicorn/agent server and wait for it to be ready."""
    env = {
        **os.environ,
        "MODEL_ID": os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-6"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", module_name],
        cwd=module_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)  # Wait for startup
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode()
        raise RuntimeError(f"Server failed to start: {stderr}")
    return proc


# --- TUI helpers ---


def print_header(title: str, mode: str):
    console.print(
        Panel(f"[bold]{title}[/bold]\nMode: [cyan]{mode}[/cyan]", border_style="blue")
    )


def print_input(payload: dict):
    console.print(
        Panel(
            json.dumps(payload, indent=2),
            title=":arrow_right: Input",
            border_style="dim",
        )
    )


def print_result(result: dict | str, title: str = "Result"):
    if isinstance(result, str):
        console.print(
            Panel(
                Markdown(result),
                title=f":white_check_mark: {title}",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                json.dumps(result, indent=2, default=str),
                title=f":white_check_mark: {title}",
                border_style="green",
            )
        )


def print_error(msg: str):
    console.print(Panel(f"[red]{msg}[/red]", title=":x: Error", border_style="red"))


def print_assertion(name: str, passed: bool, detail: str = ""):
    icon = ":white_check_mark:" if passed else ":x:"
    color = "green" if passed else "red"
    line = f"{icon} [{color}]{name}[/{color}]"
    if detail:
        line += f" [dim]({detail})[/dim]"
    console.print(line)


def print_assertions_table(assertions: list[tuple[str, bool, str]]):
    table = Table(title="Assertions", show_lines=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")
    for name, passed, detail in assertions:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(name, status, detail)
    console.print(table)
    total = len(assertions)
    passed = sum(1 for _, p, _ in assertions if p)
    color = "green" if passed == total else "red"
    console.print(f"\n[{color}]{passed}/{total} checks passed[/{color}]")
