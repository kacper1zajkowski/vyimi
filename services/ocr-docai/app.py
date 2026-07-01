import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import documentai

from models import InvoiceData, LineItem, OcrResponse

PROVIDER = "docai"
IMAGE_TYPES = {"image/jpeg", "image/png"}
PDF_TYPE = "application/pdf"

# more info about used processors: https://cloud.google.com/document-ai/docs/processors-list#processor_invoice-processor
TEXT_FIELDS = {
    "invoice_id": "invoice_number",
    "invoice_date": "issue_date",
    "supplier_name": "seller_name",
    "supplier_tax_id": "seller_tax_id",
    "receiver_name": "buyer_name",
    "receiver_tax_id": "buyer_tax_id",
    "currency": "currency",
}
MONEY_FIELDS = {
    "net_amount": "total_net",
    "total_tax_amount": "total_tax",
    "total_amount": "total_gross",
}

app = FastAPI(title="vyimi ocr-docai")


def get_processor() -> tuple[documentai.DocumentProcessorServiceClient, str]:
    project = os.getenv("DOCAI_PROJECT_ID")
    location = os.getenv("DOCAI_LOCATION", "eu")
    processor = os.getenv("DOCAI_PROCESSOR_ID")
    if not project or not processor:
        raise HTTPException(
            status_code=500,
            detail="Brak DOCAI_PROJECT_ID lub DOCAI_PROCESSOR_ID w środowisku",
        )
    # loc check for processor avialability
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    )
    return client, client.processor_path(project, location, processor)


def text_value(entity: documentai.Document.Entity) -> Optional[str]:
    """Preferuj normalized_value (np. data już w ISO), fallback na surowy tekst."""
    if entity.normalized_value and entity.normalized_value.text:
        return entity.normalized_value.text
    return entity.mention_text.strip() or None


def parse_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text)
    # "1.234,56" (zapis EU) → "1234.56"; "1,234.56" (zapis US) → "1234.56"
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def money_value(entity: documentai.Document.Entity) -> Optional[float]:
    money = entity.normalized_value.money_value
    if money and (money.units or money.nanos):
        return money.units + money.nanos / 1e9
    return parse_number(text_value(entity))


def map_line_item(entity: documentai.Document.Entity) -> LineItem:
    fields: dict = {"description": "", "quantity": None, "unit_price": None, "total": None}
    for prop in entity.properties:
        if prop.type_ == "line_item/description":
            fields["description"] = text_value(prop) or ""
        elif prop.type_ == "line_item/quantity":
            fields["quantity"] = parse_number(text_value(prop))
        elif prop.type_ == "line_item/unit_price":
            fields["unit_price"] = money_value(prop)
        elif prop.type_ == "line_item/amount":
            fields["total"] = money_value(prop)
    return LineItem(**fields)


def map_entities(document: documentai.Document) -> InvoiceData:
    data = InvoiceData(document_type="invoice")
    for entity in document.entities:
        if entity.type_ in TEXT_FIELDS:
            setattr(data, TEXT_FIELDS[entity.type_], text_value(entity))
        elif entity.type_ in MONEY_FIELDS:
            setattr(data, MONEY_FIELDS[entity.type_], money_value(entity))
        elif entity.type_ == "line_item":
            data.line_items.append(map_line_item(entity))
    return data


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": PROVIDER}


# tba
'''
@app.post("/ocr", response_model=OcrResponse)
def ocr(file: UploadFile) -> OcrResponse:
    content_type = file.content_type or ""
    if content_type not in IMAGE_TYPES and content_type != PDF_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Nieobsługiwany typ: {content_type!r}. Dozwolone: jpg, png, pdf.",
        )

    content = file.file.read()
    client, processor_name = get_processor()

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=content_type),
    )
    try:
        result = client.process_document(request=request)
    except GoogleAPICallError as exc:
        raise HTTPException(status_code=502, detail=f"Document AI: {exc.message}")

    return OcrResponse(
        provider=PROVIDER,
        filename=file.filename,
        data=map_entities(result.document),
        raw_text=result.document.text or None,
    )
'''