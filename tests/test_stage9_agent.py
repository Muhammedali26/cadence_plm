"""
tests/test_stage9_agent.py
==========================
Aşama 9: Gerçek OpenAI Tool-Calling / ReAct Karar Ajanı Birim Testleri.

Kurallar (.antigravityrules §1, §3, §4):
- Mock ve Regex fallback kaldırılmıştır. Canlı OpenAI API (gpt-4o) kullanılır.
- Sistem istemi, 4 deterministik motor aracı (tool_run_simulation, tool_get_where_used,
  tool_evaluate_rework, tool_calculate_effectivity) doğrulanır.
- Katı tip ve exception kontrolleri (CadencePLMException, ECOParsingError, PartNotFoundError).
- ReAct döngüsünün ve AgentAnalysisResult zengin modelinin doğrulanması.
"""

from __future__ import annotations

import pytest

from src.agents.eco_agent import AgentAnalysisResult, CadenceECOAgent
from src.core.exceptions import (
    CadencePLMException,
    ECOParsingError,
    PartNotFoundError,
)


# ===========================================================================
# 1. Ajan İlklendirme ve Konfigürasyon Testleri
# ===========================================================================

class TestCadenceECOAgentInit:
    """CadenceECOAgent ilklendirme, sistem istemi ve anahtar kontrolleri."""

    def test_system_prompt_content(self) -> None:
        """Ajan sistem isteminin 4 motor aracını ve rol tanımını içerdiği doğrulanır."""
        agent = CadenceECOAgent()
        expected_substrings = [
            "CadencePLM Kıdemli İmalat ve Değişiklik Yönetimi Ajanısın",
            "tool_run_simulation",
            "tool_get_where_used",
            "tool_evaluate_rework",
            "tool_calculate_effectivity",
            "net tasarruf odaklı kurumsal bir karar metni",
        ]
        for sub in expected_substrings:
            assert sub in agent.SYSTEM_PROMPT

    def test_invalid_api_key_raises_cadence_plm_exception(self) -> None:
        """Geçersiz veya sk- ile başlamayan API anahtarında CadencePLMException fırlatılmalıdır."""
        with pytest.raises(CadencePLMException) as exc_info:
            CadenceECOAgent(api_key="invalid-api-key-without-sk")
        assert "OPENAI_API_KEY" in exc_info.value.message


# ===========================================================================
# 2. Python Motor Araçlarının (OpenAI Tools) Doğrudan Birim Testleri
# ===========================================================================

class TestAgentEngineTools:
    """Ajanın içine bağlı deterministik motorların tool metotları."""

    @pytest.fixture()
    def agent(self) -> CadenceECOAgent:
        return CadenceECOAgent()

    def test_tool_run_simulation(self, agent: CadenceECOAgent) -> None:
        """tool_run_simulation deterministik simülasyon çıktısını doğrular."""
        res = agent.tool_run_simulation("GB-PINION-02", "TOLERANCE")
        assert res["status"] == "SUCCESS"
        assert res["part_number"] == "GB-PINION-02"
        assert res["total_scrap_cost"] == 7425.0
        assert res["total_affected_parts"] == 1
        assert res["total_impacted_toolings"] == 1
        assert res["max_transition_lead_time_days"] == 30

    def test_tool_run_simulation_nonexistent_part_raises(self, agent: CadenceECOAgent) -> None:
        """BOM'da olmayan parçada PartNotFoundError fırlatılmalıdır."""
        with pytest.raises(PartNotFoundError):
            agent.tool_run_simulation("GBX-NONEXISTENT", "TOLERANCE")

    def test_tool_get_where_used(self, agent: CadenceECOAgent) -> None:
        """tool_get_where_used bottom-up hiyerarşi zincirini döner."""
        res = agent.tool_get_where_used("GB-PINION-02")
        assert res["status"] == "SUCCESS"
        chain = res["where_used_chain"]
        assert len(chain) == 2
        assert chain[0]["parent_part_number"] == "GBX-1300"
        assert chain[1]["parent_part_number"] == "GBX-1000"

    def test_tool_evaluate_rework(self, agent: CadenceECOAgent) -> None:
        """tool_evaluate_rework talaşlı imalat kurtarma ve net tasarruf hesabı."""
        res = agent.tool_evaluate_rework(
            part_number="GB-PINION-02",
            unit_cost=135.0,
            stock_quantity=55,
            change_type="TOLERANCE",
        )
        assert res["status"] == "SUCCESS"
        assert res["is_reworkable"] is True
        assert res["operation_type"] == "CNC_TURNING"
        assert res["rework_cost_per_unit"] == 20.25
        assert res["net_savings"] == 6311.25

    def test_tool_calculate_effectivity(self, agent: CadenceECOAgent) -> None:
        """tool_calculate_effectivity optimum strateji ve run-out gün hesabı."""
        res = agent.tool_calculate_effectivity(
            stock_quantity=55,
            unit_cost=135.0,
            tooling_lead_time_days=30,
            daily_consumption_rate=5,
        )
        assert res["status"] == "SUCCESS"
        assert res["strategy"] == "USE_UP_STOCK"
        assert res["run_out_days"] == 11


