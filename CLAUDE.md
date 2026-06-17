# CLAUDE.md

Your goal is to help the user build out the workshop modules described in @WORKSHOP.md. Each module is an agent skill in the `skills/` directory with setup scripts, scaffold code, and reference documentation. Use the skills and references below to implement each module when the user asks. After completing each module with tests successfully passing, you MUST create a commit as described in the Git Strategy section.

## Available Skills

Skills are located in `skills/` and provide specialized instructions for each workshop module.

### module-1-consolidation-agent
Build the consolidation agent that receives KYC, document, and property data from other agents and produces a mortgage recommendation. Includes geocoding and distance verification tools.
After scaffolding, use the `open-file` skill to open `agent_code/consolidation_agent/consolidation_agent.py`.

### module-2-mcp-server
Build an MCP server backed by SQLite FTS5 for KYC data lookup. Introduces the OpenAPI-to-MCP pattern via AgentCore Gateway (deployed in Module 4).
After scaffolding, use the `open-file` skill to open `agent_code/kyc_tools/mcp_server.py`.

### module-3-research-agents
Build three research agents — document extraction (Strands multimodal + structured output), KYC research (MCP client with OAuth2), and property research (AgentCore Browser + Code Interpreter).
After scaffolding, use the `open-file` skill to open each main file in sequence: `agent_code/doc_extraction_agent/doc_extraction_agent.py`, `agent_code/kyc_agent/kyc_agent.py`, `agent_code/property_research_agent/property_research_agent.py`.

### module-4-deploy
Deploy all agents and tools to AWS using Terraform. Provisions Cognito, OAuth2, ECR, CodeBuild, AgentCore runtimes, AgentCore Gateway, AgentCore Memory, and S3.
After scaffolding, use the `open-file` skill to open `terraform/main.tf`.

### module-5-cli
Build a Python Rich CLI that orchestrates the full KYC pipeline — PDF extraction, parallel agent invocations, consolidation, and sequential display.
After scaffolding, use the `open-file` skill to open `cli/cli.py`.

### module-6-enhancements
Refactor the consolidation agent to use MCP-based geocoding (replacing the inline Strands tool) and add AgentCore Memory to all agents for regulatory compliance.
After making changes, use the `open-file` skill to open `agent_code/consolidation_agent/consolidation_agent.py`.

### module-7-cleanup
Destroy all workshop infrastructure with `terraform destroy`.

You may also use the `open-file` skill to direct the user's attention to specific lines when answering questions.

## Project Structure

```
agent_code/
├── consolidation_agent/        # Module 1 — risk assessment + distance verification
├── kyc_tools/                  # Module 2 — MCP server (FastMCP + SQLite FTS5)
├── doc_extraction_agent/       # Module 3 — document classification/extraction
├── kyc_agent/                  # Module 3 — KYC research via MCP tools
└── property_research_agent/    # Module 3 — browser-based property lookup
cli/                            # Module 5 — CLI orchestrator
terraform/                      # Module 4 — Terraform deployment
sample_data/                    # Pre-existing data, schemas, and API specs
skills/                         # Workshop module skills (setup scripts + scaffolds)
```

Each directory under `agent_code/` is a self-contained Python module with its own `Dockerfile` and `requirements.txt`.

## Python Environment

Use `uv` for managing the local Python environment:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r agent_code/<module>/requirements.txt
```

Each module maintains its own `requirements.txt`. For local testing, install all module dependencies into the shared venv.

## AWS Region

Do not hardcode AWS regions. Detect from the environment:

```python
import os
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
```

Use this for all AWS SDK clients, `AgentCoreBrowser(region=AWS_REGION)`, and `AgentCoreCodeInterpreter(region=AWS_REGION)`. In Dockerfiles, do not set `AWS_REGION` — it is injected by the AgentCore runtime at deployment.

## Model Configuration

Use global inference profile IDs for Bedrock models (not base model IDs):

```python
model_id = os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-6")
```
Use aws cli `aws bedrock list-inference-profiles | jq '.inferenceProfileSummaries[] | select(.inferenceProfileId | startswith("global")) | .inferenceProfileId'`
if you need to look up available global inference profiles. This workshop is designed and tested with `global.anthropic.claude-sonnet-4-6` and that should usually suffice.

## AgentCore Runtime Patterns

### HTTP Agents (port 8080)

Agents using `server_protocol = "HTTP"` listen on port 8080:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

APP = BedrockAgentCoreApp()

@APP.entrypoint
async def handler(payload: dict[str, str]):
    return {"result": "..."}

if __name__ == "__main__":
    APP.run()  # Defaults to port 8080
```

