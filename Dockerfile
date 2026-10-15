# ---------------------------------------------------------------------------
# CadencePLM - Endüstriyel Konteyner İmajı (Production Dockerfile)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Ortam Değişkenleri: Python çıktı tamponlama ve bytecode üretimi kapalı
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Çalışma Dizini
WORKDIR /app

# Sistem Bağımlılıklarını Kur (curl, build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılık Katmanı (Docker Cache Optimizasyonu)
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kaynak Kodları, data/ ve ui/ Dizinlerini Kopyala
COPY . .

# Projeyi editable modda kur (src paket çözümlemesi için) ve rapor dizini oluştur
RUN pip install --no-cache-dir -e . && \
    mkdir -p /app/reports

# Dışa Açılan Portlar (FastAPI API: 8000, Streamlit Dashboard: 8501)
EXPOSE 8000 8501

# Varsayılan Çalıştırma Komutu (API)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
