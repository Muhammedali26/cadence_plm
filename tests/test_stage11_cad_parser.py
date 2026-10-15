"""
tests/test_stage11_cad_parser.py
================================
Aşama 11: 3D CAD / STEP Dosya Metadata Ayrıştırıcısı Birim Testleri.

Test Senaryoları:
1. data/sample_gearbox.step dosyasını başarıyla ayrıştırma (Path, str path, io.StringIO, ham metin).
2. Hiyerarşik doğrulama: Kök montaj (GBX-1000) parent_part_number is None.
3. Alt montaj ve parça ilişkilerinin (GBX-1100, GBX-1200, GB-PINION-02 vb.) doğruluğu.
4. Çoklu kullanım (occurrence) adetlerinin doğru toplanması (GBX-1213 qty=2, GBX-1214 qty=2).
5. Revizyon etiketlerinin PRODUCT_DEFINITION_FORMATION üzerinden doğru okunması.
6. BOMTreeEngine ile doğrudan entegrasyon (parsed BOMItem listesi -> BOMTreeEngine).
7. Hata durumları (geçersiz dosya, eksik ISO-10303-21 başlığı, boş DATA bölümü -> BOMStructureError).
"""

from __future__ import annotations

import io
from pathlib import Path
import pandas as pd
import pytest

from src.core.exceptions import BOMStructureError
from src.engines.bom_tree import BOMTreeEngine
from src.engines.cad_parser import CADParser, parse_step_assembly
from src.schemas.bom import BOMItem

SAMPLE_STEP_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_gearbox.step"


