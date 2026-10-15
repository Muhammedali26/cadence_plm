"""
src/engines/impact_calculator.py
=================================
ECO etki hesaplama motoru — tamamen deterministik, saf Python.

Kurallar (.antigravityrules §1 & §2):
- Sıfır LLM / harici API bağımlılığı. Sıfır FastAPI bağımlılığı.
- Hurda maliyeti: `scrap_cost = round(stock_quantity * unit_cost, 2)`.
- Negatif stok veya tanımsız maliyet → `CostCalculationError` (sessiz pass yasak).
- `Any` tipi kullanımı yasaktır.
"""

from __future__ import annotations

from src.core.exceptions import CostCalculationError
from src.schemas.bom import BOMItem
from src.schemas.inventory import InventoryItem
from src.schemas.simulation import PartImpactDetail, SimulationSummary


class ImpactCalculatorEngine:
    """
    Etkilenen BOM parçaları ve envanter verisiyle hurda maliyetini hesaplar.

    Bu sınıfın yalnızca tek bir public metodu vardır: ``calculate``.
    Tüm hesaplama o metot içinde, yan etkisiz (side-effect free) biçimde
    gerçekleşir; nesne durumu (state) tutulmaz.

    Deterministik Garantiler
    ------------------------
    - Aynı girdi her zaman aynı çıktıyı üretir.
    - Float yuvarlama: ``round(val, 2)`` — §2 gereği 2 ondalık basamak.
    - Toplam hurda maliyeti bireysel ``scrap_cost`` değerlerin toplamıdır;
      ayrıca ``round(toplam, 2)`` uygulanır.
    """

    def calculate(
        self,
        eco_id: str,
        root_part_number: str,
        affected_parts: list[BOMItem],
        inventory_map: dict[str, InventoryItem],
    ) -> SimulationSummary:
        """
        Etkilenen parçalar üzerinde hurda maliyeti ve kalıp etkisi hesaplar.

        Parameters
        ----------
        eco_id : str
            Simülasyon yapılan ECO talebinin kimliği.
        root_part_number : str
            BOM traversal'ının başladığı kök parçanın numarası.
        affected_parts : list[BOMItem]
            ``BOMTreeEngine.get_affected_subassemblies`` çıktısı.
        inventory_map : dict[str, InventoryItem]
            Parça numarası → InventoryItem eşlemesi.
            Envanterde bulunmayan parçalar sıfır stokla değerlendirilir
            ve bu durum loglanır.

        Returns
        -------
        SimulationSummary
            Tüm etkilenen parçaların kümülatif simülasyon sonucu.

        Raises
        ------
        CostCalculationError
            - Herhangi bir parçanın `unit_cost` değeri negatifse.
            - Herhangi bir parçanın `stock_quantity` değeri negatifse.
              (Schema katmanı `ge=0` ile birincil savunma hattını sağlar;
               bu kontrol engine'in ikinci savunma hattıdır.)

        Notes
        -----
        Kalıp etkisi (tooling impact): Bir parçanın `tooling_id` alanı
        ``None`` olmayan benzersiz değerlerin kümesiyle hesaplanır.
        Aynı `tooling_id`'ye sahip birden fazla parça olsa bile yalnızca
        bir kez sayılır.
        """
        details: list[PartImpactDetail] = []
        unique_toolings: set[str] = set()
        max_lead_time: int = 0

        for part in affected_parts:
            # --- Maliyet doğrulama (engine ikinci savunma hattı) ---
            if part.unit_cost < 0:
                raise CostCalculationError(
                    "Negatif birim maliyet hesaplanamaz",
                    detail=f"part_number={part.part_number!r}, unit_cost={part.unit_cost}",
                )

            # --- Envanter kaydını bul; yoksa sıfır stok varsay ---
            inventory_item: InventoryItem | None = inventory_map.get(part.part_number)

            if inventory_item is not None:
                stock: int = inventory_item.stock_quantity
                lead_time: int = inventory_item.lead_time_days
            else:
                # Envanterde kayıt yok → stok sıfır, tedarik süresi sıfır
                stock = 0
                lead_time = 0

            # --- Engine seviyesi negatif stok koruması ---
            if stock < 0:
                raise CostCalculationError(
                    "Negatif stok miktarı hesaplanamaz",
                    detail=f"part_number={part.part_number!r}, stock_quantity={stock}",
                )

            # --- Hurda maliyeti hesabı (§2: round 2 ondalık) ---
            scrap_cost: float = round(stock * part.unit_cost, 2)
            locked_unit_cost: float = round(part.unit_cost, 2)

            # --- Kalıp etkisi ---
            is_tooling_affected: bool = part.tooling_id is not None
            if part.tooling_id is not None:
                unique_toolings.add(part.tooling_id)

            # --- Kritik yol (maksimum lead time) ---
            if lead_time > max_lead_time:
                max_lead_time = lead_time

            details.append(
                PartImpactDetail(
                    part_number=part.part_number,
                    part_name=part.part_name,
                    affected_stock=stock,
                    unit_cost=locked_unit_cost,
                    scrap_cost=scrap_cost,
                    tooling_affected=is_tooling_affected,
                    supplier_id=part.supplier_id,
                    lead_time_days=lead_time,
                )
            )

        # --- Kümülatif toplamlar ---
        total_scrap: float = round(
            sum(d.scrap_cost for d in details),
            2,
        )

        return SimulationSummary(
            eco_id=eco_id,
            root_part_number=root_part_number,
            total_affected_parts=len(details),
            total_scrap_cost=total_scrap,
            total_impacted_toolings=len(unique_toolings),
            max_transition_lead_time_days=max_lead_time,
            details=details,
        )

    # Esnek kullanım için alias
    calculate_impact = calculate
