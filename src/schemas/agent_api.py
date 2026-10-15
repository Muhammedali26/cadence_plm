"""
src/schemas/agent_api.py
========================
CadencePLM OpenAI Karar Ajanı REST API Veri Transfer Nesneleri (DTO).

Kurallar (.antigravityrules §3):
- Pydantic v2 (ConfigDict, Field) kullanılır.
- `Any` tipi kesinlikle yasaktır.
- Katı tip denetimi ve açıklayıcı alan tanımları.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentAnalyzeRequest(BaseModel):
    """
    Otonom ECO Karar Ajanı analiz istek modeli.

    Attributes
    ----------
    eco_text : str
        Kullanıcıdan gelen serbest metin ECO değişiklik talebi (en az 10 karakter).
    custom_context : str | None
        Opsiyonel ek bağlam veya talimatlar.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    eco_text: str = Field(
        ...,
        min_length=10,
        description="Serbest metin mühendislik değişiklik talebi (ECO)",
        examples=[
            "GB-PINION-02 pinyon dişlisinin temas yüzeyi toleransı daraltıldı, yeni revizyon B olarak güncellenecek."
        ],
    )
    custom_context: str | None = Field(
        default=None,
        description="Opsiyonel ek bağlam, öncelik veya fabrika kısıtları",
        examples=["Bursa fabrikasında stok tüketimi önceliklidir."],
    )


class AgentAnalyzeResponse(BaseModel):
    """
    Otonom ECO Karar Ajanı analiz yanıt modeli.

    Model çıktısı, deterministik motorların hesaplama sonuçları ve GPT-4o tarafından
    sentezlenen kurumsal karar raporunu bir arada taşır.
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )

    status: str = Field(
        default="SUCCESS",
        description="Analiz işlem durumu ('SUCCESS', 'ERROR')",
        examples=["SUCCESS"],
    )
    target_part_number: str = Field(
        ...,
        min_length=1,
        description="Analiz edilen hedef parça numarası",
        examples=["GB-PINION-02"],
    )
    change_type: str = Field(
        ...,
        min_length=1,
        description="Değişiklik türü (TOLERANCE, MATERIAL, DIMENSION vb.)",
        examples=["TOLERANCE"],
    )
    total_scrap_cost: float = Field(
        ...,
        ge=0.0,
        description="Kümülatif toplam hurda maliyeti USD",
        examples=[7425.0],
    )
    net_savings: float = Field(
        ...,
        ge=0.0,
        description="Hurdaya çıkarmak yerine rework ile kurtarma net tasarrufu USD",
        examples=[6311.25],
    )
    is_reworkable: bool = Field(
        ...,
        description="Parçanın hurda yerine talaşlı imalatla kurtarılabilir olup olmadığı",
        examples=[True],
    )
    recommended_strategy: str = Field(
        ...,
        min_length=1,
        description="Önerilen yürürlük ve geçiş stratejisi (USE_UP_STOCK veya IMMEDIATE_CUTOFF)",
        examples=["USE_UP_STOCK"],
    )
    run_out_days: int = Field(
        ...,
        ge=0,
        description="Stok tükenme gün sayısı (USE_UP stratejisi için)",
        examples=[11],
    )
    max_transition_lead_time_days: int = Field(
        ...,
        ge=0,
        description="Kritik yol kalıp ve tedarik teslim süresi (iş günü)",
        examples=[30],
    )
    where_used_chain: list[dict[str, object]] = Field(
        default_factory=list,
        description="Hedef parçanın bağlı olduğu tüm üst montaj hiyerarşisi",
    )
    tools_called: list[str] = Field(
        default_factory=list,
        description="Ajan tarafından analiz sırasında otonom tetiklenen motor araçları",
        examples=[
            [
                "tool_run_simulation",
                "tool_get_where_used",
                "tool_evaluate_rework",
                "tool_calculate_effectivity",
            ]
        ],
    )
    executive_summary: str = Field(
        ...,
        min_length=1,
        description="Üst yönetim ve IATF 16949 / PPAP karar özeti metni",
    )
