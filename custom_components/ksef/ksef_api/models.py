from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class DateRange:
    from_date: str
    to_date: str
    date_type: str = "Issue"

    def to_dict(self) -> dict:
        return {"dateType": self.date_type, "from": self.from_date, "to": self.to_date}


@dataclass
class InvoiceMetadata:
    ksef_number: str
    invoice_number: str
    issue_date: str
    seller_nip: str
    seller_name: str
    buyer_name: str
    buyer_identifier: str
    net_amount: float
    gross_amount: float
    vat_amount: float
    currency: str
    invoice_type: str

    @classmethod
    def from_dict(cls, d: dict) -> "InvoiceMetadata":
        seller = d.get("seller") or {}
        buyer = d.get("buyer") or {}
        buyer_id = buyer.get("identifier") or {}
        return cls(
            ksef_number=d.get("ksefNumber", ""),
            invoice_number=d.get("invoiceNumber", ""),
            issue_date=d.get("issueDate", ""),
            seller_nip=seller.get("nip", ""),
            seller_name=seller.get("name", ""),
            buyer_name=buyer.get("name", ""),
            buyer_identifier=buyer_id.get("value", ""),
            net_amount=float(d.get("netAmount") or 0),
            gross_amount=float(d.get("grossAmount") or 0),
            vat_amount=float(d.get("vatAmount") or 0),
            currency=d.get("currency", "PLN"),
            invoice_type=d.get("invoiceType", ""),
        )

    def as_attr_dict(self) -> dict:
        return {
            "ksef_number": self.ksef_number,
            "invoice_number": self.invoice_number,
            "date": self.issue_date[:10] if self.issue_date else "",
            "seller": self.seller_name or self.seller_nip,
            "buyer": self.buyer_name or self.buyer_identifier,
            "net": self.net_amount,
            "gross": self.gross_amount,
            "vat": self.vat_amount,
            "currency": self.currency,
            "type": self.invoice_type,
        }


@dataclass
class InvoiceQueryResponse:
    invoices: list[InvoiceMetadata]
    has_more: bool
    is_truncated: bool

    @classmethod
    def from_dict(cls, d: dict) -> "InvoiceQueryResponse":
        return cls(
            invoices=[InvoiceMetadata.from_dict(i) for i in d.get("invoices", [])],
            has_more=bool(d.get("hasMore", False)),
            is_truncated=bool(d.get("isTruncated", False)),
        )
