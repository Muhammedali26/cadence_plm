"""
tests/test_engines.py
=====================
BOMTreeEngine ve ImpactCalculatorEngine için matematiksel ve iş mantığı birim testleri.

Kural (.antigravityrules §4):
- Her motor fonksiyonu için matematiksel doğrulama testi zorunludur.
- Otomotiv şanzıman montajı (data/sample_ebom.csv, data/sample_inventory.csv) üzerinden
  uçtan uca deterministik etki doğrulaması yapılır.
- Döngüsel bağımlılık (DAG cycle) durumunda BOMStructureError fırlatıldığı teyit edilir.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from src.core.exceptions import (
    BOMStructureError,
    CostCalculationError,
    PartNotFoundError,
)
from src.engines.bom_tree import BOMTreeEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.schemas.bom import BOMItem
from src.schemas.inventory import InventoryItem
from src.schemas.simulation import SimulationSummary


# ---------------------------------------------------------------------------
# Dizin ve Veri Yolu Sabitleri
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_EBOM_PATH = DATA_DIR / "sample_ebom.csv"
SAMPLE_INVENTORY_PATH = DATA_DIR / "sample_inventory.csv"


# ---------------------------------------------------------------------------
# Yardımcı Fonksiyonlar ve Fixture'lar
# ---------------------------------------------------------------------------

def _load_inventory_csv(path: Path) -> dict[str, InventoryItem]:
    """CSV dosyasından InventoryItem haritası yükler."""
    df = pd.read_csv(path, dtype=str)
    inventory_map: dict[str, InventoryItem] = {}
    for _, row in df.iterrows():
        item = InventoryItem(
            part_number=str(row["part_number"]).strip(),
            stock_quantity=int(row["stock_quantity"]),
            lead_time_days=int(row["lead_time_days"]),
            location=str(row["location"]).strip(),
        )
        inventory_map[item.part_number] = item
    return inventory_map


def _make_mock_bom_df() -> pd.DataFrame:
    """3 seviyeli basit sentetik BOM DataFrame'i."""
    return pd.DataFrame(
        {
            "part_number": ["P-000", "P-001", "P-002", "P-003"],
            "part_name": ["Root", "Arm", "Bracket", "Pin"],
            "revision": ["Rev-A", "Rev-A", "Rev-B", "Rev-A"],
            "parent_part_number": [None, "P-000", "P-000", "P-001"],
            "quantity": [1.0, 2.0, 1.0, 4.0],
            "unit_cost": [500.0, 150.0, 80.0, 12.5],
            "supplier_id": ["S-01", "S-02", "S-03", "S-02"],
            "tooling_id": [None, "T-01", "T-02", None],
        }
    )


def _make_mock_inventory_map() -> dict[str, InventoryItem]:
    """Sentetik envanter haritası."""
    return {
        "P-000": InventoryItem(part_number="P-000", stock_quantity=10, lead_time_days=0, location="WH-A"),
        "P-001": InventoryItem(part_number="P-001", stock_quantity=30, lead_time_days=14, location="WH-B"),
        "P-002": InventoryItem(part_number="P-002", stock_quantity=20, lead_time_days=21, location="WH-C"),
        "P-003": InventoryItem(part_number="P-003", stock_quantity=100, lead_time_days=7, location="WH-B"),
    }


@pytest.fixture()
def mock_engine() -> BOMTreeEngine:
    e = BOMTreeEngine()
    e.load_from_dataframe(_make_mock_bom_df())
    return e


@pytest.fixture()
def calc_engine() -> ImpactCalculatorEngine:
    return ImpactCalculatorEngine()


@pytest.fixture()
def gearbox_engine() -> BOMTreeEngine:
    """data/sample_ebom.csv dosyasını yükleyen motor fixture'ı."""
    e = BOMTreeEngine()
    e.load_from_csv(str(SAMPLE_EBOM_PATH))
    return e


@pytest.fixture()
def gearbox_inventory() -> dict[str, InventoryItem]:
    """data/sample_inventory.csv dosyasından üretilen envanter haritası."""
    return _load_inventory_csv(SAMPLE_INVENTORY_PATH)


# ===========================================================================
# 1. Döngüsel Bağımlılık (Circular Dependency) Testleri
# ===========================================================================

