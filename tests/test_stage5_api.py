import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.asyncio
async def test_simulate_endpoint_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open("data/sample_ebom.csv", "rb") as f_ebom, open("data/sample_inventory.csv", "rb") as f_inv:
            files = {
                "ebom_file": ("sample_ebom.csv", f_ebom, "text/csv"),
                "inventory_file": ("sample_inventory.csv", f_inv, "text/csv"),
            }
            data = {"eco_text": "GB-PINION-02 parçasında tolerans değişikliği, revizyon B."}
            response = await client.post("/api/v1/simulate", files=files, data=data)
            
        assert response.status_code == 200
        json_data = response.json()
        assert "total_scrap_cost" in json_data
        assert "total_affected_parts" in json_data
        assert json_data["total_affected_parts"] > 0

@pytest.mark.asyncio
async def test_openapi_schema_generated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/v1/simulate" in response.json()["paths"]