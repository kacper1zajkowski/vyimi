import csv
import io
import os
import re
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError

from models import InvoiceData, OcrResponse

ENV_PREFIX = "PROVIDER_URL_"

ADAPTER_TIMEOUT_S = 120

PROVIDERS: dict[str, str] = {
    name.removeprefix(ENV_PREFIX).lower().replace("_", "-"): url.rstrip("/")
    for name, url in os.environ.items()
    if name.startswith(ENV_PREFIX) and url
}

DOC_FIELDS = [f for f in InvoiceData.model_fields if f != "line_items"]
ITEM_FIELDS = ["item_description", "item_quantity", "item_unit_price", "item_total"]

app = FastAPI(title="vyimi gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_csv(data: InvoiceData) -> str:
    """Jeden wiersz na pozycję dokumentu, kolumny dokumentu powtórzone w każdym
    wierszu — najprostszy kształt do wczytania w Excelu/pandas. Dokument bez
    pozycji daje jeden wiersz z pustymi kolumnami item_*."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DOC_FIELDS + ITEM_FIELDS)

    doc_values = [getattr(data, field) for field in DOC_FIELDS]
    items = data.line_items or [None]
    for item in items:
        if item is None:
            writer.writerow(doc_values + [None] * len(ITEM_FIELDS))
        else:
            writer.writerow(
                doc_values + [item.description, item.quantity, item.unit_price, item.total]
            )
    return buf.getvalue()


def csv_filename(upload_name: str | None) -> str:
    stem = Path(upload_name or "").stem or "result"
    return re.sub(r"[^A-Za-z0-9._-]", "_", stem) + ".csv"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "providers": sorted(PROVIDERS)}


'''@app.get("/providers")
def providers() -> dict:
    return {"providers": sorted(PROVIDERS)}
'''

@app.post("/ocr")
async def ocr(
    file: UploadFile,
    provider: str = Query(description="Nazwa providera OCR, patrz GET /providers"),
    format: Literal["json", "csv"] = Query("json"),
):
    base_url = PROVIDERS.get(provider)
    if base_url is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nieznany provider {provider!r}. Dostępne: {sorted(PROVIDERS)}",
        )

    async with httpx.AsyncClient(timeout=ADAPTER_TIMEOUT_S) as client:
        try:
            resp = await client.post(
                f"{base_url}/ocr",
                files={"file": (file.filename, await file.read(), file.content_type)},
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, detail=f"Adapter {provider!r} niedostępny: {exc}"
            )

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    try:
        result = OcrResponse.model_validate_json(resp.content)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Adapter {provider!r} złamał kontrakt OcrResponse: {exc}",
        )

    if format == "csv":
        return Response(
            content=to_csv(result.data),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{csv_filename(file.filename)}"'
            },
        )
    return result