class TestCircularDependencyDetection:
    """BOM hiyerarşisinde döngüsel bağımlılık tespit testleri."""

    def test_direct_two_node_cycle_raises_error(self) -> None:
        """P1 -> P2 -> P1 doğrudan iki düğümlü döngü BOMStructureError fırlatmalı."""
        cyclic_data = pd.DataFrame(
            [
                {
                    "part_number": "P1",
                    "part_name": "Part 1",
                    "revision": "A",
                    "parent_part_number": "P2",
                    "quantity": 1.0,
                    "unit_cost": 10.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                },
                {
                    "part_number": "P2",
                    "part_name": "Part 2",
                    "revision": "A",
                    "parent_part_number": "P1",
                    "quantity": 1.0,
                    "unit_cost": 20.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                },
            ]
        )
        engine = BOMTreeEngine()
        with pytest.raises(BOMStructureError, match="Döngüsel"):
            engine.load_from_dataframe(cyclic_data)

    def test_indirect_three_node_cycle_raises_error(self) -> None:
        """A -> B -> C -> A dolaylı üç düğümlü döngü tespit edilmeli."""
        cyclic_data = pd.DataFrame(
            [
                {
                    "part_number": "A",
                    "part_name": "Part A",
                    "revision": "A",
                    "parent_part_number": "C",
                    "quantity": 1.0,
                    "unit_cost": 10.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                },
                {
                    "part_number": "B",
                    "part_name": "Part B",
                    "revision": "A",
                    "parent_part_number": "A",
                    "quantity": 1.0,
                    "unit_cost": 15.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                },
                {
                    "part_number": "C",
                    "part_name": "Part C",
                    "revision": "A",
                    "parent_part_number": "B",
                    "quantity": 1.0,
                    "unit_cost": 20.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                },
            ]
        )
        engine = BOMTreeEngine()
        with pytest.raises(BOMStructureError, match="Döngüsel"):
            engine.load_from_dataframe(cyclic_data)

    def test_self_referencing_node_raises_error(self) -> None:
        """Kendine referans veren parça (P -> P) döngü hatası fırlatmalı."""
        self_loop_data = pd.DataFrame(
            [
                {
                    "part_number": "P_SELF",
                    "part_name": "Self Loop Part",
                    "revision": "A",
                    "parent_part_number": "P_SELF",
                    "quantity": 1.0,
                    "unit_cost": 100.0,
                    "supplier_id": "S1",
                    "tooling_id": None,
                }
            ]
        )
        engine = BOMTreeEngine()
        with pytest.raises(BOMStructureError):
            engine.load_from_dataframe(self_loop_data)


# ===========================================================================
# 2. Şanzıman / Dişli Mili Değişim ve Hurda Maliyeti Testleri
# ===========================================================================

