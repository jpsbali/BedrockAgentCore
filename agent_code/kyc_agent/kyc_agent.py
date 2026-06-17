import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

KYC_RESEARCH_AGENT_PROMPT = """You are a Know Your Customer (KYC) research agent whose job is to gather information about mortgage applicants to help determine their eligibility for a primary residence mortgage.

You have access to the following tools:
1. Credit Report Search: Search credit report data by 'full_legal_name' or 'primary_address'.
2. Income Verification Search: Search income verification data by 'employee_name'.
3. Property Records Search: Search property records by 'owner_name_on_deed' or 'property_address'.
4. Lien Records Search: Search lien records by 'debtor_name' or 'debtor_address'.

Gather the following information about the applicant:
1. Full legal name
2. Current address
3. Employment status and income
4. Credit score
5. Debt to income ratio
6. Any liens or judgments against them

Use fuzzy matching and partial matches across datasets to find all relevant information.
"""

KYC_AGENT = None
MCP_CLIENT = None
MODEL = BedrockModel(
    model_id=os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-6"),
    temperature=0.0,
)

APP = BedrockAgentCoreApp()

# Detect mode: if OAUTH2_ID_PROVIDER is set, use OAuth2; otherwise connect without auth
OAUTH2_ID_PROVIDER = os.getenv("OAUTH2_ID_PROVIDER", "")


def _create_mcp_client_local(mcp_url: str) -> MCPClient:
    """Local mode: connect to MCP server without authentication."""
    return MCPClient(lambda: streamablehttp_client(mcp_url))


def _create_mcp_client_remote(mcp_url: str) -> MCPClient:
    """Remote mode: connect to MCP server with OAuth2 bearer token."""
    from bedrock_agentcore.identity.auth import requires_access_token

    @requires_access_token(
        provider_name=OAUTH2_ID_PROVIDER,
        scopes=["kyc-mcp/access"],
        auth_flow="M2M",
        into="oauth2_token",
    )
    def _get_authenticated_client(mcp_url: str, *, oauth2_token: str) -> MCPClient:
        return MCPClient(
            lambda: streamablehttp_client(
                mcp_url, headers={"Authorization": f"Bearer {oauth2_token}"}
            )
        )

    return _get_authenticated_client(mcp_url)


def initialize_kyc_agent(mcp_url: str) -> tuple[MCPClient, Agent]:
    if OAUTH2_ID_PROVIDER:
        mcp_client = _create_mcp_client_remote(mcp_url)
    else:
        mcp_client = _create_mcp_client_local(mcp_url)

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(model=MODEL, system_prompt=KYC_RESEARCH_AGENT_PROMPT, tools=tools)
    return mcp_client, agent


@APP.entrypoint
async def invoke_kyc_agent(payload: dict[str, str]):
    global KYC_AGENT, MCP_CLIENT

    mcp_url = os.getenv("MCP_URL", "http://localhost:8000/mcp")

    if KYC_AGENT is None or MCP_CLIENT is None:
        MCP_CLIENT, KYC_AGENT = initialize_kyc_agent(mcp_url)

    with MCP_CLIENT:
        response = KYC_AGENT(payload["input"])
        return {"result": str(response)}


if __name__ == "__main__":
    APP.run()
