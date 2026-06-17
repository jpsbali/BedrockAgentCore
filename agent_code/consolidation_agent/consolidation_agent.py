import math
import os

import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

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


@tool
def geocode_address(address: str) -> dict:
    """Geocode an address using Nominatim API. Returns lat/lon coordinates for the given address."""
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": address,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "us",
        },
        headers={"User-Agent": "KYC-Workshop/1.0"},
        timeout=10,
    )
    results = resp.json()
    if not results:
        return {"error": f"No results found for: {address}"}
    r = results[0]
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", ""),
    }


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


@APP.entrypoint
async def consolidate_analysis(payload: dict[str, str]):
    model = BedrockModel(
        model_id=os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-6"),
        temperature=0.0,
    )
    agent = Agent(
        model=model,
        system_prompt=CONSOLIDATION_AGENT_PROMPT,
        tools=[geocode_address, calculate_distance],
    )

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

Verify that the applicant's work address is within 30 miles of the property address. Use the geocode_address tool to get coordinates for both addresses, then use calculate_distance to check.

Provide your comprehensive analysis and recommendation."""

    response = agent(input_text)
    return {"analysis": str(response)}


if __name__ == "__main__":
    APP.run()