class TestGearboxShaftImpactAnalysis:
    """
    Otomotiv 'Şanzıman / Dişli Kutusu (Gearbox Assembly)' veri seti doğrulamaları.
    Dişli Mili (GBX-1210) değiştiğinde alt montajların ve hurda maliyetinin hesabı.
    """

    def test_sample_ebom_file_exists_and_loads(self, gearbox_engine: BOMTreeEngine) -> None:
        """data/sample_ebom.csv dosyası 12 satırlık şanzıman verisini eksiksiz yüklemelidir."""
        assert gearbox_engine.part_count == 12

    def test_gearbox_shaft_affected_subassemblies(self, gearbox_engine: BOMTreeEngine) -> None:
        """
        Dişli mili (GBX-1210) değiştiğinde yalnızca kendisi ve alt parçaları etkilenmelidir:
        - GBX-1210: Ana Dişli Mili (kök)
        - GBX-1211: 1. Vites Tahrik Dişlisi
        - GBX-1212: 2. Vites Tahrik Dişlisi
        - GBX-1213: Konik Masuralı Rulman
        - GBX-1214: Emniyet Segmanı
        Gövde (GBX-1100 vb.) ve Diferansiyel (GBX-1300 vb.) etkilenmemelidir!
        """
        affected = gearbox_engine.get_affected_subassemblies("GBX-1210")
        affected_pns = [p.part_number for p in affected]

        # Toplam etkilenen parça sayısı 5 olmalıdır
        assert len(affected_pns) == 5

        # Kök parça listenin ilk elemanıdır (BFS garantisi)
        assert affected_pns[0] == "GBX-1210"

        # Tam küme doğrulaması
        expected_set = {"GBX-1210", "GBX-1211", "GBX-1212", "GBX-1213", "GBX-1214"}
        assert set(affected_pns) == expected_set

        # Üst veya kardeş montajların etkilenmediği teyit edilir
        assert "GBX-1000" not in set(affected_pns)
        assert "GBX-1100" not in set(affected_pns)
        assert "GBX-1200" not in set(affected_pns)
        assert "GBX-1300" not in set(affected_pns)

    def test_gearbox_shaft_scrap_cost_and_impact_accuracy(
        self,
        gearbox_engine: BOMTreeEngine,
        gearbox_inventory: dict[str, InventoryItem],
        calc_engine: ImpactCalculatorEngine,
    ) -> None:
        """
        Dişli mili (GBX-1210) değişikliği simülasyonu:
        Hurda Maliyeti Doğrulaması:
        - GBX-1210: 50 adet * 180.00 USD = 9,000.00 USD
        - GBX-1211: 120 adet * 75.00 USD = 9,000.00 USD
        - GBX-1212: 90 adet * 82.50 USD  = 7,425.00 USD
        - GBX-1213: 200 adet * 26.00 USD = 5,200.00 USD
        - GBX-1214: 450 adet * 4.50 USD  = 2,025.00 USD
        ------------------------------------------------
        Toplam Hurda Maliyeti = 32,650.00 USD

        Kalıp Etkisi:
        - GBX-1210: TLG-SFT-121
        - GBX-1211: TLG-GR-1211
        - GBX-1212: TLG-GR-1212
        - GBX-1213: None
        - GBX-1214: None
        Toplam Etkilenen Kalıp = 3 adet

        Geçiş Süresi (Kritik Yol):
        - max(28, 21, 21, 14, 7) = 28 gün
        """
        affected = gearbox_engine.get_affected_subassemblies("GBX-1210")
        summary: SimulationSummary = calc_engine.calculate(
            eco_id="ECO-GEARBOX-001",
            root_part_number="GBX-1210",
            affected_parts=affected,
            inventory_map=gearbox_inventory,
        )

        assert summary.eco_id == "ECO-GEARBOX-001"
        assert summary.root_part_number == "GBX-1210"
        assert summary.total_affected_parts == 5

        # Bireysel parça hurda maliyetleri
        detail_map = {d.part_number: d for d in summary.details}
        assert detail_map["GBX-1210"].scrap_cost == 9000.00
        assert detail_map["GBX-1211"].scrap_cost == 9000.00
        assert detail_map["GBX-1212"].scrap_cost == 7425.00
        assert detail_map["GBX-1213"].scrap_cost == 5200.00
        assert detail_map["GBX-1214"].scrap_cost == 2025.00

        # Kümülatif toplam hurda maliyeti
        assert summary.total_scrap_cost == 32650.00

        # Kalıp etkileri
        assert detail_map["GBX-1210"].tooling_affected is True
        assert detail_map["GBX-1211"].tooling_affected is True
        assert detail_map["GBX-1212"].tooling_affected is True
        assert detail_map["GBX-1213"].tooling_affected is False
        assert detail_map["GBX-1214"].tooling_affected is False
        assert summary.total_impacted_toolings == 3

        # Kritik yol teslim süresi
        assert summary.max_transition_lead_time_days == 28

    def test_gearbox_root_assembly_simulation(
        self,
        gearbox_engine: BOMTreeEngine,
        gearbox_inventory: dict[str, InventoryItem],
        calc_engine: ImpactCalculatorEngine,
    ) -> None:
        """Tüm şanzıman montajı (GBX-1000) değiştiğinde tüm 12 parça etkilenmelidir."""
        affected = gearbox_engine.get_affected_subassemblies("GBX-1000")
        assert len(affected) == 12

        summary = calc_engine.calculate(
            eco_id="ECO-GEARBOX-FULL",
            root_part_number="GBX-1000",
            affected_parts=affected,
            inventory_map=gearbox_inventory,
        )
        assert summary.total_affected_parts == 12
        assert summary.total_scrap_cost > 32650.00
        assert summary.max_transition_lead_time_days == 45


# ===========================================================================
# 3. BOMTreeEngine Ek Temel Fonksiyon Testleri
# ===========================================================================

