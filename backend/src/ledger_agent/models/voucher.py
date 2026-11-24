"""憑證 OCR 結構化解析結果模型。

Python 學習重點：
- `Decimal` 用於金額計算，避免二進位浮點數誤差（例如 0.1 + 0.2 = 0.30000000000000004）。
- `Enum` 限制欄位只能出現合法的枚舉值，讓 AI 輸出與 JSON 結構更穩定。
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class VoucherType(str, Enum):
    """台灣基礎常見憑證類型。"""

    TRIPLICATE_INVOICE = "triplicate_invoice"  # 三聯式統一發票
    DUPLICATE_INVOICE = "duplicate_invoice"  # 二聯式統一發票
    ELECTRONIC_INVOICE = "electronic_invoice"  # 電子發票證明聯
    RECEIPT = "receipt"  # 普通收據 / 免用統一發票收據
    OTHER = "other"  # 其他憑證


class PaymentMethod(str, Enum):
    """憑證付款方式。"""

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    PETTY_CASH = "petty_cash"
    UNKNOWN = "unknown"


class VoucherLineItem(BaseModel):
    """憑證上的單一品項明細。"""

    description: str = Field(..., description="品項名稱或服務說明")
    quantity: Decimal = Field(default=Decimal("1"), description="數量")
    unit_price: Decimal | None = Field(default=None, description="單價")
    amount: Decimal = Field(..., description="小計金額")


class VoucherExtraction(BaseModel):
    """Stage 1 多模態 VLM 解析後的標準憑證 JSON 結構。"""

    voucher_type: VoucherType = Field(
        default=VoucherType.ELECTRONIC_INVOICE,
        description="憑證類型",
    )
    voucher_number: str | None = Field(
        default=None,
        description="發票號碼（例如 AB-12345678）或收據編號",
    )
    voucher_date: str | None = Field(
        default=None,
        description="憑證日期（統一轉為西元 YYYY-MM-DD）",
    )
    vendor_name: str = Field(..., description="賣方公司或店家名稱")
    vendor_tax_id: str | None = Field(
        default=None,
        description="賣方統一編號（8碼數字）",
    )
    buyer_name: str | None = Field(default=None, description="買方名稱")
    buyer_tax_id: str | None = Field(
        default=None,
        description="買方統一編號（8碼數字，若有記載）",
    )
    currency: str = Field(default="TWD", description="幣別，預設 TWD")
    subtotal: Decimal | None = Field(default=None, description="未稅銷售額")
    tax_amount: Decimal | None = Field(default=None, description="營業稅額")
    total_amount: Decimal = Field(..., description="含稅總計金額")
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.UNKNOWN,
        description="付款方式",
    )
    items: list[VoucherLineItem] = Field(
        default_factory=list,
        description="品項明細列表",
    )
    notes: str | None = Field(
        default=None,
        description="憑證備註、手寫註記或員工填寫的用途說明",
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="辨識信心分數 (0.0 ~ 1.0)",
    )
    raw_text: str | None = Field(
        default=None,
        description="憑證關鍵原始文字摘要（便於人工核對）",
    )
