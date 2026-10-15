"""
src/schemas/inventory.py
========================
Envanter veri transfer nesneleri.

Kurallar (.antigravityrules §3):
- Pydantic v2 (ConfigDict, Field) kullanılır.
- `Any` tipi kesinlikle yasaktır.
- Negatif stok fiziksel olarak imkânsızdır; engine katmanı `CostCalculationError`
  fırlatır (src/core/exceptions.py). Schema sınırında `ge=0` ile ikinci savunma
  hattı oluşturulur.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InventoryItem(BaseModel):
    """
    Tek bir parçanın envanter kaydını temsil eder.

    Attributes
    ----------
    part_number : str
        Parçanın BOM ile eşleşen benzersiz numarası.
    stock_quantity : int
        Mevcut stok adedi (>= 0). Negatif değer engine katmanında
        ``CostCalculationError`` fırlatır.
    lead_time_days : int
        Tedarik veya üretim süresi (iş günü). Simülasyon geçiş
        süresinin hesaplanmasında kullanılır.
    location : str
        Fiziksel depo/raf konumu (ör. "WH-A/Rack-12").

    Example
    -------
    >>> item = InventoryItem(
    ...     part_number="P-001",
    ...     stock_quantity=250,
    ...     lead_time_days=14,
    ...     location="WH-A/Rack-12",
    ... )
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    part_number: str = Field(
        ...,
        min_length=1,
        description="BOM ile eşleşen benzersiz parça numarası",
        examples=["P-001"],
    )
    stock_quantity: int = Field(
        ...,
        ge=0,
        description="Mevcut stok adedi (>= 0)",
        examples=[250, 0],
    )
    lead_time_days: int = Field(
        ...,
        ge=0,
        description="Tedarik/üretim süresi iş günü cinsinden (>= 0)",
        examples=[14],
    )
    location: str = Field(
        ...,
        min_length=1,
        description="Fiziksel depo/raf konumu",
        examples=["WH-A/Rack-12"],
    )
