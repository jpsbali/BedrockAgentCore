"""Test Module 2: MCP Server — local FastMCP or remote AgentCore MCP."""

import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
from tests.helpers import (
    console, get_mode, get_terraform_outputs, start_local_server,
    print_header, print_input, print_result, print_error, print_assertions_table,
)

QUERIES = [
    ("search_credit_reports", {"query": "William Mcgee"}),
    ("search_income_verification", {"query": "William Mcgee"}),
    ("search_property_records", {"query": "2928 Coast Line"}),
    ("search_lien_records", {"query": "William Mcgee"}),
]


async def call_mcp_tools(url: str) -> dict[str, str]:
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession

    results = {}
    async with streamablehttp_client(url) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            console.print(f"[dim]Available tools: {tool_names}[/dim]\n")

            for tool_name, args in QUERIES:
                if tool_name not in tool_names:
                    results[tool_name] = f"ERROR: tool not found"
                    continue
                resp = await session.call_tool(tool_name, args)
                results[tool_name] = resp.content[0].text if resp.content else ""
    return results


def test_local():
    """Test against local MCP server."""
    proc = start_local_server("agent_code/kyc_tools", "mcp_server", port=8000)
    try:
        time.sleep(2)
        with console.status("[bold]Querying MCP tools (local)..."):
            results = asyncio.run(call_mcp_tools("http://localhost:8000/mcp"))
        return results
    finally:
        proc.terminate()
        proc.wait()


def test_remote():
    """Test against deployed AgentCore MCP runtime."""
    # For remote MCP, we invoke via the KYC agent which connects to the MCP server
    # Or test the MCP endpoint directly if accessible
    outputs = get_terraform_outputs()
    mcp_url = outputs.get("kyc_tools_mcp_url")
    if not mcp_url:
        print_error("kyc_tools_mcp_url not found in terraform outputs. Testing via KYC agent instead.")
        return test_via_kyc_agent(outputs)
    with console.status("[bold]Querying MCP tools (remote)..."):
        results = asyncio.run(call_mcp_tools(mcp_url))
    return results


def test_via_kyc_agent(outputs: dict):
    """Fallback: test MCP indirectly by invoking the KYC agent."""
    from tests.helpers import get_agentcore_client, invoke_agent
    arn = outputs.get("kyc_agent_arn")
    if not arn:
        print_error("kyc_agent_arn not found in terraform outputs")
        return None
    client = get_agentcore_client()
    with console.status("[bold]Invoking KYC agent (remote, tests MCP connectivity)..."):
        result, _ = invoke_agent(client, arn, {"input": "Research applicant William Mcgee"}, "workshop-user")
    return {"kyc_agent_response": json.dumps(result)}


def run_assertions(results: dict) -> list[tuple[str, bool, str]]:
    checks = []
    if "kyc_agent_response" in results:
        resp = results["kyc_agent_response"]
        checks.append(("KYC agent responded", bool(resp), f"{len(resp)} chars"))
        checks.append(("Contains applicant data", "mcgee" in resp.lower() or "william" in resp.lower(), ""))
        return checks

    for tool_name, _ in QUERIES:
        raw = results.get(tool_name, "")
        has_data = bool(raw) and "ERROR" not in raw
        checks.append((f"{tool_name} returns data", has_data, f"{len(raw)} chars" if has_data else raw[:50]))
        if has_data:
            try:
                parsed = json.loads(raw)
                checks.append((f"{tool_name} valid JSON", True, f"{len(parsed)} records"))
            except (json.JSONDecodeError, TypeError):
                checks.append((f"{tool_name} valid JSON", False, "parse error"))
    return checks


def main():
    mode = get_mode()
    print_header("Module 2: MCP Server (KYC Tools)", mode)

    for tool_name, args in QUERIES:
        print_input({tool_name: args})

    results = test_remote() if mode == "remote" else test_local()
    if not results:
        sys.exit(1)

    for tool_name, raw in results.items():
        print_result(raw, tool_name)

    assertions = run_assertions(results)
    print_assertions_table(assertions)

    if not all(p for _, p, _ in assertions):
        sys.exit(1)


if __name__ == "__main__":
    main()
