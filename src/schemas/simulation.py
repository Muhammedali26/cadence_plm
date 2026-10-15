"""
src/schemas/simulation.py
=========================
ECO simülasyon sonuç veri transfer nesneleri.

Kurallar (.antigravityrules §3):
- Pydantic v2 (ConfigDict, Field) kullanılır.
- `Any` tipi kesinlikle yasaktır.
- Finansal değerler (scrap_cost, total_scrap_cost) float;
  engine katmanı `round(val, 2)` ile kilitler (§2).
- Bu şemalar yalnızca çıktı (response) modelidir — engine hesaplama
  sonuçları buraya dönüştürülür, tersi değil.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.rework import ReworkFeasibility


class EffectivityStrategy(StrEnum):
    """
    ECO yürürlük ve stok geçiş stratejisi.

    Values
    ------
    IMMEDIATE_CUTOFF
        Hemen kesinti: Yeni revizyon derhal devreye alınır, mevcut stok hurdaya çıkarılır.
    USE_UP_STOCK
        Stok tüketimi: Yeni revizyona geçiş öncesi mevcut stok tükenene kadar kullanılır.
    """

    IMMEDIATE_CUTOFF = "IMMEDIATE_CUTOFF"
    USE_UP_STOCK     = "USE_UP_STOCK"

    # Kolay erişim için alias
    USE_UP = "USE_UP_STOCK"


class WhereUsedDetail(BaseModel):
    """
    Bir alt parçanın kullanıldığı üst montaj bilgisi (Where-Used).

    Attributes
    ----------
    parent_part_number : str
        Üst parçanın/montajın numarası.
    parent_part_name : str
        Üst parçanın/montajın adı.
    assembly_level : int
        Hiyerarşik yukarı yönlü seviye (1: doğrudan üst montaj, 2: bir üstü, vb.).
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )

    parent_part_number: str = Field(
        ...,
        min_length=1,
        description="Üst parça/montaj numarası",
        examples=["GBX-1300"],
    )
    parent_part_name: str = Field(
        ...,
        min_length=1,
        description="Üst parça/montaj adı",
        examples=["Diferansiyel Çıkış Grubu"],
    )
    assembly_level: int = Field(
        ...,
        ge=1,
        description="Hiyerarşik yukarı yönlü seviye (1 = doğrudan parent)",
        examples=[1, 2],
    )


