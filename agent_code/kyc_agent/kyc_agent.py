import os
import botocore.config
from uuid import uuid4

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
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

OAUTH2_ID_PROVIDER = os.getenv("OAUTH2_ID_PROVIDER", "")
MEMORY_ID = os.getenv("MEMORY_ID", "")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
BOTO_CONFIG = botocore.config.Config(retries={"max_attempts": 6, "mode": "adaptive"})


def _make_session_manager(actor_id: str) -> AgentCoreMemorySessionManager | None:
    if not MEMORY_ID:
        return None
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=f"session-{uuid4()}",
            actor_id=actor_id,
        ),
        region_name=REGION,
        boto_client_config=BOTO_CONFIG,
    )


def _create_mcp_client_local(mcp_url: str) -> MCPClient:
    return MCPClient(lambda: streamablehttp_client(mcp_url))


def _create_mcp_client_remote(mcp_url: str) -> MCPClient:
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
        agent = Agent(
            model=MODEL,
            system_prompt=KYC_RESEARCH_AGENT_PROMPT,
            tools=tools,
            session_manager=_make_session_manager(f"kyc-agent-{uuid4()}"),
        )
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