### MCP Servers (port 8000)

MCP servers using `server_protocol = "MCP"` must listen on port 8000:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name", host="0.0.0.0", port=8000)

@mcp.tool()
def my_tool(query: str) -> str:
    """Tool description."""
    return result

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

### Invoking Deployed Agents

```python
import boto3, json
from botocore.config import Config

client = boto3.client("bedrock-agentcore", region_name="us-east-1", config=Config(read_timeout=300))

resp = client.invoke_agent_runtime(
    agentRuntimeArn=arn,
    qualifier="DEFAULT",
    payload=json.dumps(payload).encode(),
    runtimeUserId="workshop-user",  # Required for agents using OAuth2 M2M flow
)
result = json.loads(resp["response"].read())
```

- **`runtimeUserId`**: Required for agents that use `@requires_access_token` (e.g., KYC agent connecting to MCP server with OAuth2).
- **`Config(read_timeout=300)`**: AgentCore runtimes cold-start on first invocation (~30-90s).
- **`runtimeSessionId`**: Use to pin subsequent requests to the same container instance (important for async polling patterns).

## Sample Data

`sample_data/` contains synthetic KYC data and input documents:

```
sample_data/
├── SCHEMA.md                              # Full database schema documentation
├── input/
│   └── sample_documents.pdf               # 4-page mortgage application PDF
├── api_schemas/
│   └── openstreetmap.json                 # OpenAPI spec for Nominatim geocoding
└── sources/
    ├── kyc_data.db                        # SQLite database with FTS5 trigram indexes
    ├── build_db.py                        # Script to rebuild the database
    ├── synthetic_credit_reports.json       # Source JSONL
    ├── synthetic_income_verification.json  # Source JSONL
    ├── synthetic_property_records.json     # Source JSONL
    └── synthetic_lien_records.json         # Source JSONL
```

