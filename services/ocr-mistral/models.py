# unified contract type across providers; eg if receipt dont have proper field - put null

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """Jedna pozycja z faktury/paragonu."""

    description: str = Field(description="Nazwa towaru lub usługi")
    quantity: Optional[float] = Field(None, description="Ilość")
    unit_price: Optional[float] = Field(None, description="Cena jednostkowa brutto")
    total: Optional[float] = Field(None, description="Wartość pozycji brutto")


class InvoiceData(BaseModel):
    """Ustrukturyzowane dane wyciągnięte z dokumentu."""

    document_type: Literal["invoice", "receipt", "other"] = Field(
        description="Typ dokumentu: faktura, paragon lub inny"
    )
    invoice_number: Optional[str] = Field(None, description="Numer faktury/paragonu")
    issue_date: Optional[str] = Field(
        None, description="Data wystawienia w formacie ISO (YYYY-MM-DD)"
    )
    seller_name: Optional[str] = Field(None, description="Nazwa sprzedawcy")
    seller_tax_id: Optional[str] = Field(None, description="NIP sprzedawcy, same cyfry")
    buyer_name: Optional[str] = Field(None, description="Nazwa nabywcy")
    buyer_tax_id: Optional[str] = Field(None, description="NIP nabywcy, same cyfry")
    currency: Optional[str] = Field(None, description="Waluta jako kod ISO, np. PLN")
    total_net: Optional[float] = Field(None, description="Suma netto")
    total_tax: Optional[float] = Field(None, description="Suma VAT")
    total_gross: Optional[float] = Field(None, description="Suma brutto")
    line_items: list[LineItem] = Field(default_factory=list, description="Pozycje dokumentu")


class OcrResponse(BaseModel):
    """Koperta odpowiedzi adaptera — to zwraca POST /ocr każdego serwisu."""

    provider: str
    filename: Optional[str] = None
    data: InvoiceData
    raw_text: Optional[str] = Field(
        None, description="Surowy tekst/markdown z OCR, do debugowania"
    )
