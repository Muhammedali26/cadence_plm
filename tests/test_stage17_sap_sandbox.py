"""
tests/test_stage17_sap_sandbox.py
=================================
Aşama 17: SAP Business Accelerator Hub (api.sap.com) Canlı Sandbox Entegrasyonu,
CSRF El Sıkışması, Çoklu Depo Agregasyonu ve Graceful Fallback Doğrulama Paketi.
"""

from __future__ import annotations

import pytest
import httpx
from starlette.testclient import TestClient

from src.connectors.sap_odata_client import (
    DEFAULT_EXCHANGE_RATES_TO_USD,
    EXCLUDED_STORAGE_LOCATIONS,
    SAPODataClient,
)
from src.core.config import Settings, settings
from src.core.exceptions import SAPAuthenticationError, SAPConnectionError
from src.main import app
from src.schemas.inventory import InventoryItem


class TestStage17SAPSandboxAndAdapter:
    """Aşama 17 SAP S/4HANA Cloud Sandbox ve Gelişmiş Adaptör Testleri."""

    def test_settings_sap_configuration(self) -> None:
        """SAP kurumsal ortam değişkenlerinin yapılandırması."""
        assert hasattr(settings, "SAP_ODATA_BASE_URL")
        assert hasattr(settings, "SAP_API_KEY")
        assert hasattr(settings, "SAP_USE_SANDBOX")
        assert "API_MATERIAL_STOCK_SRV" in settings.SAP_ODATA_BASE_URL

    def test_sandbox_vs_onprem_headers(self) -> None:
        """Sandbox modunda 'ApiKey', On-prem/Mock modunda 'X-SAP-API-Key' başlığı kullanılmalı."""
        sandbox_client = SAPODataClient(
            api_key="TEST-SANDBOX-KEY-123",
            use_sandbox=True,
        )
        sb_headers = sandbox_client._get_headers()
        assert sb_headers["ApiKey"] == "TEST-SANDBOX-KEY-123"
        assert "X-SAP-API-Key" not in sb_headers

        mock_client = SAPODataClient(
            api_key="LOCAL-MOCK-KEY-456",
            use_sandbox=False,
        )
        mock_headers = mock_client._get_headers()
        assert mock_headers["X-SAP-API-Key"] == "LOCAL-MOCK-KEY-456"
        assert "ApiKey" not in mock_headers

    def test_csrf_token_handshake_sync_and_async(self) -> None:
        """CSRF Token el sıkışması (x-csrf-token fetch)."""
        with TestClient(app) as tc:
            client = SAPODataClient(client=tc, fallback_on_error=True)
            token = client.fetch_csrf_token()
            assert token is not None and len(token) > 0

    @pytest.mark.asyncio
    async def test_csrf_token_handshake_async(self) -> None:
        """Asenkron CSRF Token el sıkışması."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            client = SAPODataClient(async_client=ac, fallback_on_error=True)
            token = await client.fetch_csrf_token_async()
            assert token is not None and len(token) > 0

    def test_multistorage_aggregation_and_quarantine_filtering(self) -> None:
        """Çoklu depo (LGORT) sonuçlarında karantina ve hurda (SCRP, QUAR, BLOCK) filtrelenmeli."""
        multi_location_payload = {
            "d": {
                "Material": "GB-PINION-02",
                "to_MatlStkInAcctMod": {
                    "results": [
                        {"LGORT": "WH-USABLE-1", "LABST": "45.000"},
                        {"LGORT": "SCRP", "LABST": "20.000"},         # Filtrelenmeli
                        {"LGORT": "WH-USABLE-2", "LABST": "35.000"},
                        {"LGORT": "QUARANTINE", "LABST": "12.000"},   # Filtrelenmeli
                        {"LGORT": "BLOCKED", "LABST": "6.000"},       # Filtrelenmeli
                        {"LGORT": "DEFECT", "LABST": "4.000"},        # Filtrelenmeli
                    ]
                },
                "PLIFZ": "30",
                "STPRS": "135.00",
                "WAERS": "USD",
            }
        }

        client = SAPODataClient()
        item = client._map_odata_to_inventory_item("GB-PINION-02", multi_location_payload)

        # 45 + 35 = 80 (SCRP, QUARANTINE, BLOCKED, DEFECT elendi)
        assert item.stock_quantity == 80
        assert "WH-USABLE-1" in item.location
        assert "WH-USABLE-2" in item.location
        assert "SCRP" not in item.location
        assert "DEFECT" not in item.location

    def test_single_quarantine_location_yields_zero_stock(self) -> None:
        """Tekil kayıt hurda/karantina deposuysa stok 0 olmalı."""
        quarantine_payload = {
            "d": {
                "MATNR": "GB-SCRAP-PART",
                "LABST": "100.000",
                "LGORT": "SCRP",
                "STPRS": "50.00",
                "WAERS": "USD",
                "PLIFZ": "10",
            }
        }
        client = SAPODataClient()
        item = client._map_odata_to_inventory_item("GB-SCRAP-PART", quarantine_payload)
        assert item.stock_quantity == 0
        assert "EXCLUDED" in item.location

    def test_currency_conversion_and_normalization(self) -> None:
        """Farklı para birimlerinde (EUR, TRY, JPY) güvenli kur normalizasyonu."""
        client = SAPODataClient()
        eur_payload = {
            "d": {
                "MATNR": "GB-TEST-EUR",
                "LABST": "50.000",
                "STPRS": "100.00",
                "WAERS": "EUR",
                "PLIFZ": "14",
                "LGORT": "WH-EUR",
            }
        }
        item_eur = client._map_odata_to_inventory_item("GB-TEST-EUR", eur_payload)
        assert item_eur.stock_quantity == 50
        assert item_eur.lead_time_days == 14

        # Bilinmeyen para biriminde de çökmemeli (varsayılan 1.0 çarpanı)
        unknown_curr_payload = {
            "d": {
                "MATNR": "GB-TEST-XYZ",
                "LABST": "10.000",
                "STPRS": "500.00",
                "WAERS": "XYZ",
                "PLIFZ": "7",
                "LGORT": "WH-XYZ",
            }
        }
        item_xyz = client._map_odata_to_inventory_item("GB-TEST-XYZ", unknown_curr_payload)
        assert item_xyz.stock_quantity == 10

    def test_graceful_fallback_on_network_or_auth_failure(self) -> None:
        """Sandbox bağlantı hatası veya eksik API anahtarında sistem çökmemeli, yerel emülatöre düşmeli."""
        # fallback_on_error=True ile hatalı URL ve key verildiğinde
        resilient_client = SAPODataClient(
            base_url="https://invalid-sandbox-subdomain.api.sap.com",
            api_key="INVALID_KEY",
            use_sandbox=True,
            fallback_on_error=True,
            timeout=1.0,
            max_retries=1,
        )

        item = resilient_client.get_material_stock("GB-PINION-02")
        assert isinstance(item, InventoryItem)
        assert item.part_number == "GB-PINION-02"
        assert item.stock_quantity == 55  # Yerel emülatördeki stok
        assert "FALLBACK" in item.location

    def test_404_material_not_found_raises_without_fallback(self) -> None:
        """fallback_on_error=False iken parça bulunamadığında PartNotFoundError fırlatılmalı."""
        from src.core.exceptions import PartNotFoundError

        # Local mock TestClient ile olmayan bir parça sorgula
        mock_client = TestClient(app)
        client = SAPODataClient(
            base_url="http://testserver/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV",
            api_key="SAP-ODATA-KEY-2024",
            fallback_on_error=False,
            client=mock_client,
        )

        with pytest.raises(PartNotFoundError) as exc_info:
            client.get_material_stock("NON-EXISTENT-PART-999")
        assert "NON-EXISTENT-PART-999" in str(exc_info.value)

    def test_404_material_not_found_graceful_fallback(self) -> None:
        """fallback_on_error=True iken parça bulunamadığında güvenli emülatör verisine düşmeli."""
        mock_client = TestClient(app)
        client = SAPODataClient(
            base_url="http://testserver/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV",
            api_key="SAP-ODATA-KEY-2024",
            fallback_on_error=True,
            client=mock_client,
        )

        item = client.get_material_stock("NON-EXISTENT-PART-999")
        assert isinstance(item, InventoryItem)
        assert item.part_number == "NON-EXISTENT-PART-999"
        assert item.stock_quantity >= 0
        assert "FALLBACK" in item.location

    def test_tg11_standard_demo_material_mapping(self) -> None:
        """TG11 standart SAP S/4HANA Cloud demo parçasının emülatör/adaptör eşlemesi doğrulanır."""
        mock_client = TestClient(app)
        client = SAPODataClient(
            base_url="http://testserver/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV",
            api_key="SAP-ODATA-KEY-2024",
            fallback_on_error=False,
            client=mock_client,
        )

        item = client.get_material_stock("TG11")
        assert isinstance(item, InventoryItem)
        assert item.part_number == "TG11"
        assert item.stock_quantity == 154345
        assert item.location == "171R"

