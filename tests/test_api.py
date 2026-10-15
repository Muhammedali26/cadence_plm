"""
tests/test_api.py
=================
FastAPI API katmanı entegrasyon testleri (httpx.AsyncClient ile).

Kural (.antigravityrules §1 & §4):
- API katmanı uçtan uca multipart dosya yükleme ve simülasyon akışını doğrular.
- Başarılı simülasyon (200), ayrıştırılamayan ECO (422), bulunamayan parça (404),
  ve döngüsel/hatalı BOM yükleme (400) durumları test edilir.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_EBOM_PATH = DATA_DIR / "sample_ebom.csv"
SAMPLE_INVENTORY_PATH = DATA_DIR / "sample_inventory.csv"


@pytest.fixture()
def transport() -> ASGITransport:
    return ASGITransport(app=app)


# ===========================================================================
# 1. Başarılı Simülasyon Testleri (HTTP 200)
# ===========================================================================

@pytest.mark.asyncio
async def test_simulate_gearbox_shaft_success(transport: ASGITransport) -> None:
    """
    POST /api/v1/simulate endpoint'ine gerçek şanzıman verileriyle istek atılır.
    - 5 etkilenen parça
    - 32,650.00 USD hurda maliyeti
    - 3 kalıp
    - 28 gün lead time
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_EBOM_PATH, "rb") as ebom_f, open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("sample_ebom.csv", ebom_f, "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {
                "eco_text": "GBX-1210 ana dişli milinin toleransını revize ediyoruz, yeni rev C olacak."
            }
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 200
    res_json = resp.json()

    assert res_json["root_part_number"] == "GBX-1210"
    assert res_json["total_affected_parts"] == 5
    assert res_json["total_scrap_cost"] == 32650.00
    assert res_json["total_impacted_toolings"] == 3
    assert res_json["max_transition_lead_time_days"] == 28
    assert len(res_json["details"]) == 5


@pytest.mark.asyncio
async def test_simulate_pinion_success(transport: ASGITransport) -> None:
    """GB-PINION-02 için POST /api/v1/simulate başarılı yanıt dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_EBOM_PATH, "rb") as ebom_f, open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("sample_ebom.csv", ebom_f, "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {
                "eco_text": "GB-PINION-02 parçasında tolerans revizyonu yapıldı, yeni revizyon B."
            }
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["root_part_number"] == "GB-PINION-02"
    assert res_json["total_affected_parts"] == 1
    assert res_json["total_scrap_cost"] == 7425.00


# ===========================================================================
# 2. Hata Senaryoları (HTTP 422, 404, 400)
# ===========================================================================

@pytest.mark.asyncio
async def test_simulate_unparseable_eco_text_returns_422(transport: ASGITransport) -> None:
    """Anlamsız serbest metin gönderildiğinde global handler HTTP 422 dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_EBOM_PATH, "rb") as ebom_f, open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("sample_ebom.csv", ebom_f, "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {"eco_text": "Hava bugün çok güzel, kahve içelim."}
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 422
    res_json = resp.json()
    assert res_json["error"] == "ECOParsingError"


@pytest.mark.asyncio
async def test_simulate_unknown_part_returns_404(transport: ASGITransport) -> None:
    """BOM'da bulunmayan parça içeren ECO gönderildiğinde HTTP 404 dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_EBOM_PATH, "rb") as ebom_f, open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("sample_ebom.csv", ebom_f, "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {"eco_text": "P-UNKNOWN-999 parçasında tolerans revizyonu yapıldı, yeni rev B."}
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 404
    res_json = resp.json()
    assert res_json["error"] == "PartNotFoundError"
    assert res_json["part_id"] == "P-UNKNOWN-999"


@pytest.mark.asyncio
async def test_simulate_cyclic_bom_returns_400(transport: ASGITransport) -> None:
    """Döngüsel bağımlılık içeren bozuk BOM yüklendiğinde HTTP 400 dönmelidir."""
    cyclic_csv = (
        "part_number,part_name,revision,parent_part_number,quantity,unit_cost,supplier_id,tooling_id\n"
        "CYC-1,Part 1,A,CYC-2,1.0,50.0,S1,T1\n"
        "CYC-2,Part 2,A,CYC-1,1.0,50.0,S1,T1\n"
    ).encode("utf-8")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("cyclic.csv", cyclic_csv, "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {"eco_text": "CYC-1 parçasında tolerans revizyonu, yeni rev B."}
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 400
    res_json = resp.json()
    assert res_json["error"] == "BOMStructureError"


@pytest.mark.asyncio
async def test_simulate_empty_file_returns_400(transport: ASGITransport) -> None:
    """Boş dosya yüklendiğinde HTTP 400 dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(SAMPLE_INVENTORY_PATH, "rb") as inv_f:
            files = {
                "ebom_file": ("empty.csv", b"", "text/csv"),
                "inventory_file": ("sample_inventory.csv", inv_f, "text/csv"),
            }
            data = {"eco_text": "GBX-1210 revizyon B tolerans."}
            resp = await client.post("/api/v1/simulate", files=files, data=data)

    assert resp.status_code == 400


# ===========================================================================
# 3. Sistem Sağlık Endpoint Testleri
# ===========================================================================

@pytest.mark.asyncio
async def test_health_check_endpoint(transport: ASGITransport) -> None:
    """GET /health 200 dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(transport: ASGITransport) -> None:
    """GET / 200 dönmelidir."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"
