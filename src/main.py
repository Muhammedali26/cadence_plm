"""
src/main.py
===========
CadencePLM FastAPI ana uygulama modülü.

Kurallar (.antigravityrules §1 & §3):
- Katmanlar kendi exception'larını fırlatır; global exception handler'lar
  bu istisnaları uygun HTTP durum kodlarına ve JSON yapılarına dönüştürür.
- CORS ve konfigürasyon ayarları pydantic-settings (settings) üzerinden yönetilir.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.mock_sap_odata import router as mock_sap_router
from src.api.v1.simulation_router import router as simulation_router
from src.core.config import settings
from src.core.exceptions import (
    BOMStructureError,
    CadencePLMException,
    CostCalculationError,
    ECOParsingError,
    PartNotFoundError,
)


def create_app() -> FastAPI:
    """FastAPI uygulama fabrikası."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="CadencePLM – BOM Maliyet Analizi ve ECO Simülasyon Motoru",
        debug=settings.is_debug,
    )

    # ------------------------------------------------------------------
    # CORS Yapılandırması
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Global İstisna Yöneticileri (Exception Handlers)
    # ------------------------------------------------------------------

    @app.exception_handler(PartNotFoundError)
    async def handle_part_not_found(
        request: Request, exc: PartNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "PartNotFoundError",
                "message": exc.message,
                "part_id": exc.part_id,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(BOMStructureError)
    async def handle_bom_structure_error(
        request: Request, exc: BOMStructureError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "BOMStructureError",
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(ECOParsingError)
    async def handle_eco_parsing_error(
        request: Request, exc: ECOParsingError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "ECOParsingError",
                "message": exc.message,
                "raw_input": exc.raw_input,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(CostCalculationError)
    async def handle_cost_calculation_error(
        request: Request, exc: CostCalculationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "CostCalculationError",
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(CadencePLMException)
    async def handle_cadence_base_exception(
        request: Request, exc: CadencePLMException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    # ------------------------------------------------------------------
    # Router Kayıtları
    # ------------------------------------------------------------------
    # /api/v1/simulate
    app.include_router(simulation_router, prefix=settings.API_PREFIX)
    # /simulate doğrudan erişim için de router eklenir
    app.include_router(simulation_router)
    # SAP S/4HANA OData v4 / v2 router'ı
    app.include_router(mock_sap_router)

    # ------------------------------------------------------------------
    # Temel Sistem Endpoint'leri
    # ------------------------------------------------------------------
    @app.get("/", tags=["System"])
    async def root() -> dict[str, str]:
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
        }

    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        return {
            "status": "healthy",
            "environment": str(settings.ENVIRONMENT),
        }

    return app


app: FastAPI = create_app()
