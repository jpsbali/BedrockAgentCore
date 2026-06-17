"""Test Module 1: Consolidation Agent — local uvicorn or remote AgentCore."""

import json
import sys
import time
import httpx

sys.path.insert(0, ".")
from tests.helpers import (
    console, get_mode, get_terraform_outputs, get_agentcore_client,
    invoke_agent, start_local_server, print_header, print_input,
    print_result, print_error, print_assertions_table,
)

SAMPLE_INPUT = {
    "kyc_data": json.dumps({
        "applicant_name": "William Mcgee",
        "credit_score": 742,
        "annual_income": 95000,
        "employer": "Desert Sun Electric",
        "employer_address": "3100 W Sahara Ave, Las Vegas, NV 89102",
        "debt_to_income": 0.28,
        "liens": [],
    }),
    "doc_data": json.dumps({
        "id_verified": True,
        "name_on_id": "William J Mcgee",
        "w2_income": 94850,
        "employer_on_w2": "Desert Sun Electric LLC",
    }),
    "property_data": json.dumps({
        "address": "2928 Coast Line Ct, Las Vegas, NV 89117",
        "assessed_value": 385000,
        "owner_on_deed": "Sunrise Holdings LLC",
        "annual_taxes": 4200,
        "year_built": 2004,
    }),
}


def test_local():
    """Test against local uvicorn server."""
    proc = start_local_server("agent_code/consolidation_agent", "consolidation_agent")
    try:
        time.sleep(2)
        print_input(SAMPLE_INPUT)
        with console.status("[bold]Invoking consolidation agent (local)..."):
            resp = httpx.post(
                "http://localhost:8080/invocations",
                json=SAMPLE_INPUT,
                timeout=120.0,
            )
        result = resp.json()
        return result
    finally:
        proc.terminate()
        proc.wait()


def test_remote():
    """Test against deployed AgentCore runtime."""
    outputs = get_terraform_outputs()
    arn = outputs.get("consolidation_agent_arn")
    if not arn:
        print_error("consolidation_agent_arn not found in terraform outputs")
        return None
    client = get_agentcore_client()
    print_input(SAMPLE_INPUT)
    with console.status("[bold]Invoking consolidation agent (remote, may cold-start ~60s)..."):
        result, _ = invoke_agent(client, arn, SAMPLE_INPUT)
    return result


def run_assertions(result: dict) -> list[tuple[str, bool, str]]:
    checks = []
    analysis = result.get("analysis", "")
    checks.append(("Response has analysis", bool(analysis), f"{len(analysis)} chars"))
    checks.append(("Contains recommendation", any(w in analysis.lower() for w in ["approve", "deny", "conditional"]), ""))
    checks.append(("Contains distance check", "mile" in analysis.lower() or "distance" in analysis.lower(), ""))
    checks.append(("Contains risk assessment", "risk" in analysis.lower(), ""))
    checks.append(("Mentions applicant name", "mcgee" in analysis.lower(), ""))
    return checks


def main():
    mode = get_mode()
    print_header("Module 1: Consolidation Agent", mode)

    result = test_remote() if mode == "remote" else test_local()
    if not result:
        sys.exit(1)

    print_result(result.get("analysis", str(result)), "Consolidation Analysis")
    assertions = run_assertions(result)
    print_assertions_table(assertions)

    if not all(p for _, p, _ in assertions):
        sys.exit(1)


if __name__ == "__main__":
    main()