# ===========================================================================
# 3. Hata Yönetimi ve İstisna Testleri
# ===========================================================================

class TestECOAgentExceptions:
    """Hatalı ve eksik girdilerde uygun domain exception kontrolleri."""

    @pytest.fixture()
    def agent(self) -> CadenceECOAgent:
        return CadenceECOAgent()

    def test_empty_string_raises_eco_parsing_error(self, agent: CadenceECOAgent) -> None:
        """Boş metin verildiğinde ECOParsingError fırlatılmalıdır."""
        with pytest.raises(ECOParsingError):
            agent.analyze_eco_unstructured("")

        with pytest.raises(ECOParsingError):
            agent.analyze_eco_unstructured("   ")

    def test_nonexistent_part_raises_part_not_found(self, agent: CadenceECOAgent) -> None:
        """BOM'da olmayan geçerli formatlı parça PartNotFoundError fırlatmalıdır."""
        with pytest.raises(PartNotFoundError):
            agent.analyze_eco_unstructured(
                "GBX-9999 olmayan parça toleransı değişti, revizyon B."
            )


# ===========================================================================
# 4. Gerçek OpenAI Tool-Calling / ReAct Uçtan Uca Entegrasyon Testi
# ===========================================================================

class TestRealOpenAIToolCalling:
    """Canlı OpenAI GPT-4o ReAct Tool-Calling döngüsü testi."""

    @pytest.fixture()
    def agent(self) -> CadenceECOAgent:
        return CadenceECOAgent()

    def test_pinion_tolerance_live_react_loop(self, agent: CadenceECOAgent) -> None:
        """GPT-4o serbest metni alıp araçları otonom çağırarak sentezlemelidir."""
        text = (
            "GB-PINION-02 ayna pinyon dişlisinin temas yüzeyi toleransı daraltıldı. "
            "Yeni revizyon B olarak güncellenecek."
        )
        res = agent.analyze_eco_unstructured(text)

        assert isinstance(res, dict)
        assert isinstance(res, AgentAnalysisResult)

        # Hedef parça ve değişiklik türü
        assert res["target_part_number"] == "GB-PINION-02"
        assert res.target_part_number == "GB-PINION-02"
        assert res["change_type"] == "TOLERANCE"

        # Simülasyon metrikleri (Deterministik araçlardan toplanan)
        assert res["total_scrap_cost"] == 7425.0
        assert res.total_scrap_cost == 7425.0
        assert res["recommended_strategy"] == "USE_UP_STOCK"
        assert res["run_out_days"] == 11
        assert res["is_reworkable"] is True
        assert res["net_savings"] == 6311.25

        # Araç çağırma zinciri kontrolü
        assert "tool_run_simulation" in res["tools_called"]

        # Doğal dilde yönetici karar metni
        assert len(str(res.executive_summary)) > 100
        assert "GB-PINION-02" in str(res.executive_summary)
