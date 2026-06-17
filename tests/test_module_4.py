"""Test Module 4: Deployment Validation — terraform outputs + agent health checks."""

import json
import sys

sys.path.insert(0, ".")
from tests.helpers import (
    console, get_terraform_outputs, get_agentcore_client,
    invoke_agent, print_header, print_error, print_assertions_table, print_result,
)

EXPECTED_OUTPUTS = [
    "consolidation_agent_arn",
    "doc_extraction_agent_arn",
    "kyc_agent_arn",
    "property_research_agent_arn",
    "kyc_tools_arn",
]


def health_check(client, arn: str, payload: dict, runtime_user_id: str = None) -> tuple[bool, str]:
    """Invoke agent with minimal payload to verify it responds."""
    try:
        result, _ = invoke_agent(client, arn, payload, runtime_user_id=runtime_user_id)
        return True, f"OK ({len(json.dumps(result))} chars)"
    except Exception as e:
        return False, str(e)[:80]


def main():
    print_header("Module 4: Deployment Validation", "remote")

    try:
        outputs = get_terraform_outputs()
    except Exception as e:
        print_error(f"Cannot read terraform outputs: {e}")
        sys.exit(1)

    print_result(outputs, "Terraform Outputs")

    checks = []

    # Check all expected outputs exist
    for key in EXPECTED_OUTPUTS:
        present = key in outputs and bool(outputs[key])
        checks.append((f"Output: {key}", present, outputs.get(key, "MISSING")[:60]))

    # Health check each agent
    client = get_agentcore_client()
    console.print("\n[bold]Running agent health checks (cold starts may take ~60s each)...[/bold]\n")

    health_tests = [
        ("consolidation_agent_arn", {"kyc_data": "{}", "doc_data": "{}", "property_data": "{}"}, None),
        ("doc_extraction_agent_arn", {"pdf_b64": "dGVzdA=="}, None),  # minimal base64
        ("kyc_agent_arn", {"input": "ping"}, "workshop-user"),
    ]

    for arn_key, payload, user_id in health_tests:
        arn = outputs.get(arn_key)
        if not arn:
            checks.append((f"Health: {arn_key}", False, "ARN missing"))
            continue
        with console.status(f"[bold]Health check: {arn_key}..."):
            ok, detail = health_check(client, arn, payload, user_id)
        checks.append((f"Health: {arn_key}", ok, detail))

    print_assertions_table(checks)

    if not all(p for _, p, _ in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
