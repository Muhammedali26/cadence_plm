"""
src/schemas/eco.py
==================
ECO (Engineering Change Order) veri transfer nesneleri.

Kurallar (.antigravityrules §3):
- Pydantic v2 (ConfigDict, Field, Enum) kullanılır.
- `Any` tipi kesinlikle yasaktır.
- Serbest metin (raw_text) ayrıştırılamadığında engine/service katmanı
  `ECOParsingError` fırlatır (src/core/exceptions.py).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ECOChangeType(StrEnum):
    """
    ECO talebinin kapsadığı değişiklik kategorisi.

    Values
    ------
    TOLERANCE
        Boyutsal tolerans veya ölçü güncellemesi.
    MATERIAL
        Malzeme türü veya spesifikasyon değişikliği.
    GEOMETRY
        Form, şekil veya geometrik yeniden tasarım.
    OBSOLETE
        Parçanın üretim dışı bırakılması ve yerine geçecek parçanın
        tanımlanması.
    """

    TOLERANCE = "TOLERANCE"
    MATERIAL   = "MATERIAL"
    GEOMETRY   = "GEOMETRY"
    OBSOLETE   = "OBSOLETE"


class ECORequest(BaseModel):
    """
    Serbest metin ECO talebini yapılandırılmış forma dönüştüren DTO.

    Bu nesne ``src/services/`` katmanı tarafından LLM çıktısından
    veya API isteğinden doldurulur. Tüm alanlar zorunludur — eksik alan
    varsa ``ECOParsingError`` fırlatılmalıdır.

    Attributes
    ----------
    eco_id : str
        ECO talebinin benzersiz kimliği (ör. "ECO-2024-0042").
    raw_text : str
        Kullanıcıdan gelen işlenmemiş serbest metin.
        Ayrıştırma başarısız olursa ``ECOParsingError.raw_input``
        olarak taşınır.
    affected_part_number : str
        ECO'dan etkilenen birincil parça numarası.
    target_revision : str
        ECO uygulandıktan sonra parçanın alacağı yeni revizyon.
    change_type : ECOChangeType
        Değişiklik kategorisi.
    description : str
        ECO'nun kısa, insan tarafından yazılmış açıklaması.

    Example
    -------
    >>> req = ECORequest(
    ...     eco_id="ECO-2024-0042",
    ...     raw_text="Change bolt P-101 material from steel to titanium",
    ...     affected_part_number="P-101",
    ...     target_revision="Rev-C",
    ...     change_type=ECOChangeType.MATERIAL,
    ...     description="Steel → Titanium for weight reduction",
    ... )
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
        use_enum_values=True,   # JSON'da string olarak serialize edilir
    )

    eco_id: str = Field(
        ...,
        min_length=1,
        description="ECO talebinin benzersiz kimliği",
        examples=["ECO-2024-0042"],
    )
    raw_text: str = Field(
        ...,
        min_length=1,
        description="İşlenmemiş serbest metin ECO talebi",
        examples=["Change bolt P-101 material from steel to titanium"],
    )
    affected_part_number: str = Field(
        ...,
        min_length=1,
        description="ECO'dan etkilenen birincil parça numarası",
        examples=["P-101"],
    )
    target_revision: str = Field(
        ...,
        min_length=1,
        description="ECO sonrası hedef revizyon etiketi",
        examples=["Rev-C"],
    )
    change_type: ECOChangeType = Field(
        ...,
        description="Değişiklik kategorisi",
        examples=[ECOChangeType.MATERIAL],
    )
    description: str = Field(
        ...,
        min_length=1,
        description="ECO'nun kısa insan tarafından yazılmış açıklaması",
        examples=["Steel → Titanium for weight reduction"],
    )
