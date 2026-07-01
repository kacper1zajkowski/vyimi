import base64
import os

from fastapi import FastAPI, HTTPException, UploadFile
from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from models import InvoiceData, OcrResponse

PROVIDER = "mistral"
OCR_MODEL = "mistral-ocr-latest"
IMAGE_TYPES = {"image/jpeg", "image/png"}
PDF_TYPE = "application/pdf"

MAX_ANNOTATION_PAGES = 8 # for mistral api 

app = FastAPI(title="vyimi ocr-mistral")


def get_client() -> Mistral:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Brak MISTRAL_API_KEY w środowisku")
    return Mistral(api_key=api_key)


def build_document(content: bytes, content_type: str) -> dict:
    b64 = base64.b64encode(content).decode("ascii")
    data_uri = f"data:{content_type};base64,{b64}"
    if content_type == PDF_TYPE:
        return {"type": "document_url", "document_url": data_uri}
    return {"type": "image_url", "image_url": data_uri}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": PROVIDER}


@app.post("/ocr", response_model=OcrResponse)
async def ocr(file: UploadFile) -> OcrResponse:
    content_type = file.content_type or ""
    if content_type not in IMAGE_TYPES and content_type != PDF_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Nieobsługiwany typ: {content_type!r}. Dozwolone: jpg, png, pdf.",
        )

    content = await file.read()
    client = get_client()

    resp = client.ocr.process(
        model=OCR_MODEL,
        document=build_document(content, content_type),
        document_annotation_format=response_format_from_pydantic_model(InvoiceData),
        pages=list(range(MAX_ANNOTATION_PAGES)),
        include_image_base64=False,
    )

    try:
        data = InvoiceData.model_validate_json(resp.document_annotation or "")
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Nieznany schemat danych: {exc}",
        )

    raw_text = "\n\n".join(page.markdown for page in resp.pages)

    return OcrResponse(
        provider=PROVIDER,
        filename=file.filename,
        data=data,
        raw_text=raw_text,
    )
