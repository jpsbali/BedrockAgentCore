import io
import os
import threading
import botocore.config
from typing import List
from uuid import uuid4

import boto3
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from PIL import Image as PILImage
from pydantic import BaseModel, Field
from strands import Agent
from strands.experimental.hooks import AfterToolInvocationEvent
from strands.hooks import HookProvider, HookRegistry
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser
from strands_tools.browser.models import BrowserInput, ScreenshotAction
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

APP = BedrockAgentCoreApp(debug=False)
TASK_RESULTS = {}

MEMORY_ID = os.getenv("MEMORY_ID", "")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
BOTO_CONFIG = botocore.config.Config(retries={"max_attempts": 6, "mode": "adaptive"})


class PropertyInfo(BaseModel):
    address: str = Field(..., description="The full address of the property.")
    parcel_identifier: str = Field(..., description="The parcel identifier.")
    land_size_sqft: int = Field(..., description="The land size in square feet.")
    building_size_sqft: int = Field(
        ..., description="The building size in square feet."
    )
    livable_area_sqft: int = Field(..., description="The livable area in square feet.")
    year_built: int = Field(..., description="The year the property was built.")
    construction_type: str = Field(..., description="The type of construction.")
    roof_type: str = Field(..., description="The type of roof.")
    has_pool: bool = Field(..., description="Whether the property has a pool.")
    number_of_fireplaces: int = Field(..., description="Number of fireplaces.")
    assessed_value: float = Field(..., description="The assessed value.")
    taxable_value: float = Field(..., description="The taxable value.")
    annual_property_tax: float = Field(..., description="The annual property tax.")


class CaptureHooks(HookProvider):
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.screenshot_dir = f"/tmp/screenshots_{task_id}"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.screenshot_paths = []
        self.code_snippets = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolInvocationEvent, self.take_screenshot)
        registry.add_callback(AfterToolInvocationEvent, self.save_code)

    def take_screenshot(self, event: AfterToolInvocationEvent) -> None:
        try:
            if event.tool_use.get("name") == "browser":
                session_name = (
                    event.tool_use.get("input", {})
                    .get("browser_input", {})
                    .get("action", {})
                    .get("session_name", "default")
                )
                browser_tool = event.selected_tool
                screenshot_path = (
                    f"{self.screenshot_dir}/screenshot_{len(self.screenshot_paths)}.png"
                )
                action = ScreenshotAction(
                    type="screenshot", session_name=session_name, path=screenshot_path
                )
                browser_input = BrowserInput(action=action)
                try:
                    os.environ["STRANDS_BROWSER_SCREENSHOTS_DIR"] = self.screenshot_dir
                    browser_tool(browser_input)
                    if os.path.exists(screenshot_path):
                        self.screenshot_paths.append(screenshot_path)
                except Exception as e:
                    print(f"[DEBUG] screenshot error: {e}", flush=True)
        except Exception as e:
            print(f"[DEBUG] browser hook error: {e}", flush=True)

    def save_code(self, event: AfterToolInvocationEvent) -> None:
        try:
            if event.tool_use.get("name") == "code_interpreter":
                code_input = (
                    event.tool_use.get("input", {})
                    .get("code_interpreter_input", {})
                    .get("action", {})
                )
                if code_input.get("type") == "executeCode":
                    self.code_snippets.append(code_input["code"])
                elif code_input.get("type") == "executeCommand":
                    self.code_snippets.append(f"# Command: {code_input['command']}")
        except Exception:
            pass


PROPERTY_RESEARCH_PROMPT = """You are a building research agent. Your job is to get information about a specific building in Clark County, Nevada.
Only use the official Clark County website (https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx) to research the property.
Decompose the address into its components (street number, street name, street type, city) and enter these into the form.
Use the following html element ids: txtNumber, txtName, lstType, lstCity, btnSubmit.
The search results table id is "gvList". Click the parcel identifier link in the third column.
Extract all text content from the property details page.
Use code interpreter to calculate annual tax (assessed value * 0.0056).
"""


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


def upload_to_s3(bucket_name: str, key: str, data: bytes, content_type: str) -> str:
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket_name, Key=key, Body=data, ContentType=content_type)
    return f"s3://{bucket_name}/{key}"


def generate_gif(screenshot_paths: List[str], output_path: str) -> str:
    if not screenshot_paths:
        return ""
    images = [PILImage.open(path) for path in screenshot_paths]
    images[0].save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=500,
        loop=0,
    )
    return output_path


def research_property_background(
    address: str, bucket_name: str, region: str, task_id: int, browser: AgentCoreBrowser
):
    global TASK_RESULTS
    try:
        TASK_RESULTS[task_id] = {"status": "BUSY", "task_id": task_id}

        code_interpreter = AgentCoreCodeInterpreter(region=region)
        capture_hooks = CaptureHooks(task_id)

        model = BedrockModel(
            model_id="global.anthropic.claude-sonnet-4-6", temperature=0.0
        )
        agent = Agent(
            model=model,
            system_prompt=PROPERTY_RESEARCH_PROMPT,
            tools=[browser.browser, code_interpreter.code_interpreter],
            hooks=[capture_hooks],
            session_manager=_make_session_manager(f"property-research-{uuid4()}"),
        )

        result = agent(
            f"Find information about the property at {address}",
            structured_output_model=PropertyInfo,
        )

        # Generate GIF replay
        replay_path = ""
        if capture_hooks.screenshot_paths:
            replay_path = f"/tmp/replay_{task_id}.gif"
            generate_gif(capture_hooks.screenshot_paths, replay_path)
            if bucket_name:
                try:
                    with open(replay_path, "rb") as f:
                        replay_path = upload_to_s3(
                            bucket_name,
                            f"replays/{task_id}/replay.gif",
                            f.read(),
                            "image/gif",
                        )
                except Exception as e:
                    print(f"[DEBUG] S3 upload error: {e}", flush=True)

        browser.close_platform()
        code_interpreter.cleanup_platform()

        TASK_RESULTS[task_id] = {
            "property_info": result.structured_output.model_dump(),
            "screenshots": capture_hooks.screenshot_paths,
            "replay_gif": replay_path,
            "code_snippets": capture_hooks.code_snippets,
            "status": "completed",
        }
        APP.complete_async_task(task_id)
    except Exception as e:
        TASK_RESULTS[task_id] = {"error": str(e), "status": "failed"}
        APP.complete_async_task(task_id)


@APP.entrypoint
def research_property_endpoint(payload: dict[str, str]):
    global TASK_RESULTS
    address = payload.get("address")
    task_id_to_check = payload.get("task_id")

    if task_id_to_check is not None:
        task_id_int = int(task_id_to_check)
        if task_id_int in TASK_RESULTS:
            return TASK_RESULTS[task_id_int]
        return {"status": "BUSY", "task_id": task_id_int}

    if not address:
        for task_id, result in TASK_RESULTS.items():
            if result.get("status") in ["completed", "failed"]:
                return result
        return {"status": "BUSY"}

    bucket_name = payload.get("bucket_name", os.getenv("S3_BUCKET_NAME", ""))
    region = os.getenv("AWS_REGION", "us-east-1")

    browser = AgentCoreBrowser(region=region)

    task_id = APP.add_async_task("property_research", {"address": address})
    threading.Thread(
        target=research_property_background,
        args=(address, bucket_name, region, task_id, browser),
        daemon=True,
    ).start()

    return {
        "message": f"Property research started for {address}",
        "task_id": task_id,
        "status": "BUSY",
    }


if __name__ == "__main__":
    APP.run()
