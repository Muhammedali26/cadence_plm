"""
src/core/config.py
==================
CadencePLM ortam konfigürasyonu.

pydantic-settings kullanarak tüm gizli/çevresel ayarları yönetir.
Kural (.antigravityrules §5):
  - Gizli anahtarlar ve konfigürasyonlar yalnızca bu modül üzerinden okunur.
  - Değerler `.env` dosyasından veya sistem ortam değişkenlerinden çekilir.
  - `settings` tekil (singleton) nesnesi import edilerek kullanılır.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.exceptions import CadencePLMException


# ---------------------------------------------------------------------------
# Yardımcı Enum'lar
# ---------------------------------------------------------------------------

class Environment(StrEnum):
    """Uygulama çalışma ortamları."""

    DEVELOPMENT = "development"
    STAGING     = "staging"
    PRODUCTION  = "production"
    TEST        = "test"


class LogLevel(StrEnum):
    """Standart Python log seviyeleri."""

    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Ayar Modeli
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Tüm ortam değişkenlerinin Pydantic-settings üzerinden merkezi yönetimi.

    Öncelik sırası (yüksekten düşüğe):
      1. İşletim sistemi ortam değişkenleri
      2. `.env` dosyası
      3. Alan tanımındaki varsayılan değer

    Fields
    ------
    APP_NAME : str
        Uygulamanın görünen adı (API başlıkları, log etiketleri).
    APP_VERSION : str
        Semantik versiyon dizgesi.
    ENVIRONMENT : Environment
        Çalışma ortamı; `production` modunda hata ayıklama bilgileri gizlenir.
    LOG_LEVEL : LogLevel
        Root logger seviyesi.
    DEBUG : bool
        True iken Uvicorn/FastAPI hata izlerini (traceback) döndürür.
        Production'da False olmalıdır.

    API Ayarları
    ------------
    API_PREFIX : str
        Tüm endpoint'lerin ortak öneki (ör. "/api/v1").
    ALLOWED_ORIGINS : list[str]
        CORS için izin verilen origin listesi.

    Dosya İşleme
    ------------
    MAX_UPLOAD_SIZE_MB : int
        Yüklenebilecek maksimum dosya boyutu (MB cinsinden).
    TEMP_DIR : str
        Geçici dosyaların yazılacağı dizin; tercihen bellek içi akış kullanılır.

    LLM / Gemini Entegrasyonu
    --------------------------
    GEMINI_API_KEY : str | None
        Google Gemini API anahtarı. Boş bırakılırsa LLM çağrısı yapılmaz.
    GEMINI_MODEL : str
        Kullanılacak Gemini model adı.

    Veritabanı (İleride)
    --------------------
    DATABASE_URL : str | None
        Opsiyonel SQL bağlantı dizgesi (Aşama 2 için ayrıldı).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,       # Büyük/küçük harf duyarlı eşleşme
        extra="ignore",            # Bilinmeyen env değişkenleri sessizce yok sayılır
    )

    # ------------------------------------------------------------------
    # Uygulama Kimliği
    # ------------------------------------------------------------------
    APP_NAME: str = Field(default="CadencePLM", description="Uygulama adı")
    APP_VERSION: str = Field(default="0.1.0", description="Semantik versiyon")
    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Çalışma ortamı",
    )
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        description="Root logger seviyesi",
    )
    DEBUG: bool = Field(
        default=False,
        description="Hata ayıklama modu; production'da False olmalı",
    )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    API_PREFIX: str = Field(
        default="/api/v1",
        description="Tüm route'ların ortak öneki",
    )
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="CORS için izin verilen origin'ler",
    )

    # ------------------------------------------------------------------
    # Dosya İşleme
    # ------------------------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Yüklenebilecek maks. dosya boyutu (MB)",
    )
    TEMP_DIR: str = Field(
        default="/tmp/cadence_plm",
        description="Geçici dosya dizini (tercih: bellek içi akış)",
    )

    # ------------------------------------------------------------------
    # LLM / Gemini & OpenAI
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API anahtarı",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Kullanılacak Gemini modeli",
    )
    OPENAI_API_KEY: SecretStr = Field(
        ...,
        description="OpenAI API anahtarı (SecretStr)",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="Kullanılacak OpenAI modeli",
    )

    # ------------------------------------------------------------------
    # Veritabanı (Aşama 2 için yer tutucu)
    # ------------------------------------------------------------------
    DATABASE_URL: str | None = Field(
        default=None,
        description="SQL bağlantı dizgesi (opsiyonel, Aşama 2)",
    )

    # ------------------------------------------------------------------
    # Doğrulayıcılar
    # ------------------------------------------------------------------
    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def _validate_openai_api_key(cls, v: object) -> str:
        if v is None:
            raise CadencePLMException(
                "OPENAI_API_KEY ortam değişkeni bulunamadı veya boş.",
                detail="Lütfen .env dosyasında geçerli bir OPENAI_API_KEY tanımlayın.",
            )
        if isinstance(v, SecretStr):
            raw = v.get_secret_value().strip()
        else:
            raw = str(v).strip()
        if not raw or not raw.startswith("sk-") or len(raw) < 15:
            raise CadencePLMException(
                f"Geçersiz OPENAI_API_KEY anahtarı: {raw[:8]}...",
                detail="OpenAI API anahtarı 'sk-' ile başlamalı ve geçerli bir token olmalıdır.",
            )
        return raw

    @field_validator("API_PREFIX")
    @classmethod
    def _api_prefix_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"API_PREFIX '/' ile başlamalıdır; alınan: {v!r}")
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: str | list[str]) -> list[str]:
        """
        `.env` dosyasında virgülle ayrılmış string olarak saklanabilir:
            ALLOWED_ORIGINS=http://localhost:3000,https://cadence.example.com
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ------------------------------------------------------------------
    # Hesaplanan Özellikler
    # ------------------------------------------------------------------
    @property
    def openai_api_key_str(self) -> str:
        """OpenAI API anahtarını güvenli biçimde string olarak döndürür."""
        return self.OPENAI_API_KEY.get_secret_value()

    @property
    def is_production(self) -> bool:
        """Üretim ortamında çalışılıyorsa True döner."""
        return self.ENVIRONMENT is Environment.PRODUCTION

    @property
    def is_debug(self) -> bool:
        """DEBUG modu veya development/test ortamında True döner."""
        return self.DEBUG or self.ENVIRONMENT in (
            Environment.DEVELOPMENT,
            Environment.TEST,
        )

    @property
    def max_upload_size_bytes(self) -> int:
        """MAX_UPLOAD_SIZE_MB değerini bayta çevirir."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Singleton erişimi — `from src.core.config import settings`
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Ayarları bir kez oluşturur ve önbelleğe alır.
    Test ortamında `get_settings.cache_clear()` ile sıfırlanabilir.
    """
    return Settings()


#: Modül düzeyi kısayol — doğrudan import için.
settings: Settings = get_settings()
