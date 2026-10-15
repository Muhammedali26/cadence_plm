"""
src/schemas/rework.py
=====================
Endüstriyel kurtarma (Rework vs. Scrap) veri transfer nesneleri.

Kurallar (.antigravityrules §2 & §3):
- Pydantic v2 (ConfigDict, Field) kullanılır.
- Float alanlar maliyet hesaplarında `round(val, 2)` hassasiyetindedir.
- `Any` tipi kesinlikle yasaktır.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReworkOperationType(StrEnum):
    """Yeniden işleme (rework) talaşlı imalat operasyon türleri."""

    CNC_TURNING = "CNC_TURNING"
    GRINDING    = "GRINDING"
    DRILLING    = "DRILLING"
    NONE        = "NONE"


class ReworkFeasibility(BaseModel):
    """
    Bir parçanın hurdaya ayrılmak yerine yeniden işlenip (rework) kurtarılabilirlik analizi.

    Attributes
    ----------
    is_reworkable : bool
        Parçanın yeniden işlenip kurtarılabilirliği.
    operation_type : str
        Uygulanacak operasyon türü ('CNC_TURNING', 'GRINDING', 'DRILLING', 'NONE').
    rework_cost_per_unit : float
        Birim başına yeniden işleme maliyeti USD (unit_cost * 0.15).
    net_savings : float
        Yeniden işleme sayesinde elde edilen net tasarruf USD ((unit_cost - rework_cost) * stock).
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )

    is_reworkable: bool = Field(
        ...,
        description="Parçanın hurda yerine yeniden işlenebilir olup olmadığı",
        examples=[True, False],
    )
    operation_type: str = Field(
        ...,
        description="Uygulanacak talaşlı imalat operasyonu (CNC_TURNING, GRINDING, DRILLING, NONE)",
        examples=["CNC_TURNING", "NONE"],
    )
    rework_cost_per_unit: float = Field(
        ...,
        ge=0.0,
        description="Birim parça başına yeniden işleme maliyeti USD (unit_cost * 0.15)",
        examples=[20.25],
    )
    net_savings: float = Field(
        ...,
        ge=0.0,
        description="Hurdaya çıkarmak yerine yeniden işleme ile sağlanan net tasarruf USD",
        examples=[6311.25],
    )
