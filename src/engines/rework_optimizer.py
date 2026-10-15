"""
src/engines/rework_optimizer.py
===============================
Endüstriyel Kurtarma (Rework vs. Scrap) Optimizasyon Motoru.

Kurallar (.antigravityrules §1 & §2):
- Saf, deterministik Python kodu. Sıfır LLM, sıfır FastAPI bağımlılığı.
- Finansal değerler `round(val, 2)` ile 2 ondalık basamağa kilitlenir.
- Negatif stok veya maliyet değerlerinde `CostCalculationError` fırlatılır.
- `Any` tipi kesinlikle yasaktır.
"""

from __future__ import annotations

import re

from src.core.exceptions import CostCalculationError
from src.schemas.eco import ECOChangeType
from src.schemas.rework import ReworkFeasibility, ReworkOperationType

# İşlenebilir metal parçaları (mil, dişli, burç vb.) tespit etmek için anahtar kelimeler
_MACHINABLE_PATTERNS: tuple[str, ...] = (
    r"pinion",
    r"shaft",
    r"gear",
    r"mil",
    r"di[sş]li",
    r"pinyon",
    r"[sş]aft",
    r"bur[cç]",
    r"bush",
    r"rot\b",
    r"aks\b",
    r"axle",
    r"spindle",
    r"hub\b",
    r"flan[sş]",
    r"sft",
    r"\bgr\b",
)

# Yeniden işleme (CNC torna vb.) uygun olmayan parçalar (conta, rulman, segman vb.)
_NON_REWORKABLE_PATTERNS: tuple[str, ...] = (
    r"seal",
    r"conta",
    r"o-ring",
    r"gasket",
    r"rulman",
    r"bearing",
    r"segman",
    r"circlip",
    r"fastener",
    r"bolt",
    r"c[iı]vata",
    r"somun",
    r"nut",
    r"pul",
    r"washer",
)