class PartImpactDetail(BaseModel):
    """
    Tek bir parçanın ECO simülasyonundan nasıl etkilendiğini gösterir.

    Attributes
    ----------
    part_number : str
        Etkilenen parçanın numarası.
    part_name : str
        Etkilenen parçanın adı.
    affected_stock : int
        ECO uygulandığında hurda olacak stok miktarı (>= 0).
    unit_cost : float
        Birim maliyet USD (>= 0). Engine `round(val, 2)` ile sabitler.
    scrap_cost : float
        Bu parça için hesaplanan toplam hurda maliyeti USD (>= 0).
        ``affected_stock * unit_cost`` — Engine katmanında hesaplanır.
    tooling_affected : bool
        Bu parçaya bağlı kalıp/aparat etkileniyor mu?
    supplier_id : str
        Tedarikçi kimliği.
    lead_time_days : int
        Yeniden tedarik/üretim süresi iş günü cinsinden (>= 0).

    Example
    -------
    >>> detail = PartImpactDetail(
    ...     part_number="P-042",
    ...     part_name="Side Bracket",
    ...     affected_stock=30,
    ...     unit_cost=12.50,
    ...     scrap_cost=375.00,
    ...     tooling_affected=True,
    ...     supplier_id="SUP-07",
    ...     lead_time_days=21,
    ... )
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )

    part_number: str = Field(
        ...,
        min_length=1,
        description="Etkilenen parçanın numarası",
        examples=["P-042"],
    )
    part_name: str = Field(
        ...,
        min_length=1,
        description="Etkilenen parçanın adı",
        examples=["Side Bracket"],
    )
    affected_stock: int = Field(
        ...,
        ge=0,
        description="Hurda olacak stok miktarı (>= 0)",
        examples=[30],
    )
    unit_cost: float = Field(
        ...,
        ge=0.0,
        description="Birim maliyet USD (>= 0)",
        examples=[12.50],
    )
    scrap_cost: float = Field(
        ...,
        ge=0.0,
        description="Toplam hurda maliyeti USD — engine round(val,2) ile sabitler",
        examples=[375.00],
    )
    tooling_affected: bool = Field(
        ...,
        description="Kalıp/aparat etkileniyor mu?",
        examples=[True, False],
    )
    supplier_id: str = Field(
        ...,
        min_length=1,
        description="Tedarikçi kimliği",
        examples=["SUP-07"],
    )
    lead_time_days: int = Field(
        ...,
        ge=0,
        description="Yeniden tedarik süresi iş günü cinsinden (>= 0)",
        examples=[21],
    )


class SimulationSummary(BaseModel):
    """
    Bir ECO talebinin tüm BOM ağacı üzerindeki kümülatif simülasyon sonucu.

    Bu model API yanıtının kökü olarak kullanılır ve
    ``src/engines/`` katmanının deterministik hesaplama çıktısını taşır.

    Attributes
    ----------
    eco_id : str
        Simülasyon yapılan ECO talebinin kimliği.
    root_part_number : str
        BOM traversal'ının başladığı kök parçanın numarası.
    total_affected_parts : int
        ECO'dan etkilenen toplam parça sayısı (>= 0).
    total_scrap_cost : float
        Tüm etkilenen parçaların kümülatif hurda maliyeti USD (>= 0).
        Engine `round(val, 2)` ile sabitler.
    total_impacted_toolings : int
        Etkilenen kalıp/aparat sayısı (>= 0).
    max_transition_lead_time_days : int
        Geçiş sürecindeki en uzun tedarik süresi iş günü cinsinden (>= 0).
        Kritik yol hesabında kullanılır.
    details : list[PartImpactDetail]
        Her etkilenen parça için ayrıntılı etki kaydı.

    Example
    -------
    >>> summary = SimulationSummary(
    ...     eco_id="ECO-2024-0042",
    ...     root_part_number="P-000",
    ...     total_affected_parts=5,
    ...     total_scrap_cost=1250.00,
    ...     total_impacted_toolings=2,
    ...     max_transition_lead_time_days=21,
    ...     details=[],
    ... )
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )

    eco_id: str = Field(
        ...,
        min_length=1,
        description="Simülasyon yapılan ECO kimliği",
        examples=["ECO-2024-0042"],
    )
    root_part_number: str = Field(
        ...,
        min_length=1,
        description="BOM traversal'ının başladığı kök parça numarası",
        examples=["P-000"],
    )
    total_affected_parts: int = Field(
        ...,
        ge=0,
        description="ECO'dan etkilenen toplam parça sayısı",
        examples=[5],
    )
    total_scrap_cost: float = Field(
        ...,
        ge=0.0,
        description="Kümülatif hurda maliyeti USD — engine round(val,2) ile sabitler",
        examples=[1250.00],
    )
    total_impacted_toolings: int = Field(
        ...,
        ge=0,
        description="Etkilenen kalıp/aparat sayısı",
        examples=[2],
    )
    max_transition_lead_time_days: int = Field(
        ...,
        ge=0,
        description="En uzun geçiş tedarik süresi (kritik yol) iş günü",
        examples=[21],
    )
    details: list[PartImpactDetail] = Field(
        default_factory=list,
        description="Her etkilenen parça için ayrıntılı etki kaydı",
    )
    where_used_parents: list[WhereUsedDetail] = Field(
        default_factory=list,
        description="Hedef parçanın bağlı olduğu tüm üst montajlar (Where-Used)",
    )
    recommended_strategy: EffectivityStrategy = Field(
        default=EffectivityStrategy.IMMEDIATE_CUTOFF,
        description="Önerilen yürürlük stratejisi",
    )
    run_out_days: int = Field(
        default=0,
        ge=0,
        description="USE_UP seçilirse stoğun biteceği gün sayısı",
    )
    rework_analysis: ReworkFeasibility | None = Field(
        default=None,
        description="Endüstriyel kurtarma (Rework vs. Scrap) analizi",
    )