class TestCADParser:
    """CADParser ve parse_step_assembly testleri."""

    def test_sample_gearbox_file_exists(self) -> None:
        """data/sample_gearbox.step dosyasının mevcut ve ISO standardında olduğunu doğrular."""
        assert SAMPLE_STEP_PATH.exists(), f"{SAMPLE_STEP_PATH} bulunamadı!"
        content = SAMPLE_STEP_PATH.read_text(encoding="utf-8")
        assert "ISO-10303-21;" in content
        assert "PRODUCT('GBX-1000'" in content
        assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE" in content

    def test_parse_step_assembly_from_path(self) -> None:
        """Path nesnesi ile STEP dosyasını ayrıştırma testi."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)
        assert isinstance(items, list)
        assert len(items) == 12

        # Tüm elemanların BOMItem örneği olduğunu doğrula
        for item in items:
            assert isinstance(item, BOMItem)

    def test_parse_step_assembly_from_string_path(self) -> None:
        """String dosya yolu ile STEP dosyasını ayrıştırma testi."""
        items = parse_step_assembly(str(SAMPLE_STEP_PATH))
        assert len(items) == 12

    def test_parse_step_assembly_from_string_io(self) -> None:
        """io.StringIO nesnesi ile STEP dosyasını bellek içi ayrıştırma testi."""
        content = SAMPLE_STEP_PATH.read_text(encoding="utf-8")
        buffer = io.StringIO(content)
        items = parse_step_assembly(buffer)
        assert len(items) == 12

    def test_parse_step_assembly_from_raw_text(self) -> None:
        """Doğrudan ham metin (string content) ile ayrıştırma testi."""
        content = SAMPLE_STEP_PATH.read_text(encoding="utf-8")
        items = parse_step_assembly(content)
        assert len(items) == 12

    def test_root_assembly_properties(self) -> None:
        """Kök parça GBX-1000'in parent_part_number'ının None olduğunu doğrular."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)
        root_items = [it for it in items if it.parent_part_number is None]
        assert len(root_items) == 1
        root = root_items[0]
        assert root.part_number == "GBX-1000"
        assert "Şanzıman" in root.part_name or "Gearbox" in root.part_name
        assert root.quantity == 1.0

    def test_assembly_hierarchy_and_parent_links(self) -> None:
        """Tüm parça-ebeveyn montaj ilişkilerinin doğruluğu."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)
        item_map = {it.part_number: it for it in items}

        # GBX-1000 -> GBX-1100, GBX-1200, GBX-1300
        assert item_map["GBX-1100"].parent_part_number == "GBX-1000"
        assert item_map["GBX-1200"].parent_part_number == "GBX-1000"
        assert item_map["GBX-1300"].parent_part_number == "GBX-1000"

        # GBX-1100 -> GBX-1110, GBX-1120
        assert item_map["GBX-1110"].parent_part_number == "GBX-1100"
        assert item_map["GBX-1120"].parent_part_number == "GBX-1100"

        # GBX-1200 -> GBX-1210
        assert item_map["GBX-1210"].parent_part_number == "GBX-1200"

        # GBX-1210 -> GBX-1211, GBX-1212, GBX-1213, GBX-1214
        assert item_map["GBX-1211"].parent_part_number == "GBX-1210"
        assert item_map["GBX-1212"].parent_part_number == "GBX-1210"
        assert item_map["GBX-1213"].parent_part_number == "GBX-1210"
        assert item_map["GBX-1214"].parent_part_number == "GBX-1210"

        # GBX-1300 -> GB-PINION-02
        assert item_map["GB-PINION-02"].parent_part_number == "GBX-1300"

    def test_multiple_occurrences_quantity_aggregation(self) -> None:
        """Çift kullanım (NAUO occurrence) içeren rulman ve segman adetlerini doğrular."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)
        item_map = {it.part_number: it for it in items}

        # GBX-1213 (Rulman): 2 adet occurrence tanımlıydı
        assert item_map["GBX-1213"].quantity == 2.0

        # GBX-1214 (Segman): 2 adet occurrence tanımlıydı
        assert item_map["GBX-1214"].quantity == 2.0

        # Diğer tekil parçaların quantity'si 1.0 olmalıdır
        assert item_map["GBX-1211"].quantity == 1.0
        assert item_map["GB-PINION-02"].quantity == 1.0

    def test_revisions_parsed_correctly(self) -> None:
        """Revizyon harflerinin (A, B, C) doğru ayrıştırıldığını doğrular."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)
        item_map = {it.part_number: it for it in items}

        assert item_map["GBX-1000"].revision == "A"
        assert item_map["GBX-1120"].revision == "B"  # Step'te 'B' verildi
        assert item_map["GBX-1210"].revision == "B"  # Step'te 'B' verildi
        assert item_map["GBX-1214"].revision == "C"  # Step'te 'C' verildi

    def test_integration_with_bom_tree_engine(self) -> None:
        """Ayrıştırılan BOMItem listesinin doğrudan BOMTreeEngine'e yüklenip Where-Used çalıştırması."""
        items = parse_step_assembly(SAMPLE_STEP_PATH)

        # BOMItem listesini DataFrame'e dönüştür
        records = [it.model_dump() for it in items]
        df = pd.DataFrame(records)

        tree = BOMTreeEngine()
        tree.load_from_dataframe(df)

        # GB-PINION-02 parçasının Where-Used zincirini sorgula:
        # GB-PINION-02 -> GBX-1300 -> GBX-1000
        where_used = tree.get_where_used("GB-PINION-02")
        assert len(where_used) == 2
        assert where_used[0].parent_part_number == "GBX-1300"
        assert where_used[1].parent_part_number == "GBX-1000"

        # GBX-1200 alt montajı etkilendiğinde alt dalları bul:
        # GBX-1200 -> GBX-1210 -> GBX-1211, GBX-1212, GBX-1213, GBX-1214
        affected = tree.get_affected_subassemblies("GBX-1200")
        affected_pns = {it.part_number for it in affected}
        assert "GBX-1210" in affected_pns
        assert "GBX-1211" in affected_pns
        assert "GBX-1213" in affected_pns

    def test_invalid_step_header_raises_bom_structure_error(self) -> None:
        """ISO-10303-21 başlığı olmayan bozuk dosyada BOMStructureError fırlatılmalıdır."""
        invalid_text = "HEADER; FILE_NAME('test.stp'); ENDSEC; DATA; ENDSEC;"
        with pytest.raises(BOMStructureError) as exc_info:
            parse_step_assembly(invalid_text)
        assert "ISO-10303-21" in str(exc_info.value.message)

    def test_empty_step_file_raises_bom_structure_error(self) -> None:
        """Tamamen boş içerikte BOMStructureError fırlatılmalıdır."""
        with pytest.raises(BOMStructureError):
            parse_step_assembly("")

    def test_missing_data_entities_raises_bom_structure_error(self) -> None:
        """DATA bölümünde entity bulunmayan dosyada BOMStructureError fırlatılmalıdır."""
        no_entities = "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
        with pytest.raises(BOMStructureError) as exc_info:
            parse_step_assembly(no_entities)
        assert "işlenebilir DATA entity kaydı bulunamadı" in str(exc_info.value.message)

    def test_custom_cad_parser_instance(self) -> None:
        """Özel bir CADParser örneğinin varsayılan değerlerle çalışabilmesi."""
        custom_parser = CADParser(ebom_reference_path=None)
        items = custom_parser.parse_step_assembly(
            SAMPLE_STEP_PATH,
            default_unit_cost=42.5,
            default_supplier_id="CUSTOM-SUPP",
        )
        assert len(items) == 12
        for it in items:
            assert it.unit_cost == 42.5
            assert it.supplier_id == "CUSTOM-SUPP"
