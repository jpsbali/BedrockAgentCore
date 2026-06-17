"""KYC Mortgage Application CLI — Rich TUI orchestrator."""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import boto3
from botocore.config import Config
from rich.columns import Columns
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.text import Text

console = Console()

TERRAFORM_DIR = Path(__file__).parent.parent / "terraform"


def get_terraform_outputs() -> dict:
    """Fetch agent ARNs from terraform outputs."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs = json.loads(result.stdout)
        return {k: v["value"] for k, v in outputs.items()}
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as e:
        console.print(
            f"[yellow]Warning: Could not read terraform outputs: {e}[/yellow]"
        )
        return {}


def get_config() -> dict:
    """Get agent ARNs from terraform outputs or environment."""
    tf = get_terraform_outputs()
    return {
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "doc_extraction_arn": os.getenv(
            "DOC_EXTRACTION_AGENT_ARN", tf.get("doc_extraction_agent_runtime_arn", "")
        ),
        "kyc_arn": os.getenv("KYC_AGENT_ARN", tf.get("kyc_agent_runtime_arn", "")),
        "property_arn": os.getenv(
            "PROPERTY_RESEARCH_AGENT_ARN",
            tf.get("property_research_agent_runtime_arn", ""),
        ),
        "consolidation_arn": os.getenv(
            "CONSOLIDATION_AGENT_ARN", tf.get("consolidation_agent_runtime_arn", "")
        ),
    }


def invoke_agent(
    client, arn: str, payload: dict, runtime_user_id: str = None, session_id: str = None
) -> tuple[dict, str]:
    """Invoke agent and return (result, session_id)."""
    kwargs = dict(
        agentRuntimeArn=arn, qualifier="DEFAULT", payload=json.dumps(payload).encode()
    )
    if runtime_user_id:
        kwargs["runtimeUserId"] = runtime_user_id
    if session_id:
        kwargs["runtimeSessionId"] = session_id
    response = client.invoke_agent_runtime(**kwargs)
    sid = response.get("runtimeSessionId", "")
    return json.loads(response["response"].read()), sid


def poll_property_research(
    client, arn: str, task_id, session_id: str, timeout: int = 300
) -> dict:
    """Poll property research agent until complete or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            result, _ = invoke_agent(
                client, arn, {"task_id": str(task_id)}, session_id=session_id
            )
        except Exception:
            try:
                result, _ = invoke_agent(client, arn, {"task_id": str(task_id)})
            except Exception:
                time.sleep(10)
                continue
        if result.get("status") != "BUSY":
            return result
        time.sleep(10)
    return {"status": "timeout", "error": "Property research timed out"}


