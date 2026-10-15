"""
src/schemas/bom.py
==================
BOM (Bill of Materials) veri transfer nesneleri.

Kurallar (.antigravityrules §3):
- Pydantic v2 (ConfigDict, Field) kullanılır.
- `Any` tipi kesinlikle yasaktır.
- Finansal değerler (unit_cost) float; engine katmanında `round(val, 2)`
  ile sabitlenir (§2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BOMItem(BaseModel):
    """
    BOM ağacındaki tek bir satırı temsil eder.

    Attributes
    ----------
    part_number : str
        Parçanın benzersiz numarası (ör. "P-001-A").
    part_name : str
        İnsan tarafından okunabilir parça adı.
    revision : str
        Mevcut revizyon etiketleri (ör. "Rev-B", "03").
    parent_part_number : str | None
        Üst parçanın numarası. Kök parçalarda ``None``.
    quantity : float
        Bu alt parçadan kaç adet kullanıldığı (kesirli miktar desteklenir).
    unit_cost : float
        Birim maliyet (USD). Engine katmanı ``round(val, 2)`` ile kilitler.
    supplier_id : str
        Tedarikçi kimliği.
    tooling_id : str | None
        Bu parçaya özel kalıp/aparat kimliği; yoksa ``None``.

    Example
    -------
    >>> item = BOMItem(
    ...     part_number="P-001",
    ...     part_name="Main Frame",
    ...     revision="Rev-A",
    ...     parent_part_number=None,
    ...     quantity=1.0,
    ...     unit_cost=150.75,
    ...     supplier_id="SUP-10",
    ...     tooling_id="T-001",
    ... )
    """

    model_config = ConfigDict(
        frozen=True,          # Immutable DTO — engine'lar kopyayla çalışır
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    part_number: str = Field(
        ...,
        min_length=1,
        description="Benzersiz parça numarası",
        examples=["P-001-A"],
    )
    part_name: str = Field(
        ...,
        min_length=1,
        description="İnsan tarafından okunabilir parça adı",
        examples=["Main Frame"],
    )
    revision: str = Field(
        ...,
        min_length=1,
        description="Revizyon etiketi",
        examples=["Rev-B", "03"],
    )
    parent_part_number: str | None = Field(
        default=None,
        description="Üst parça numarası; kök parçalarda None",
        examples=["P-000", None],
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Kullanım miktarı (> 0)",
        examples=[1.0, 2.5],
    )
    unit_cost: float = Field(
        ...,
        ge=0.0,
        description="Birim maliyet USD cinsinden (>= 0)",
        examples=[150.75],
    )
    supplier_id: str = Field(
        ...,
        min_length=1,
        description="Tedarikçi kimliği",
        examples=["SUP-10"],
    )
    tooling_id: str | None = Field(
        default=None,
        description="Kalıp/aparat kimliği; yoksa None",
        examples=["T-001", None],
    )