class ReworkOptimizerEngine:
    """
    Bir ECO değişikliğinde parçanın hurdaya ayrılmak yerine yeniden işlenip
    (rework) kurtarılabilirliğini ve ekonomik tasarrufunu hesaplayan motor.

    Endüstriyel Mantık:
    -------------------
    1. Değişiklik tipi 'TOLERANCE' veya 'DIMENSION' ise ve parça mil/dişli/burç
       gibi işlenebilir metal ise (`GB-PINION`, `GB-SHAFT` vb.):
       - is_reworkable = True
       - operation_type = 'CNC_TURNING'
       - rework_cost_per_unit = unit_cost * 0.15 (Birim maliyetin %15'i)
       - net_savings = (unit_cost - rework_cost_per_unit) * stock_quantity
    2. Değişiklik tipi 'MATERIAL' ise kurtarma imkansızdır (is_reworkable = False,
       hurda kaçınılmaz).
    """

    def is_machinable_metal(
        self,
        part_number: str,
        part_name: str | None = None,
    ) -> bool:
        """
        Parçanın CNC torna/freze ile yeniden işlenebilir metal (mil/dişli/burç vb.)
        olup olmadığını belirler.
        """
        combined = f"{part_number} {part_name or ''}".lower()

        # Önce işlenemez (conta, rulman, segman vb.) kontrolü
        for pattern in _NON_REWORKABLE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return False

        # İşlenebilir metal parça kontrolü
        for pattern in _MACHINABLE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return True

        return False

    def evaluate_rework(
        self,
        part_number: str,
        unit_cost: float,
        stock_quantity: int | None = None,
        change_type: str | ECOChangeType = "TOLERANCE",
        part_name: str | None = None,
        **kwargs: object,
    ) -> ReworkFeasibility:
        """
        Verilen parça ve ECO parametreleri için yeniden işleme fizibilitesini hesaplar.

        Parameters
        ----------
        part_number : str
            Parça numarası (örn. 'GB-PINION-02').
        unit_cost : float
            Birim maliyet USD.
        stock_quantity : int | None
            Mevcut SAP stok miktarı. (kwargs üzerinden 'stock_qty' de kabul edilir).
        change_type : str | ECOChangeType
            Değişiklik tipi ('TOLERANCE', 'DIMENSION', 'MATERIAL', vb.).
        part_name : str | None
            Parça adı (isteğe bağlı).

        Returns
        -------
        ReworkFeasibility
            Kurtarılabilirlik, operasyon türü, birim maliyet ve net tasarruf.

        Raises
        ------
        CostCalculationError
            Negatif stok veya negatif birim maliyet durumunda.
        """
        # Esnek stok miktarı çözümlemesi
        if stock_quantity is None:
            stock_quantity = int(kwargs.get("stock_qty", 0))  # type: ignore[arg-type]

        # Negatif değer koruması (.antigravityrules §2 & §3)
        if unit_cost < 0.0:
            raise CostCalculationError(
                "Negatif birim maliyet kabul edilemez",
                detail=f"part_number={part_number!r}, unit_cost={unit_cost}",
            )
        if stock_quantity < 0:
            raise CostCalculationError(
                "Negatif stok miktarı kabul edilemez",
                detail=f"part_number={part_number!r}, stock_quantity={stock_quantity}",
            )

        # Değişiklik tipini normalize et
        type_str = (
            change_type.value
            if isinstance(change_type, ECOChangeType)
            else str(change_type)
        ).strip().upper()

        # 1. Kural: TOLERANCE veya DIMENSION ve işlenebilir metal parça
        if type_str in ("TOLERANCE", "DIMENSION") and self.is_machinable_metal(
            part_number, part_name
        ):
            rework_cost_per_unit = round(unit_cost * 0.15, 2)
            net_savings = round(
                (unit_cost - rework_cost_per_unit) * stock_quantity,
                2,
            )
            # Net tasarruf negatif olamaz
            if net_savings < 0.0:
                net_savings = 0.0

            return ReworkFeasibility(
                is_reworkable=True,
                operation_type=ReworkOperationType.CNC_TURNING.value,
                rework_cost_per_unit=rework_cost_per_unit,
                net_savings=net_savings,
            )

        # 2. Kural: MATERIAL veya işlenemez parça durumunda kurtarma imkansız
        return ReworkFeasibility(
            is_reworkable=False,
            operation_type=ReworkOperationType.NONE.value,
            rework_cost_per_unit=0.0,
            net_savings=0.0,
        )

    # -----------------------------------------------------------------------
    # Alias Yöntemler
    # -----------------------------------------------------------------------

    def calculate_rework_feasibility(
        self,
        part_number: str,
        unit_cost: float,
        stock_quantity: int | None = None,
        change_type: str | ECOChangeType = "TOLERANCE",
        part_name: str | None = None,
        **kwargs: object,
    ) -> ReworkFeasibility:
        """evaluate_rework için alias."""
        return self.evaluate_rework(
            part_number=part_number,
            unit_cost=unit_cost,
            stock_quantity=stock_quantity,
            change_type=change_type,
            part_name=part_name,
            **kwargs,
        )

    def calculate(
        self,
        part_number: str,
        unit_cost: float,
        stock_quantity: int | None = None,
        change_type: str | ECOChangeType = "TOLERANCE",
        part_name: str | None = None,
        **kwargs: object,
    ) -> ReworkFeasibility:
        """evaluate_rework için alias."""
        return self.evaluate_rework(
            part_number=part_number,
            unit_cost=unit_cost,
            stock_quantity=stock_quantity,
            change_type=change_type,
            part_name=part_name,
            **kwargs,
        )

    def evaluate(
        self,
        part_number: str,
        unit_cost: float,
        stock_quantity: int | None = None,
        change_type: str | ECOChangeType = "TOLERANCE",
        part_name: str | None = None,
        **kwargs: object,
    ) -> ReworkFeasibility:
        """evaluate_rework için alias."""
        return self.evaluate_rework(
            part_number=part_number,
            unit_cost=unit_cost,
            stock_quantity=stock_quantity,
            change_type=change_type,
            part_name=part_name,
            **kwargs,
        )
