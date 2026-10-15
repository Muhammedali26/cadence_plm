"""
tests/test_stage15_docker.py
============================
Aşama 15: Kurumsal Konteynerizasyon (Docker & Docker-Compose) testleri.

Kurallar (.antigravityrules §1, §3):
- .dockerignore dosyasının ve hariç tutulan dizinlerin doğrulanması.
- Dockerfile temel imajı, ortam değişkenleri ve port yapılandırmasının doğrulanması.
- docker-compose.yml sözdizimi, servisler (api, dashboard), portlar ve volume eşlemelerinin doğrulanması.
"""

from __future__ import annotations

from pathlib import Path
import yaml
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDockerignoreConfiguration:
    """`.dockerignore` dosyasının kurallara uygunluk testi."""

    def test_dockerignore_file_exists(self) -> None:
        dockerignore_path = PROJECT_ROOT / ".dockerignore"
        assert dockerignore_path.exists(), ".dockerignore dosyası bulunamadı."

    def test_dockerignore_contains_required_exclusions(self) -> None:
        dockerignore_path = PROJECT_ROOT / ".dockerignore"
        content = dockerignore_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

        expected_patterns = [
            ".git",
            ".venv",
            "__pycache__",
            "*.pyc",
            "reports/*.html",
            ".env",
            ".pytest_cache",
        ]

        for pattern in expected_patterns:
            assert any(pattern == line or pattern in line for line in lines), (
                f"Gerekli desen .dockerignore içinde bulunamadı: {pattern}"
            )


class TestDockerfileConfiguration:
    """`Dockerfile` dosyasının mimari ve ortam testi."""

    def test_dockerfile_exists(self) -> None:
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile bulunamadı."

    def test_dockerfile_specifications(self) -> None:
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        content = dockerfile_path.read_text(encoding="utf-8")

        # 1. Temel İmaj
        assert "python:3.12-slim" in content, "Temel imaj python:3.12-slim olmalıdır."

        # 2. Ortam Değişkenleri
        assert "PYTHONUNBUFFERED=1" in content
        assert "PYTHONDONTWRITEBYTECODE=1" in content

        # 3. Çalışma Dizini
        assert "WORKDIR /app" in content

        # 4. Sistem Bağımlılıkları (curl, build-essential)
        assert "curl" in content
        assert "build-essential" in content

        # 5. Bağımlılık Kurulumu
        assert "pip install" in content
        assert "--no-cache-dir" in content

        # 6. Dışa Açılan Portlar (FastAPI: 8000, Streamlit: 8501)
        assert "8000" in content
        assert "8501" in content
        assert "EXPOSE" in content


class TestDockerComposeConfiguration:
    """`docker-compose.yml` servis ve orkestrasyon testi."""

    def test_docker_compose_exists_and_valid_yaml(self) -> None:
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml bulunamadı."

        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "services" in data, "docker-compose.yml içinde 'services' anahtarı bulunamadı."
        assert "api" in data["services"], "'api' servisi tanımlı değil."
        assert "dashboard" in data["services"], "'dashboard' servisi tanımlı değil."

    def test_api_service_configuration(self) -> None:
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        api_svc = data["services"]["api"]

        # Komut
        assert "uvicorn src.main:app" in api_svc["command"]
        assert "--host 0.0.0.0" in api_svc["command"]
        assert "--port 8000" in api_svc["command"]

        # Port
        assert "8000:8000" in api_svc["ports"]

        # env_file
        assert ".env" in api_svc["env_file"]

        # Volumes
        volumes = api_svc["volumes"]
        assert "./reports:/app/reports" in volumes
        assert "./data:/app/data" in volumes

    def test_dashboard_service_configuration(self) -> None:
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        dash_svc = data["services"]["dashboard"]

        # Komut
        assert "streamlit run ui/app.py" in dash_svc["command"]
        assert "--server.port 8501" in dash_svc["command"]
        assert "--server.address 0.0.0.0" in dash_svc["command"]

        # Port
        assert "8501:8501" in dash_svc["ports"]

        # Depends On
        assert "api" in dash_svc["depends_on"]

        # env_file
        assert ".env" in dash_svc["env_file"]

        # Volumes
        volumes = dash_svc["volumes"]
        assert "./reports:/app/reports" in volumes
        assert "./data:/app/data" in volumes
