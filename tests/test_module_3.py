"""Test Module 3: Research Agents — doc extraction, KYC, property research.

Usage:
    python tests/test_module_3.py              # Test all agents
    python tests/test_module_3.py doc          # Test doc extraction only
    python tests/test_module_3.py kyc          # Test KYC research only
    python tests/test_module_3.py property     # Test property research only
"""

import base64
import json
import sys
import time

sys.path.insert(0, ".")
from tests.helpers import (
    console,
    get_agentcore_client,
    get_mode,
    get_terraform_outputs,
    invoke_agent,
    print_assertions_table,
    print_error,
    print_header,
    print_input,
    print_result,
    start_local_server,
)

PDF_PATH = "sample_data/input/sample_documents.pdf"
VALID_AGENTS = {"doc", "kyc", "property"}


def load_pdf_b64() -> str:
    with open(PDF_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode()


# --- Doc Extraction ---


def test_doc_extraction_local():
    proc = start_local_server("agent_code/doc_extraction_agent", "doc_extraction_agent")
    try:
        import httpx

        time.sleep(3)
        payload = {"pdf_b64": load_pdf_b64()}
        with console.status("[bold]Doc extraction (local, ~30s)..."):
            resp = httpx.post(
                "http://localhost:8080/invocations", json=payload, timeout=120.0
            )
        return resp.json()
    finally:
        proc.terminate()
        proc.wait()


def test_doc_extraction_remote(client, arn: str):
    payload = {"pdf_b64": load_pdf_b64()}
    with console.status("[bold]Doc extraction (remote, may cold-start)..."):
        result, _ = invoke_agent(client, arn, payload)
    return result


# --- KYC Research ---


def test_kyc_local():
    mcp_proc = start_local_server("agent_code/kyc_tools", "mcp_server", port=8000)
    proc = start_local_server("agent_code/kyc_agent", "kyc_agent")
    try:
        import httpx

        time.sleep(3)
        payload = {"input": "Research applicant William Mcgee"}
        with console.status("[bold]KYC research (local, ~30s)..."):
            resp = httpx.post(
                "http://localhost:8080/invocations", json=payload, timeout=120.0
            )
        return resp.json()
    finally:
        proc.terminate()
        proc.wait()
        mcp_proc.terminate()
        mcp_proc.wait()


def test_kyc_remote(client, arn: str):
    payload = {"input": "Research applicant William Mcgee"}
    with console.status("[bold]KYC research (remote, may cold-start)..."):
        result, _ = invoke_agent(client, arn, payload, runtime_user_id="workshop-user")
    return result


# --- Property Research ---


def test_property_local():
    proc = start_local_server(
        "agent_code/property_research_agent", "property_research_agent"
    )
    try:
        import httpx

        time.sleep(3)
        payload = {"address": "2928 Coast Line Ct, Las Vegas, NV 89117"}
        with console.status("[bold]Property research (local, ~60s)..."):
            resp = httpx.post(
                "http://localhost:8080/invocations", json=payload, timeout=180.0
            )
        result = resp.json()
        # Handle async pattern locally too
        if result.get("status") == "BUSY":
            task_id = result.get("task_id")
            console.print(f"[dim]Task {task_id} started, polling...[/dim]")
            for _ in range(30):
                time.sleep(10)
                resp = httpx.post(
                    "http://localhost:8080/invocations",
                    json={"task_id": task_id},
                    timeout=60.0,
                )
                result = resp.json()
                if result.get("status") != "BUSY":
                    break
        return result
    finally:
        proc.terminate()
        proc.wait()


def test_property_remote(client, arn: str):
    payload = {"address": "2928 Coast Line Ct, Las Vegas, NV 89117"}
    with console.status("[bold]Property research (remote, async polling)..."):
        result, session_id = invoke_agent(client, arn, payload)
    if result.get("status") == "BUSY":
        task_id = result.get("task_id")
        console.print(f"[dim]Task {task_id} started, polling...[/dim]")
        for _ in range(30):
            time.sleep(10)
            result, _ = invoke_agent(
                client, arn, {"task_id": task_id}, session_id=session_id
            )
            if result.get("status") != "BUSY":
                break
    return result


# --- Assertions ---


def run_assertions(doc_result, kyc_result, prop_result) -> list[tuple[str, bool, str]]:
    checks = []

    if doc_result:
        text = json.dumps(doc_result).lower()
        checks.append(("Doc extraction returned data", bool(doc_result), ""))
        checks.append(
            (
                "Contains mortgage application",
                "mortgageapplication" in text or "mortgage" in text,
                "",
            )
        )
        checks.append(
            ("Contains W2 or paystub data", "w2" in text or "pay" in text, "")
        )

    if kyc_result:
        kyc_text = json.dumps(kyc_result).lower()
        checks.append(("KYC returned data", bool(kyc_result), ""))
        checks.append(
            ("KYC mentions applicant", "mcgee" in kyc_text or "william" in kyc_text, "")
        )
        checks.append(
            ("KYC has credit info", "credit" in kyc_text or "score" in kyc_text, "")
        )

    if prop_result:
        prop_text = json.dumps(prop_result).lower()
        checks.append(("Property research returned", bool(prop_result), ""))
        checks.append(
            (
                "Property has address data",
                "coast" in prop_text or "vegas" in prop_text,
                "",
            )
        )

    return checks


def main():
    mode = get_mode()

    # Parse optional agent filter
    agents_to_test = VALID_AGENTS
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg not in VALID_AGENTS:
            print_error(
                f"Unknown agent: {arg}. Valid options: {', '.join(sorted(VALID_AGENTS))}"
            )
            sys.exit(1)
        agents_to_test = {arg}

    print_header(
        f"Module 3: Research Agents ({', '.join(sorted(agents_to_test))})", mode
    )

    doc_result = kyc_result = prop_result = None

    if mode == "remote":
        outputs = get_terraform_outputs()
        client = get_agentcore_client()

        if "doc" in agents_to_test:
            arn = outputs.get("doc_extraction_agent_arn")
            if arn:
                doc_result = test_doc_extraction_remote(client, arn)
                print_result(doc_result, "Doc Extraction")
            else:
                print_error("doc_extraction_agent_arn not in terraform outputs")

        if "kyc" in agents_to_test:
            arn = outputs.get("kyc_agent_arn")
            if arn:
                kyc_result = test_kyc_remote(client, arn)
                print_result(kyc_result, "KYC Research")
            else:
                print_error("kyc_agent_arn not in terraform outputs")

        if "property" in agents_to_test:
            arn = outputs.get("property_research_agent_arn")
            if arn:
                prop_result = test_property_remote(client, arn)
                print_result(prop_result, "Property Research")
            else:
                print_error("property_research_agent_arn not in terraform outputs")
    else:
        if "doc" in agents_to_test:
            doc_result = test_doc_extraction_local()
            print_result(doc_result, "Doc Extraction")

        if "kyc" in agents_to_test:
            kyc_result = test_kyc_local()
            print_result(kyc_result, "KYC Research")

        if "property" in agents_to_test:
            prop_result = test_property_local()
            print_result(prop_result, "Property Research")

    assertions = run_assertions(doc_result, kyc_result, prop_result)
    print_assertions_table(assertions)

    if not all(p for _, p, _ in assertions):
        sys.exit(1)


if __name__ == "__main__":
    main()
