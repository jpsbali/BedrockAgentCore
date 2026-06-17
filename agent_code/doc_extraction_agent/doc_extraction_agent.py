import base64
import io
import os
from enum import Enum

import pdfplumber
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock
from strands.types.media import ImageContent, ImageSource


class DocumentType(str, Enum):
    MortgageApplication = "MortgageApplication"
    W2Form = "W2Form"
    PayStub = "PayStub"
    DriverLicense = "DriverLicense"
    Unknown = "Unknown"


class ClassificationResult(BaseModel):
    document_type: DocumentType


class MortgageApplication(BaseModel):
    first_name: str
    last_name: str
    work_address: str
    property_address: str


class W2Form(BaseModel):
    employer_name: str
    employee_name: str
    employer_address: str
    wages: float
    federal_tax_withheld: float
    social_security_wages: float
    social_security_tax_withheld: float
    medicare_wages: float
    medicare_tax_withheld: float


class PayStub(BaseModel):
    pay_period: str
    pay_date: str
    employer_name: str
    employee_name: str
    wages: float
    tax_withheld: float


class DriverLicense(BaseModel):
    license_number: str
    name: str
    date_of_birth: str
    expiration_date: str


EXTRACTION_MODELS = {
    DocumentType.MortgageApplication: MortgageApplication,
    DocumentType.W2Form: W2Form,
    DocumentType.PayStub: PayStub,
    DocumentType.DriverLicense: DriverLicense,
}

APP = BedrockAgentCoreApp()

MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-6")


def classify_and_extract(image_bytes: bytes) -> dict:
    model = BedrockModel(model_id=MODEL_ID, temperature=0.0)

    # Classify
    classify_agent = Agent(
        model=model,
        system_prompt="Classify documents into: MortgageApplication, W2Form, PayStub, DriverLicense, or Unknown.",
    )
    content: list[ContentBlock] = [
        {"text": "Classify this document."},
        {"image": ImageContent(format="png", source=ImageSource(bytes=image_bytes))},
    ]
    result = classify_agent(content, structured_output_model=ClassificationResult)
    doc_type = result.structured_output.document_type

    if doc_type == DocumentType.Unknown:
        return {"document_type": doc_type.value, "extracted_data": None}

    # Extract
    extract_agent = Agent(
        model=model,
        system_prompt=f"Extract all fields from this {doc_type.value} document.",
    )
    extract_content: list[ContentBlock] = [
        {"text": f"Extract information from this {doc_type.value}."},
        {"image": ImageContent(format="png", source=ImageSource(bytes=image_bytes))},
    ]
    extraction = extract_agent(
        extract_content, structured_output_model=EXTRACTION_MODELS[doc_type]
    )
    return {
        "document_type": doc_type.value,
        "extracted_data": extraction.structured_output.model_dump(),
    }


def pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=150).original
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pages.append(buf.getvalue())
    return pages


@APP.entrypoint
async def extract_document(payload: dict[str, str]):
    try:
        raw_b64 = (
            payload.get("image")
            or payload.get("image_b64")
            or payload.get("pdf")
            or payload.get("pdf_b64")
        )
        if not raw_b64:
            return {"error": "Missing 'image', 'image_b64', or 'pdf' in payload"}

        raw_bytes = base64.b64decode(raw_b64)

        if raw_bytes[:4] == b"%PDF":
            page_images = pdf_to_page_images(raw_bytes)
            extractions = [classify_and_extract(p) for p in page_images]
            return {"extractions": extractions}

        extractions = [classify_and_extract(raw_bytes)]
        return {"extractions": extractions}

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    APP.run()
