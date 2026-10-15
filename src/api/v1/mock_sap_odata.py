"""
src/api/v1/mock_sap_odata.py
============================
Gerçek SAP S/4HANA OData v4/v2 API_MATERIAL_STOCK_SRV simülasyon router'ı.

Kurallar (.antigravityrules §1, §3 & §5):
- Gerçek SAP S/4HANA OData endpoint formatını birebir uygular:
  GET /sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock('{matnr}')
- Güvenlik: Basic Auth veya X-SAP-API-Key header denetimi yapar (HTTP 401).
- Yanıt formatı: Standart SAP OData v2/v4 JSON paketidir ("d" kök nesnesi).
"""

from __future__ import annotations

import base64
import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["SAP S/4HANA OData"])

# Geçerli kurumsal API anahtarları ve yetkili kullanıcılar
_VALID_API_KEYS: set[str] = {
    "SAP-ODATA-KEY-2024",
    "SAP-SECRET-KEY-PROD",
    "CADENCE-SAP-ODATA-TOKEN",
    "ENTERPRISE-S4HANA-KEY",
}

# Standart SAP S/4HANA Malzeme Envanter Veritabanı
_SAP_MATERIAL_DATABASE: dict[str, dict[str, Any]] = {
    "GB-PINION-02": {
        "MATNR": "GB-PINION-02",
        "MAKTX": "Ayna Pinyon Dislisi",
        "LABST": "55.000",
        "MEINS": "EA",
        "STPRS": "135.00",
        "WAERS": "USD",
        "PLIFZ": "30",
        "TOOL_IMP": True,
        "LGORT": "WH-01",
    },
    "GB-SHAFT-01": {
        "MATNR": "GB-SHAFT-01",
        "MAKTX": "Ana Tahrik Mili",
        "LABST": "40.000",
        "MEINS": "EA",
        "STPRS": "320.00",
        "WAERS": "USD",
        "PLIFZ": "28",
        "TOOL_IMP": True,
        "LGORT": "WH-02",
    },
    "GBX-1210": {
        "MATNR": "GBX-1210",
        "MAKTX": "Ana Tahrik Mili (1210)",
        "LABST": "40.000",
        "MEINS": "EA",
        "STPRS": "320.00",
        "WAERS": "USD",
        "PLIFZ": "28",
        "TOOL_IMP": True,
        "LGORT": "WH-02",
    },
    "GBX-1000": {
        "MATNR": "GBX-1000",
        "MAKTX": "Sanziman Govdesi",
        "LABST": "10.000",
        "MEINS": "EA",
        "STPRS": "1250.00",
        "WAERS": "USD",
        "PLIFZ": "45",
        "TOOL_IMP": True,
        "LGORT": "WH-01",
    },
    "GBX-1300": {
        "MATNR": "GBX-1300",
        "MAKTX": "Diferansiyel Grubu",
        "LABST": "25.000",
        "MEINS": "EA",
        "STPRS": "450.00",
        "WAERS": "USD",
        "PLIFZ": "21",
        "TOOL_IMP": True,
        "LGORT": "WH-01",
    },
    "TG11": {
        "MATNR": "TG11",
        "MAKTX": "Trading Good 11 (SAP S/4HANA Demo Material)",
        "LABST": "154345.000",
        "MEINS": "EA",
        "STPRS": "120.00",
        "WAERS": "USD",
        "PLIFZ": "14",
        "TOOL_IMP": False,
        "LGORT": "171R",
    },
}


def _verify_sap_authentication(
    api_key: str | None,
    authorization: str | None,
) -> bool:
    """Basic Auth veya X-SAP-API-Key / ApiKey geçerliliğini denetler."""
    from src.core.config import settings

    if api_key:
        clean_key = api_key.strip()
        if clean_key in _VALID_API_KEYS:
            return True
        if settings.SAP_API_KEY and clean_key == settings.SAP_API_KEY:
            return True

    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "basic":
            try:
                decoded = base64.b64decode(parts[1]).decode("utf-8")
                user, password = decoded.split(":", 1)
                if user in ("sap_user", "s4hana_rfc", "cadence") and password:
                    return True
            except Exception:
                return False

    return False


def _clean_matnr(raw_matnr: str) -> str:
    """URL içinden parça numarasını ayıklar: A_MaterialStock('GB-PINION-02') -> GB-PINION-02."""
    cleaned = raw_matnr.strip()
    match = re.search(r"['\"]([^'\"]+)['\"]", cleaned)
    if match:
        return match.group(1).strip()
    return cleaned.strip("()'\"")


@router.get(
    "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock('{matnr}')",
    summary="SAP S/4HANA OData A_MaterialStock Endpoint (Single Quote Path)",
    response_class=JSONResponse,
)
@router.get(
    "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock({matnr})",
    summary="SAP S/4HANA OData A_MaterialStock Endpoint (Generic Path)",
    response_class=JSONResponse,
)
async def get_sap_material_stock(
    matnr: str,
    request: Request,
    x_sap_api_key: str | None = Header(None, alias="X-SAP-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
    fault: str | None = Query(None, description="Kaos testi için sunucu hatası simülasyonu (örn: '503')"),
) -> JSONResponse:
    """
    SAP S/4HANA `API_MATERIAL_STOCK_SRV` standardına uygun malzeme stok ve maliyet verisi sunar.
    """
    # 1. Kaos ve Hata Enjeksiyonu Denetimi (Chaos Testing 503 / Timeout)
    header_fault = request.headers.get("X-SAP-Fault")
    if fault == "503" or header_fault == "503":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "/IWBEP/CM_MGW/503",
                    "message": {
                        "lang": "en",
                        "value": "Service Temporarily Unavailable: SAP S/4HANA gateway is busy.",
                    },
                }
            },
        )

    # 2. Yetkilendirme Denetimi (Authentication Check)
    effective_api_key = (
        x_sap_api_key
        or request.headers.get("ApiKey")
        or request.headers.get("apikey")
        or request.headers.get("X-SAP-API-Key")
        or request.headers.get("x-sap-api-key")
    )
    if not _verify_sap_authentication(effective_api_key, authorization):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic realm='SAP S/4HANA API_MATERIAL_STOCK_SRV'"},
            content={
                "error": {
                    "code": "401",
                    "message": {
                        "lang": "en",
                        "value": "Unauthorized: Invalid or missing X-SAP-API-Key or Basic Authorization header.",
                    },
                }
            },
        )

    # 3. Malzeme Kimliğini Çözümleme
    clean_part = _clean_matnr(matnr)

    # 4. Envanter Sorgusu
    if clean_part not in _SAP_MATERIAL_DATABASE:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "/IWBEP/CM_MGW/004",
                    "message": {
                        "lang": "en",
                        "value": f"Resource not found for segment 'A_MaterialStock' with MATNR '{clean_part}'",
                    },
                }
            },
        )

    record = _SAP_MATERIAL_DATABASE[clean_part]
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"d": record},
    )
