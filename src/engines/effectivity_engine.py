"""
src/engines/effectivity_engine.py
=================================
ECO yürürlük (effectivity) ve stok geçiş planlama motoru.

Kurallar (.antigravityrules §1 & §2):
- Deterministik saf Python kodudur. Sıfır LLM/AI ve sıfır FastAPI bağımlılığı.
- Stok tükenme süresi (run-out days):
    run_out_days = ceil(stock_quantity / daily_consumption_rate)
- Karar Kuralı:
    run_out_days <= tooling_lead_time ise:
        Strateji: USE_UP_STOCK (stok tükenene kadar kullan)
        Geçiş Süresi: run_out_days
        Hurda Maliyeti: 0.00 USD (stok sıfır hurda ile doğal olarak tüketilir)
    Aksi halde:
        Strateji: IMMEDIATE_CUTOFF (derhal kesinti ve hurdaya ayırma)
        Geçiş Süresi: 0 gün (veya anlık)
        Hurda Maliyeti: round(stock_quantity * unit_cost, 2)
- Sıfıra bölme (günlük tüketim hızı <= 0) veya negatif girdi -> CostCalculationError
"""

from __future__ import annotations

import math

from src.core.exceptions import CostCalculationError
from src.schemas.simulation import EffectivityStrategy


class EffectivityEngine:
    """
    Stok miktarı, birim maliyet, kalıp teslim süresi ve günlük tüketim hızına göre
    en uygun ECO geçiş stratejisini belirleyen deterministik motor.
    """

    def __init__(
        self,
        stock_quantity: int | None = None,
        daily_consumption_rate: int = 5,
        unit_cost: float | None = None,
        default_daily_consumption_rate: int | None = None,
    ) -> None:
        rate = (
            default_daily_consumption_rate
            if default_daily_consumption_rate is not None
            else daily_consumption_rate
        )
        if rate <= 0:
            raise CostCalculationError(
                "Varsayılan günlük tüketim hızı sıfırdan büyük olmalıdır",
                detail=f"daily_consumption_rate={rate}",
            )
        self.default_stock_quantity: int | None = stock_quantity
        self.default_daily_consumption_rate: int = rate
        self.default_unit_cost: float | None = unit_cost

    def calculate_transition_plan(
        self,
        stock_quantity: int | None = None,
        unit_cost: float | None = None,
        tooling_lead_time_days: int | None = None,
        daily_consumption_rate: int | None = None,
        tooling_lead_time: int | None = None,
        sanitize_dirty_data: bool = False,
    ) -> tuple[EffectivityStrategy, int, float]:
        """
        Stok tükenme süresi ve kalıp teslim süresini karşılaştırarak geçiş planı üretir.

        Parameters
        ----------
        stock_quantity : int | None
            Mevcut envanter stok adedi (>= 0).
        unit_cost : float | None
            Birim maliyet USD (>= 0).
        tooling_lead_time_days : int | None
            Yeni kalıp teslim süresi iş günü (>= 0).
        daily_consumption_rate : int | None
            Günlük parça tüketim hızı (> 0). Verilmezse 5 varsayılır.
        tooling_lead_time : int | None
            tooling_lead_time_days için alias parametre.
        sanitize_dirty_data : bool
            Kirli fabrika verisi zırhı; True ise negatif stokları 0'a sabitler,
            None/NaN maliyetleri 0.0 kabul eder ve sıfır tüketim hızında ZeroDivisionError önler.

        Returns
        -------
        tuple[EffectivityStrategy, int, float]
            (Önerilen Strateji, Geçiş/Tükenme Gün Sayısı, Tahmini Hurda Maliyeti)

        Raises
        ------
        CostCalculationError
            Negatif stok, negatif birim maliyet veya geçersiz tüketim hızı durumunda (sanitize_dirty_data=False ise).
        """
        # Değer çözümleme (parametre veya __init__ varsayılanı)
        stock = stock_quantity if stock_quantity is not None else self.default_stock_quantity
        cost = unit_cost if unit_cost is not None else self.default_unit_cost
        rate = daily_consumption_rate if daily_consumption_rate is not None else self.default_daily_consumption_rate

        lead_time = (
            tooling_lead_time_days
            if tooling_lead_time_days is not None
            else (tooling_lead_time if tooling_lead_time is not None else 0)
        )

        # Kirli veri koruma zırhı (sanitize_dirty_data=True)
        if sanitize_dirty_data:
            if stock is None or stock < 0:
                stock = max(0, stock if stock is not None else 0)
            if cost is None or (isinstance(cost, float) and (math.isnan(cost) or math.isinf(cost))):
                cost = 0.0
            if rate is None or rate <= 0:
                rate = self.default_daily_consumption_rate if self.default_daily_consumption_rate > 0 else 5
            if lead_time < 0:
                lead_time = 0

        if stock is None:
            raise CostCalculationError(
                "Stok miktarı belirtilmelidir",
                detail="stock_quantity parametresi None olamaz",
            )
        if cost is None:
            raise CostCalculationError(
                "Birim maliyet belirtilmelidir",
                detail="unit_cost parametresi None olamaz",
            )

        # Pozisyonel argüman yer değişimi toleransı (cost float, lead_time int)
        if isinstance(cost, int) and isinstance(lead_time, float):
            cost, lead_time = float(lead_time), int(cost)

        # Doğrulamalar (.antigravityrules §2)
        if stock < 0:
            raise CostCalculationError(
                "Negatif stok miktarı ile yürürlük hesaplanamaz",
                detail=f"stock_quantity={stock}",
            )

        if cost < 0:
            raise CostCalculationError(
                "Negatif birim maliyet ile yürürlük hesaplanamaz",
                detail=f"unit_cost={cost}",
            )

        if rate <= 0:
            raise CostCalculationError(
                "Günlük tüketim hızı sıfır veya negatif olamaz",
                detail=f"daily_consumption_rate={rate}",
            )

        if lead_time < 0:
            raise CostCalculationError(
                "Kalıp teslim süresi negatif olamaz",
                detail=f"lead_time={lead_time}",
            )

        # Stok tükenme süresi (run-out days)
        if stock == 0:
            run_out_days = 0
        else:
            run_out_days = math.ceil(stock / rate)

        # Karar mantığı
        if run_out_days <= lead_time:
            # Stok kalıp tesliminden önce tükenir -> USE_UP_STOCK (0.00 USD hurda)
            return (EffectivityStrategy.USE_UP_STOCK, run_out_days, 0.0)

        # Stok daha uzun sürede tükenir -> IMMEDIATE_CUTOFF
        scrap = round(stock * cost, 2)
        return (EffectivityStrategy.IMMEDIATE_CUTOFF, 0, scrap)

    def calculate_transition_plan_safe(
        self,
        stock_quantity: int | None = None,
        unit_cost: float | None = None,
        tooling_lead_time_days: int | None = None,
        daily_consumption_rate: int | None = None,
        tooling_lead_time: int | None = None,
    ) -> tuple[EffectivityStrategy, int, float]:
        """Kirli fabrika verilerine karşı zırhlı güvenli yürürlük hesaplayıcı."""
        return self.calculate_transition_plan(
            stock_quantity=stock_quantity,
            unit_cost=unit_cost,
            tooling_lead_time_days=tooling_lead_time_days,
            daily_consumption_rate=daily_consumption_rate,
            tooling_lead_time=tooling_lead_time,
            sanitize_dirty_data=True,
        )

    # Esnek kullanım ve alias
    calculate_effectivity = calculate_transition_plan
