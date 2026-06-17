import math
import os
import botocore.config
from uuid import uuid4

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

CONSOLIDATION_AGENT_PROMPT = """You are a mortgage application consolidation agent. Your job is to analyze all the gathered information about a mortgage applicant and provide a final recommendation.

You will receive:
1. Customer background information (credit score, employment, debt-to-income ratio, liens)
2. Document extraction results (ID verification, W2, bank statements)
3. Property research data (property details, assessed value, taxes)

You have access to tools for geocoding addresses and calculating distances. Use these to verify that the applicant's work location is within 30 miles of the mortgage property location. This is a requirement for primary residence mortgages.

Provide a comprehensive analysis with:
1. **Executive Summary** - Brief overview of the application
2. **Risk Assessment** - Overall risk level (Low/Medium/High) with justification
3. **Key Findings** - Most important positive and negative factors
4. **Distance Verification** - Confirm work-to-property distance is within 30 miles
5. **Recommendation** - Clear approve/deny/conditional approval decision
6. **Conditions** (if applicable) - What needs to be addressed before approval

Be concise but thorough. Use markdown formatting for clarity.
"""

APP = BedrockAgentCoreApp()

GATEWAY_URL = os.getenv("GEOCODING_GATEWAY_URL", "")
OAUTH2_ID_PROVIDER = os.getenv("OAUTH2_ID_PROVIDER", "")
MEMORY_ID = os.getenv("MEMORY_ID", "")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
BOTO_CONFIG = botocore.config.Config(retries={"max_attempts": 6, "mode": "adaptive"})


@tool
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Calculate distance in miles between two points using the haversine formula."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    return {"distance_miles": round(distance, 2), "within_30_miles": distance <= 30.0}


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


def _initialize_agent_local(model):
    """Local mode: no auth, no MCP geocoding — fall back to plain agent."""
    return None, Agent(
        model=model,
        system_prompt=CONSOLIDATION_AGENT_PROMPT,
        tools=[calculate_distance],
        session_manager=_make_session_manager(f"consolidation-agent-{uuid4()}"),
    )


@requires_access_token(
    provider_name=OAUTH2_ID_PROVIDER or "placeholder",
    scopes=["kyc-mcp/access"],
    auth_flow="M2M",
    into="oauth2_token",
)
def _initialize_agent_remote(model, *, oauth2_token: str):
    """Remote mode: connect to Gateway MCP with OAuth2 bearer token."""
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            GATEWAY_URL, headers={"Authorization": f"Bearer {oauth2_token}"}
        )
    )
    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            system_prompt=CONSOLIDATION_AGENT_PROMPT,
            tools=[calculate_distance] + mcp_tools,
            session_manager=_make_session_manager(f"consolidation-agent-{uuid4()}"),
        )
    return mcp_client, agent


@APP.entrypoint
async def consolidate_analysis(payload: dict[str, str]):
    model = BedrockModel(
        model_id=os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-6"),
        temperature=0.0,
    )

    if OAUTH2_ID_PROVIDER and GATEWAY_URL:
        mcp_client, agent = _initialize_agent_remote(model)
    else:
        mcp_client, agent = _initialize_agent_local(model)

    kyc_data = payload.get("kyc_data", "")
    doc_data = payload.get("doc_data", "")
    property_data = payload.get("property_data", "")

    input_text = f"""Analyze the following mortgage application data and provide your recommendation:

## Customer Background (KYC)
{kyc_data}

## Document Verification
{doc_data}

## Property Information
{property_data}

Verify that the applicant's work address is within 30 miles of the property address. Use the geocoding tool to get coordinates for both addresses, then use calculate_distance to check.

Provide your comprehensive analysis and recommendation."""

    if mcp_client:
        with mcp_client:
            response = agent(input_text)
    else:
        response = agent(input_text)

    return {"analysis": str(response)}


if __name__ == "__main__":
    APP.run()