def save_artifacts(property_result: dict) -> list[str]:
    """Save replay GIF and code snippets from property research."""
    run_dir = Path.cwd() / "artifacts" / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    replay = property_result.get("replay_gif", "")
    if replay and os.path.exists(replay):
        import shutil

        dest = run_dir / "property_replay.gif"
        shutil.copy2(replay, dest)
        saved.append(str(dest))
    elif replay and replay.startswith("s3://"):
        parts = replay.replace("s3://", "").split("/", 1)
        dest = run_dir / "property_replay.gif"
        boto3.client("s3").download_file(parts[0], parts[1], str(dest))
        saved.append(str(dest))

    code_snippets = property_result.get("code_snippets", [])
    if code_snippets:
        dest = run_dir / "property_research_code.py"
        dest.write_text("\n\n# " + "=" * 50 + "\n\n".join(code_snippets))
        saved.append(str(dest))

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="KYC Mortgage Application Analysis",
        epilog="Example: python cli.py ../typst_templates/sample_documents.pdf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf", type=Path, help="Path to the mortgage application PDF")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not pdf_path.exists():
        console.print(f"[red]Error: File not found: {pdf_path}[/red]")
        raise SystemExit(1)

    config = get_config()
    missing = [k for k, v in config.items() if k != "region" and not v]
    if missing:
        console.print(f"[red]Error: Missing agent ARNs: {missing}[/red]")
        console.print("Ensure terraform is deployed or set environment variables.")
        sys.exit(1)

    client = boto3.client(
        "bedrock-agentcore",
        region_name=config["region"],
        config=Config(read_timeout=300),
    )
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode()

    console.print(
        Panel(
            f"[bold]KYC Mortgage Application Analysis[/bold]\nPDF: {pdf_path.name}",
            border_style="blue",
        )
    )
    console.print()

    # Step 1: Document Extraction
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as progress:
        task = progress.add_task(
            ":page_facing_up: Extracting documents from PDF...", total=None
        )
        doc_result, _ = invoke_agent(
            client, config["doc_extraction_arn"], {"pdf": pdf_b64}
        )
        progress.remove_task(task)

    extractions = doc_result.get("extractions", [])
    doc_summary = "\n\n".join(
        f"**{e['document_type']}**: ```json\n{json.dumps(e.get('extracted_data', {}), indent=2)}\n```"
        for e in extractions
        if e.get("extracted_data")
    )
    doc_renderables = []
    for e in extractions:
        if not e.get("extracted_data"):
            continue
        doc_renderables.append(Text(e["document_type"], style="bold"))
        doc_renderables.append(
            Syntax(
                json.dumps(e["extracted_data"], indent=2),
                "json",
                theme="ansi_dark",
                background_color="default",
            )
        )
    console.print(
        Panel(
            Group(*doc_renderables),
            title=":page_facing_up: Document Extraction",
            border_style="green",
        )
    )
    console.print()

    # Extract applicant info
    applicant_name = ""
    property_address = ""
    for e in extractions:
        data = e.get("extracted_data", {})
        if e.get("document_type") == "DriverLicense":
            applicant_name = data.get("name", "")
        if e.get("document_type") == "MortgageApplication":
            property_address = data.get("property_address", "")
    if not applicant_name:
        for e in extractions:
            data = e.get("extracted_data", {})
            if "employee_name" in data:
                applicant_name = data["employee_name"]
                break
    if not property_address:
        property_address = "2928 Coast Line Ct, Las Vegas, NV 89117"

    console.print(
        f"[dim]Applicant: {applicant_name} | Property: {property_address}[/dim]\n"
    )

    # Step 2: Parallel research
    kyc_result = {}
    property_result = {}

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as progress:
        kyc_task = progress.add_task(":mag: KYC Research...", total=None)
        prop_task = progress.add_task(":house: Property Research...", total=None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    invoke_agent,
                    client,
                    config["kyc_arn"],
                    {"input": f"Research applicant: {applicant_name}"},
                    "workshop-user",
                ): "kyc",
                executor.submit(
                    invoke_agent,
                    client,
                    config["property_arn"],
                    {"address": property_address},
                ): "property",
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result, session_id = future.result()
                    if name == "kyc":
                        kyc_result = result
                        progress.remove_task(kyc_task)
                    else:
                        # Start property research
                        task_id = result.get("task_id")
                        if task_id and result.get("status") == "BUSY":
                            region = config["region"]
                            progress.console.print(
                                f"   [dim]:globe_with_meridians: View live browser session: https://{region}.console.aws.amazon.com/bedrock-agentcore/browser/aws.browser.v1#[/dim]"
                            )
                            progress.update(
                                prop_task,
                                description=":house: Property Research (browser navigating)...",
                            )
                            property_result = poll_property_research(
                                client, config["property_arn"], task_id, session_id
                            )
                        else:
                            property_result = result
                        progress.remove_task(prop_task)
                except Exception as ex:
                    if name == "kyc":
                        kyc_result = {"error": str(ex)}
                        progress.remove_task(kyc_task)
                    else:
                        property_result = {"error": str(ex)}
                        progress.remove_task(prop_task)

    # Display KYC results
    kyc_text = str(kyc_result.get("result", json.dumps(kyc_result, indent=2)))
    console.print(
        Panel(Markdown(kyc_text), title=":mag: KYC Research", border_style="green")
    )
    console.print()

    # Display Property results
    prop_info = property_result.get("property_info", property_result)
    prop_text = f"```json\n{json.dumps(prop_info, indent=2)}\n```"
    console.print(
        Panel(
            Markdown(prop_text), title=":house: Property Research", border_style="green"
        )
    )
    console.print()

    # Step 3: Consolidation
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as progress:
        task = progress.add_task(":clipboard: Generating recommendation...", total=None)
        consolidation_result, _ = invoke_agent(
            client,
            config["consolidation_arn"],
            {
                "kyc_data": json.dumps(kyc_result),
                "doc_data": doc_summary,
                "property_data": json.dumps(prop_info),
            },
            runtime_user_id="workshop-user",
        )
        progress.remove_task(task)

    analysis = consolidation_result.get("analysis", str(consolidation_result))
    console.print(
        Panel(
            Markdown(analysis),
            title=":clipboard: Recommendation",
            border_style="bold green",
        )
    )
    console.print()

    # Save artifacts
    artifacts = save_artifacts(property_result)
    if artifacts:
        console.print("[bold]:file_folder: Artifacts saved:[/bold]")
        for path in artifacts:
            console.print(f"   → {path}")
        console.print()

    console.print("[bold green]:heavy_check_mark: KYC analysis complete.[/bold green]")

    region = config["region"]
    console.print(
        f"\n[bold]:bar_chart: Observability:[/bold] https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#/gen-ai-observability/agent-core/agents?tabId=sessions"
    )


if __name__ == "__main__":
    main()