class TestBOMTreeEngineGeneral:
    """BOMTreeEngine genel yükleme ve gezinti kontrolleri."""

    def test_load_from_csv_stringio(self) -> None:
        """io.StringIO bellek içi akış kontrolü (.antigravityrules §5)."""
        csv_text = (
            "part_number,part_name,revision,parent_part_number,quantity,unit_cost,supplier_id,tooling_id\n"
            "M1,Main,A,,1.0,100.0,S1,T1\n"
            "M2,Sub,A,M1,2.0,25.0,S2,\n"
        )
        engine = BOMTreeEngine()
        engine.load_from_csv(io.StringIO(csv_text))
        assert engine.part_count == 2
        assert engine.get_part("M1").part_name == "Main"

    def test_missing_column_raises_bom_structure_error(self) -> None:
        bad_df = pd.DataFrame(
            {
                "part_number": ["X1"],
                "part_name": ["Part X"],
                # unit_cost ve diğer sütunlar eksik
            }
        )
        engine = BOMTreeEngine()
        with pytest.raises(BOMStructureError, match="zorunlu sütunlar"):
            engine.load_from_dataframe(bad_df)

    def test_nonexistent_part_raises_part_not_found(self, mock_engine: BOMTreeEngine) -> None:
        with pytest.raises(PartNotFoundError) as exc_info:
            mock_engine.get_affected_subassemblies("NONEXISTENT_PART")
        assert exc_info.value.part_id == "NONEXISTENT_PART"


# ===========================================================================
# 4. ImpactCalculatorEngine Temel Fonksiyon Testleri
# ===========================================================================

class TestImpactCalculatorGeneral:
    """Maliyet hesaplama sınır ve hata testleri."""

    def test_zero_stock_yields_zero_scrap(self, calc_engine: ImpactCalculatorEngine) -> None:
        part = BOMItem(
            part_number="P-ZERO",
            part_name="Zero Stock Part",
            revision="A",
            parent_part_number=None,
            quantity=1.0,
            unit_cost=250.00,
            supplier_id="SUP-1",
        )
        inv = {
            "P-ZERO": InventoryItem(
                part_number="P-ZERO",
                stock_quantity=0,
                lead_time_days=10,
                location="WH-0",
            )
        }
        summary = calc_engine.calculate(
            eco_id="ECO-Z",
            root_part_number="P-ZERO",
            affected_parts=[part],
            inventory_map=inv,
        )
        assert summary.total_scrap_cost == 0.00
        assert summary.details[0].scrap_cost == 0.00

    def test_missing_inventory_treated_as_zero_stock(self, calc_engine: ImpactCalculatorEngine) -> None:
        part = BOMItem(
            part_number="P-UNTRACKED",
            part_name="Untracked Part",
            revision="A",
            parent_part_number=None,
            quantity=1.0,
            unit_cost=100.00,
            supplier_id="SUP-1",
        )
        summary = calc_engine.calculate(
            eco_id="ECO-U",
            root_part_number="P-UNTRACKED",
            affected_parts=[part],
            inventory_map={},  # Boş envanter
        )
        assert summary.details[0].affected_stock == 0
        assert summary.details[0].scrap_cost == 0.00

    def test_negative_unit_cost_raises_cost_calculation_error(
        self, calc_engine: ImpactCalculatorEngine
    ) -> None:
        """Birim maliyet negatif olduğunda motor CostCalculationError fırlatmalı."""
        bad_part = BOMItem.model_construct(
            part_number="P-NEG",
            part_name="Negative Cost Part",
            revision="A",
            parent_part_number=None,
            quantity=1.0,
            unit_cost=-50.0,
            supplier_id="SUP-1",
            tooling_id=None,
        )
        with pytest.raises(CostCalculationError, match="Negatif birim maliyet"):
            calc_engine.calculate(
                eco_id="ECO-ERR",
                root_part_number="P-NEG",
                affected_parts=[bad_part],
                inventory_map={},
            )

    def test_duplicate_tooling_ids_counted_once(self, calc_engine: ImpactCalculatorEngine) -> None:
        """Aynı kalıbı paylaşan parçalar tek bir etkilenen kalıp olarak sayılmalıdır."""
        parts = [
            BOMItem(
                part_number="P-T1",
                part_name="Tool Part 1",
                revision="A",
                parent_part_number=None,
                quantity=1.0,
                unit_cost=10.0,
                supplier_id="S1",
                tooling_id="TOOL-SHARED",
            ),
            BOMItem(
                part_number="P-T2",
                part_name="Tool Part 2",
                revision="A",
                parent_part_number="P-T1",
                quantity=1.0,
                unit_cost=20.0,
                supplier_id="S2",
                tooling_id="TOOL-SHARED",
            ),
        ]
        summary = calc_engine.calculate(
            eco_id="ECO-TOOL",
            root_part_number="P-T1",
            affected_parts=parts,
            inventory_map={},
        )
        assert summary.total_impacted_toolings == 1
