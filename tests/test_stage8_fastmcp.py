"""
tests/test_stage8_fastmcp.py
============================
Aşama 8: FastMCP Kurumsal Protokol Katmanı birim testleri.

Kurallar (.antigravityrules §1, §3, §4):
- Teamcenter PLM taklidi (tool_get_ebom) doğrulanır.
- SAP S/4HANA taklidi (tool_get_inventory) doğrulanır.
- Çekirdek simülasyon motoru sarmalaması (tool_run_impact_simulation) doğrulanır.
- FastMCP Tool protokol çağrıları doğrulanır.
"""

from __future__ import annotations

import pytest

from src.core.exceptions import PartNotFoundError
from src.mcp_servers.fastmcp_gateway import (
    cadence_mcp,
    mcp,
    tool_get_ebom,
    tool_get_inventory,
    tool_run_impact_simulation,
)
from src.schemas.simulation import EffectivityStrategy


# ===========================================================================
# 1. Sunucu Başlatma ve Tool Kayıt Testleri
# ===========================================================================

class TestFastMCPServerRegistration:
    """FastMCP sunucu tanımı ve kayıtlı araçların doğrulanması."""

    def test_server_instance_and_name(self) -> None:
        """Sunucu örneği ve adı doğrulanır."""
        assert cadence_mcp.name == "cadence_mcp"
        assert mcp is cadence_mcp

    @pytest.mark.asyncio
    async def test_tool_registration_list(self) -> None:
        """3 temel kurumsal aracın MCP'ye kayıtlı olduğu doğrulanır."""
        tools = await cadence_mcp.list_tools()
        tool_names = {t.name for t in tools}

        assert "tool_get_ebom" in tool_names
        assert "tool_get_inventory" in tool_names
        assert "tool_run_impact_simulation" in tool_names


# ===========================================================================
# 2. Teamcenter PLM EBOM Aracı Testleri (tool_get_ebom)
# ===========================================================================

class TestToolGetEBOM:
    """tool_get_ebom aracının doğrulanması."""

    def test_root_assembly_query(self) -> None:
        """Kök montaj (GBX-1000) sorgulandığında tüm parça ağacı döner."""
        result = tool_get_ebom("GBX-1000")

        assert result["part_number"] == "GBX-1000"
        assert result.part_number == "GBX-1000"
        assert "Şanzıman" in str(result["part_name"])
        assert result["source_system"] == "Teamcenter PLM"

        # Bileşen sayısı en az 10 olmalıdır (sample_ebom.csv'de 12 satır var)
        assert len(result["components"]) >= 10
        assert result["total_components"] >= 10

        # Dizi indeksleme ve iterasyon desteği
        assert result[0]["part_number"] == "GBX-1000"
        part_numbers = [item["part_number"] for item in result]
        assert "GBX-1100" in part_numbers
        assert "GB-PINION-02" in part_numbers

    def test_leaf_part_where_used_hierarchy(self) -> None:
        """Alt parça (GB-PINION-02) sorgulandığında Where-Used montajları döner."""
        result = tool_get_ebom("GB-PINION-02")

        assert result["part_number"] == "GB-PINION-02"
        where_used = result["where_used"]
        assert len(where_used) >= 1

        # Diferansiyel çıkış grubu (GBX-1300) Seviye 1 parent olmalı
        assert any(
            wu["parent_part_number"] == "GBX-1300" and wu["assembly_level"] == 1
            for wu in where_used
        )
        # Şanzıman ana montajı (GBX-1000) Seviye 2 parent olmalı
        assert any(
            wu["parent_part_number"] == "GBX-1000" and wu["assembly_level"] == 2
            for wu in where_used
        )

    def test_unknown_part_raises_part_not_found(self) -> None:
        """BOM'da olmayan parça için PartNotFoundError fırlatılır."""
        with pytest.raises(PartNotFoundError) as exc_info:
            tool_get_ebom("UNKNOWN-PLM-PART-999")
        assert exc_info.value.part_id == "UNKNOWN-PLM-PART-999"


# ===========================================================================
# 3. SAP S/4HANA Envanter Aracı Testleri (tool_get_inventory)
# ===========================================================================