`sample_data/input/sample_documents.pdf` — 4-page sample mortgage application (mortgage form, paystub, W2, driver's license) for applicant **William Mcgee**, property at **2928 Coast Line Ct, Las Vegas, NV 89117**.

### Database Tables

| Table | Key Fields | FTS-Indexed Fields |
|---|---|---|
| credit_reports | government_id (PK), full_legal_name, credit_score, account_tradelines (JSON) | full_legal_name, primary_address |
| income_verification | government_id (PK), employee_name, employer_name, verified_annual_salary | employee_name |
| property_records | property_id (PK), owner_name_on_deed, property_address, assessed_value | owner_name_on_deed, property_address |
| lien_records | lien_id (PK), property_id, debtor_name, lien_amount, lien_holder | debtor_name, debtor_address |

### Querying

```sql
-- Fuzzy search (FTS5 trigram)
SELECT t.* FROM credit_reports t
JOIN credit_reports_fts fts ON t.rowid = fts.rowid
WHERE credit_reports_fts MATCH '"William Mcgee"'
ORDER BY bm25(credit_reports_fts) LIMIT 5;
```

### Read-Only Filesystem

AgentCore containers have a read-only filesystem. Copy the database to `/tmp` at startup:

```python
import shutil
_SRC_DB = os.path.join(os.path.dirname(__file__), "kyc_data.db")
DB_PATH = "/tmp/kyc_data.db"
if not os.path.exists(DB_PATH):
    shutil.copy2(_SRC_DB, DB_PATH)
```

## Dockerfile Pattern

All agents use the same Dockerfile structure:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
RUN useradd -m -u 1000 bedrock_agentcore
WORKDIR /app
ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1 UV_NO_PROGRESS=1 PYTHONUNBUFFERED=1 DOCKER_CONTAINER=1
ENTRYPOINT ["opentelemetry-instrument", "python"]
CMD ["-m", "module_name"]
COPY requirements.txt .
RUN uv pip install -r requirements.txt
RUN uv pip install aws-opentelemetry-distro==0.12.2
USER bedrock_agentcore
COPY --chown=bedrock_agentcore:bedrock_agentcore . .
```

Key points:
- `opentelemetry-instrument` entrypoint enables AgentCore tracing
- `aws-opentelemetry-distro` requires `boto3` in requirements (even for MCP servers)
- Run as non-root `bedrock_agentcore` user
- `python -m module_name` finds `module_name.py` in `/app`

## Terraform Deployment

Module 4 scaffold includes reusable terraform modules:

| Module | Purpose |
|--------|---------|
| `cognito` | OAuth2 user pool + app client |
| `oauth2_credential_provider` | AgentCore M2M token acquisition |
| `api_key_credential_provider` | API key injection for outbound headers |
| `agentcore_gateway` | OpenAPI → MCP via Gateway |
| `memory` | AgentCore Memory for session persistence |
| `agentcore_runtime` | Container-based agent runtime |
| `docker_build_push` | ECR + CodeBuild image pipeline |
| `observability` | CloudWatch + Xray setup for logging and tracing |

After `terraform apply`, generate `.env` directly from the terraform outputs



## Testing & Makefile

Each module's setup script copies a test into `tests/`. After completing each module, instruct the user to run the corresponding test (e.g. `make test_module_1`) and inform the user to let you know if there are any issues. Do not mark a module as done until the user prompts you to proceed to next module after successfully running the test.

After completing each module, first make sure you are in the workshop parent directory, then make sure the corresponding target is added to the root `Makefile` and provide the user with instructions to run the test. 

**After Module 1:**
```makefile
.PHONY: test_module_1
test_module_1:
	$(PYTHON) tests/test_module_1.py
```

**After Module 2:**
```makefile
.PHONY: test_module_2
test_module_2:
	$(PYTHON) tests/test_module_2.py
```

**After Module 3:**
```makefile
.PHONY: test_module_3
test_module_3:
	$(PYTHON) tests/test_module_3.py
```

**After Module 4:**
```makefile
.PHONY: test_module_4
test_module_4:
	$(PYTHON) tests/test_module_4.py
```

**After Module 5:**
```makefile
.PHONY: test_module_5
test_module_5:
	$(PYTHON) tests/test_module_5.py
```

The `Makefile` starts with only a `PYTHON` variable. Targets are appended progressively:

```makefile
PYTHON := .venv/bin/python
```

Tests auto-detect local vs remote mode. Override with `TEST_MODE=local` or `TEST_MODE=remote`.

**Exception — Module 5:** Instead of running the automated test, provide the user with the CLI command to run manually:
Also inform the user that the command should be run from the workshop root directory ~/workshop.
```bash
.venv/bin/python cli/cli.py sample_data/input/sample_documents.pdf
```

The CLI takes 3-5 minutes to complete the full pipeline. Let the user run it interactively so they can observe the Rich output, browser console link, and progress indicators in real time.

## Testing Locally

Start agents locally for testing before deploying:

```bash
# MCP Server (port 8080 locally, 8000 on AgentCore)
cd agent_code/kyc_tools && python -m mcp_server

# Test via MCP client
python -c "
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
import asyncio

async def test():
    async with streamablehttp_client('http://localhost:8080/mcp') as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print([t.name for t in tools.tools])
asyncio.run(test())
"
```

## Key Gotchas

1. **MCP port**: AgentCore MCP runtimes must listen on port **8000** (not 8080)
2. **Read-only filesystem**: Copy databases to `/tmp` at startup
3. **Model IDs**: Use inference profiles (`global.anthropic.claude-sonnet-4-6`), not base model IDs
4. **OAuth2 agents**: Pass `runtimeUserId` when invoking agents that use `@requires_access_token`
5. **Cold starts**: First invocation takes 1-5s — use `Config(read_timeout=300)`
6. **Async polling**: Use `runtimeSessionId` to pin poll requests to the same container
7. **FastMCP constructor**: Pass `host`/`port` in `FastMCP()` constructor, not in `run()`
8. **boto3 for otel**: MCP servers need `boto3` in requirements for `aws-opentelemetry-distro`

## Git Strategy

### Module Commits

After each module is completed create a commit on `main`:

```bash
git add -A
git commit -m "Module N: <brief description>"
```

Example commit messages:
- `Module 1: Consolidation agent with geocoding and distance tools`
- `Module 2: MCP server with SQLite FTS5`
- `Module 3: Research agents (doc extraction, KYC, property)`
- `Module 4: Terraform deployment and gateway refactoring`
- `Module 5: Rich CLI orchestrator`
- `Module 6: Cleanup script`

### Feature Branches

When the user requests a new feature, enhancement, or experiment outside the standard module flow, create a feature branch:

```bash
git checkout -b feature/<short-description>
```

Commit work on the branch. When the user confirms the feature is complete, offer to merge back to `main`:

```bash
git checkout main
git merge feature/<short-description>
git branch -d feature/<short-description>
```

If the user wants to discard the experiment, switch back to `main` without merging.

### Initial Setup

On first module start, initialize the repo if not already done:

```bash
git init
git add -A
git commit -m "Initial workshop scaffold"
```
