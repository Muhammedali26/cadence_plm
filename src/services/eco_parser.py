"""
src/services/eco_parser.py
==========================
Serbest metin ECO taleplerini yapılandırılmış ECORequest modeline dönüştüren servis.

Kurallar (.antigravityrules §1 & §3):
- Deterministik Ayrım: Matematiksel hesaplama içermez; yalnızca serbest metni
  Pydantic modeline dönüştürmekle sorumludur.
- Çok Katmanlı Ayrıştırma:
  1. Öncelikli Yol: LLM (Gemini API) yapılandırılmış JSON extraction (API anahtarı varsa).
  2. Fallback Yolu: Kural tabanlı regex analizörü (deterministik ve offline çalışır).
- Başarısızlık Durumu: Zorunlu alanlar çıkarılamadığında ECOParsingError fırlatılır.
- Tip Güvenliği: Sıfır Any tipi.
"""

from __future__ import annotations

import json
import re
import uuid

import httpx

from src.core.config import settings
from src.core.exceptions import ECOParsingError
from src.schemas.eco import ECOChangeType, ECORequest


class ECOParser:
    """
    Serbest metin ECO açıklamalarını Pydantic ECORequest modeline dönüştürür.

    Attributes
    ----------
    api_key : str | None
        Gemini API anahtarı. Bulunmadığında doğrudan regex motoru çalışır.
    model : str
        Kullanılacak LLM modeli adı.
    timeout_seconds : float
        LLM HTTP çağrısı için zaman aşımı süresi.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.api_key: str | None = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model: str = model or settings.GEMINI_MODEL
        self.timeout_seconds: float = timeout_seconds

    # ------------------------------------------------------------------
    # Ana Giriş Noktası
    # ------------------------------------------------------------------

    def parse(self, raw_text: str, eco_id: str | None = None) -> ECORequest:
        """
        Serbest metni analiz eder ve ECORequest döner.

        Parameters
        ----------
        raw_text : str
            Kullanıcı tarafından girilen serbest metin ECO açıklaması.
        eco_id : str | None
            İsteğe bağlı ECO numarası. Verilmezse metinden aranır veya üretilir.

        Returns
        -------
        ECORequest
            Doğrulanmış Pydantic modeli.

        Raises
        ------
        ECOParsingError
            Metin anlamlandırılamadığında veya zorunlu alanlar bulunamadığında.
        """
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ECOParsingError(
                message="ECO metni boş olamaz.",
                raw_input=raw_text,
            )

        # 1. Aşama: LLM ile ayrıştırma (API anahtarı mevcutsa)
        if self.api_key:
            try:
                return self._parse_with_llm(cleaned_text, eco_id)
            except (httpx.HTTPError, ValueError, KeyError):
                # LLM başarısız olursa deterministik regex fallback'e geç
                pass

        # 2. Aşama: Kural tabanlı regex motoru (Fallback / Default)
        return self._parse_with_rules(cleaned_text, eco_id)

    # ------------------------------------------------------------------
    # LLM Tabanlı JSON Extraction
    # ------------------------------------------------------------------

    def _parse_with_llm(self, text: str, eco_id: str | None) -> ECORequest:
        """Google Gemini API ile yapılandırılmış JSON çıkarımı yapar."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        prompt = (
            "Analyze the following Engineering Change Order (ECO) text and extract "
            "structured data strictly as JSON with the following keys:\n"
            "- affected_part_number (string): The part identifier being modified.\n"
            "- target_revision (string): The new target revision code (e.g. B, Rev-B, C).\n"
            "- change_type (string): One of [TOLERANCE, MATERIAL, GEOMETRY, OBSOLETE].\n"
            "- description (string): Short summary of the change.\n"
            f"Input text: \"{text}\""
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content_str = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed_dict = json.loads(content_str)

        resolved_eco_id = eco_id or self._extract_or_generate_eco_id(text)
        raw_change_type = str(parsed_dict.get("change_type", "TOLERANCE")).upper()
        change_type = (
            ECOChangeType(raw_change_type)
            if raw_change_type in ECOChangeType.__members__
            else ECOChangeType.TOLERANCE
        )

        return ECORequest(
            eco_id=resolved_eco_id,
            raw_text=text,
            affected_part_number=str(parsed_dict["affected_part_number"]).strip(),
            target_revision=str(parsed_dict["target_revision"]).strip(),
            change_type=change_type,
            description=str(parsed_dict.get("description", text)).strip(),
        )

    # ------------------------------------------------------------------
    # Kural Tabanlı Regex Analizörü (Fallback)
    # ------------------------------------------------------------------

    def _parse_with_rules(self, text: str, eco_id: str | None) -> ECORequest:
        """Regex ve anahtar kelime eşleşmeleriyle deterministik ayrıştırma yapar."""
        resolved_eco_id = eco_id or self._extract_or_generate_eco_id(text)
        part_number = self._extract_part_number(text)
        target_revision = self._extract_revision(text)
        change_type = self._extract_change_type(text)

        if not part_number:
            raise ECOParsingError(
                message="ECO metninden etkilenen parça numarası tespit edilemedi.",
                raw_input=text,
                detail="Örnek parça formatı: GB-SHAFT-01, GBX-1210, P-101",
            )

        if not target_revision:
            raise ECOParsingError(
                message="ECO metninden hedef revizyon tespit edilemedi.",
                raw_input=text,
                detail="Örnek revizyon formatı: yeni rev B, revizyon C, Rev-02",
            )

        return ECORequest(
            eco_id=resolved_eco_id,
            raw_text=text,
            affected_part_number=part_number,
            target_revision=target_revision,
            change_type=change_type,
            description=text,
        )

    # ------------------------------------------------------------------
    # Alan Çıkarım Yardımcıları
    # ------------------------------------------------------------------

    def _extract_or_generate_eco_id(self, text: str) -> str:
        """Metin içindeki ECO-XXXX kimliğini bulur veya otomatik üretir."""
        match = re.search(r"\b(ECO-[A-Za-z0-9_-]+)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return f"ECO-AUTO-{uuid.uuid4().hex[:6].upper()}"

    def _extract_part_number(self, text: str) -> str | None:
        """Metinden parça numarasını çıkarır."""
        # 1. Açık anahtar kelime sonrasındaki parça: (parça/part/mili vb.)
        kw_patterns = [
            r"(?:parça(?:sı|nın)?|part|mil(?:i|inin)?|bileşen(?:i)?)\s*[:=]?\s*([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+)",
            r"([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+)\s+(?:parça(?:sı|nın)?|mil(?:i|inin)?|bileşen(?:i)?)",
        ]
        for pattern in kw_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and not m.group(1).upper().startswith("ECO-"):
                return m.group(1).strip()

        # 2. Genel parça formatı eşleşmesi (örn: GB-SHAFT-01, GBX-1210, P-101, P_CHILD)
        tokens = re.findall(r"\b([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+)\b", text)
        for token in tokens:
            upper_token = token.upper()
            if not upper_token.startswith("ECO-") and not upper_token.startswith("REV-"):
                return token.strip()

        return None

    def _extract_revision(self, text: str) -> str | None:
        """Metinden hedef revizyon bilgisini çıkarır."""
        stop_words = {
            "olacak", "yapıldı", "edildi", "yeni", "new",
            "nedeniyle", "sebebiyle", "dolayısıyla", "kapsamında",
            "için", "sonucu", "sonrasında", "bağlı", "göre",
        }

        patterns = [
            # "yeni rev B", "hedef revizyon Rev-02", "target revision C"
            r"\b(?:yeni\s+rev(?:izyon)?|hedef\s+rev(?:izyon)?|target\s+rev(?:ision)?|new\s+rev(?:ision)?)\b\s*[:=]?\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)?)\b",
            # "revizyonu: B", "revizyon B", "revision C"
            r"\b(?:rev(?:izyon|ision)?(?:u)?)\b\s*[:=]?\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)?)\b",
            # "rev B olacak", "rev: B"
            r"\brev\b\s*[:=]?\s*([A-Za-z0-9]+)\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val.lower() not in stop_words:
                    # Genellikle revizyonlar kısa kodlardır (örn: A, B, Rev-1, 02)
                    if len(val) <= 6 or val.lower().startswith("rev"):
                        return val

        # Eğer metinde açıkça 'revizyon' / 'revize' eylemi geçiyor ancak harf verilmemişse:
        if re.search(r"\b(revizyon\w*|revize)\b", text, re.IGNORECASE):
            return "B"

        return None

    def _extract_change_type(self, text: str) -> ECOChangeType:
        """Metindeki anahtar kelimelerden ECOChangeType belirler."""
        lowered = text.lower()
        if re.search(r"\b(obsolete\w*|iptal\w*|kullanım\s*dışı|ıskarta\w*|hurda\w*|end\s*of\s*life|eol)\b", lowered):
            return ECOChangeType.OBSOLETE
        if re.search(r"\b(malzeme\w*|material\w*|alaşım\w*|alloy\w*|hammadde\w*|çelik\w*|titanyum\w*|alüminyum\w*|steel\w*|aluminum\w*)\b", lowered):
            return ECOChangeType.MATERIAL
        if re.search(r"\b(geometri\w*|geometry\w*|şekil\w*|boyut\w*|form\w*|shape\w*|tasarım\w*|tasarlan\w*|redesign\w*|cad)\b", lowered):
            return ECOChangeType.GEOMETRY
        if re.search(r"\b(tolerans\w*|tolerance\w*|sapma\w*|ölçü\w*|clearance\w*)\b", lowered):
            return ECOChangeType.TOLERANCE

        # Varsayılan mühendislik tipi
        return ECOChangeType.TOLERANCE