class TestToolGetInventory:
    """tool_get_inventory aracının doğrulanması."""

    def test_existing_part_stock_and_lead_time(self) -> None:
        """SAP envanterinden stok adedi ve teslim süresi doğru döner."""
        inv = tool_get_inventory("GB-PINION-02")

        assert inv["part_number"] == "GB-PINION-02"
        assert inv.part_number == "GB-PINION-02"
        assert inv["stock_quantity"] == 55
        assert inv.stock_quantity == 55
        assert inv["lead_time_days"] == 30
        assert inv["location"] == "WH-GEAR-E05"
        assert inv["source_system"] == "SAP S/4HANA"
        assert inv["status"] == "AVAILABLE"

    def test_unknown_part_raises_part_not_found(self) -> None:
        """SAP'de bulunmayan parça için PartNotFoundError fırlatılır."""
        with pytest.raises(PartNotFoundError) as exc_info:
            tool_get_inventory("SAP-NOT-FOUND-000")
        assert exc_info.value.part_id == "SAP-NOT-FOUND-000"


# ===========================================================================
# 4. Çekirdek Simülasyon Aracı Testleri (tool_run_impact_simulation)
# ===========================================================================

class TestToolRunImpactSimulation:
    """tool_run_impact_simulation aracının doğrulanması."""

    def test_successful_simulation_run(self) -> None:
        """GB-PINION-02 için tolerans değişikliği simülasyonu başarıyla çalışır."""
        sim = tool_run_impact_simulation(
            eco_id="ECO-2024-TEST-01",
            part_number="GB-PINION-02",
            change_type="TOLERANCE",
        )

        assert sim["eco_id"] == "ECO-2024-TEST-01"
        assert sim.eco_id == "ECO-2024-TEST-01"
        assert sim["root_part_number"] == "GB-PINION-02"
        assert sim["change_type"] == "TOLERANCE"
        assert sim["source_system"] == "CadencePLM Simulation Engine"

        # Finansal ve operasyonel metrikler
        assert sim["total_affected_parts"] >= 1
        assert sim["total_scrap_cost"] == 7425.0  # 55 * 135.00 = 7425.0
        assert sim.total_scrap_cost == 7425.0
        assert sim["max_transition_lead_time_days"] == 30

        # Yürürlük ve geçiş planı
        assert sim["recommended_strategy"] == EffectivityStrategy.USE_UP_STOCK
        assert sim["run_out_days"] == 11  # 55 stok / 5 günlük tüketim = 11 gün

        # Where-Used montajları
        where_used = sim["where_used_parents"]
        assert len(where_used) >= 1
        assert any(wu["parent_part_number"] == "GBX-1300" for wu in where_used)

    def test_unknown_part_raises_part_not_found(self) -> None:
        """BOM'da olmayan parça için simülasyon PartNotFoundError fırlatır."""
        with pytest.raises(PartNotFoundError) as exc_info:
            tool_run_impact_simulation(
                eco_id="ECO-ERR",
                part_number="INVALID-PART-99",
                change_type="MATERIAL",
            )
        assert exc_info.value.part_id == "INVALID-PART-99"


# ===========================================================================
# 5. MCP Protokol Seviyesi Çağrı Testleri
# ===========================================================================

class TestFastMCPProtocolCalls:
    """FastMCP protokol katmanı üzerinden asenkron tool çağırma testleri."""

    @pytest.mark.asyncio
    async def test_protocol_call_inventory(self) -> None:
        """cadence_mcp.call_tool ile tool_get_inventory çağrısı."""
        result = await cadence_mcp.call_tool(
            "tool_get_inventory",
            {"part_number": "GB-PINION-02"},
        )
        assert result is not None
        # Sonucun metin içeriğinde beklenen parça numarası bulunmalı
        text_content = str(result)
        assert "GB-PINION-02" in text_content
        assert "55" in text_content

    @pytest.mark.asyncio
    async def test_protocol_call_ebom(self) -> None:
        """cadence_mcp.call_tool ile tool_get_ebom çağrısı."""
        result = await cadence_mcp.call_tool(
            "tool_get_ebom",
            {"part_number": "GB-PINION-02"},
        )
        assert result is not None
        text_content = str(result)
        assert "GB-PINION-02" in text_content
        assert "GBX-1300" in text_content

    @pytest.mark.asyncio
    async def test_protocol_call_simulation(self) -> None:
        """cadence_mcp.call_tool ile tool_run_impact_simulation çağrısı."""
        result = await cadence_mcp.call_tool(
            "tool_run_impact_simulation",
            {
                "eco_id": "ECO-ASYNC-01",
                "part_number": "GB-PINION-02",
                "change_type": "TOLERANCE",
            },
        )
        assert result is not None
        text_content = str(result)
        assert "ECO-ASYNC-01" in text_content
        assert "7425" in text_content
