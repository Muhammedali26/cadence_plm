"""
src/core/exceptions.py
======================
CadencePLM özel istisna hiyerarşisi.

Kural (.antigravityrules §3 & §2):
- Genel `except Exception` yasaktır; her katman yalnızca bu
  modülde tanımlı, amaca özgü exception'ları fırlatır.
- Sessiz `pass` yasaktır; belirsiz durumlarda mutlaka exception raise edilir.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Taban Sınıf
# ---------------------------------------------------------------------------

class CadencePLMException(Exception):
    """
    CadencePLM uygulamasındaki tüm özel istisnaların ortak atası.

    Attributes
    ----------
    message : str
        İnsan tarafından okunabilir hata açıklaması.
    detail : str | None
        Ek bağlam bilgisi (isteğe bağlı, örn. kök neden veya bağlamsal veri).
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.detail: str | None = detail

    def __repr__(self) -> str:  # pragma: no cover
        cls = type(self).__name__
        return f"{cls}(message={self.message!r}, detail={self.detail!r})"


# ---------------------------------------------------------------------------
# BOM Yapısı Hataları
# ---------------------------------------------------------------------------

class BOMStructureError(CadencePLMException):
    """
    BOM (Bill of Materials) hiyerarşisindeki yapısal bozukluklarda fırlatılır.

    Kullanım senaryoları:
    - Döngüsel bağımlılık (cyclic dependency) tespiti — DAG gezintisi sırasında
      `visited_parts` kümesinde zaten olan bir parça tekrar ziyaret edildiğinde.
    - Eksik parent: Bir alt parça, tanımlanmamış bir parent ID'ye referans verdiğinde.
    - Bozuk hiyerarşi: Derinlik/quantity tutarsızlığı veya geçersiz BOM satırı.

    Example
    -------
    >>> raise BOMStructureError(
    ...     "Cyclic dependency detected",
    ...     detail="Part P-001 → P-002 → P-001 forms a cycle",
    ... )
    """


class PartNotFoundError(CadencePLMException):
    """
    BOM yapısında veya envanterde istenen parça bulunamadığında fırlatılır.

    Attributes
    ----------
    part_id : str
        Bulunamayan parçanın benzersiz kimliği.

    Example
    -------
    >>> raise PartNotFoundError(part_id="P-999", message="Part not found in BOM")
    """

    def __init__(
        self,
        message: str,
        part_id: str,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail)
        self.part_id: str = part_id

    def __repr__(self) -> str:  # pragma: no cover
        cls = type(self).__name__
        return (
            f"{cls}(part_id={self.part_id!r}, "
            f"message={self.message!r}, detail={self.detail!r})"
        )


# ---------------------------------------------------------------------------
# ECO Ayrıştırma Hataları
# ---------------------------------------------------------------------------

class ECOParsingError(CadencePLMException):
    """
    Serbest metin ECO (Engineering Change Order) talebi ayrıştırılamadığında
    fırlatılır.

    Kullanım senaryoları:
    - Zorunlu alan (part_number, revision, quantity) metinden çıkarılamadığında.
    - LLM çıktısı beklenen Pydantic şemasına uygun değilken.
    - ECO metninin desteklenmeyen bir formatta olması durumunda.

    Attributes
    ----------
    raw_input : str
        Ayrıştırılamayan ham giriş metni (izleme/loglama için saklanır).

    Example
    -------
    >>> raise ECOParsingError(
    ...     message="Could not extract part_number from ECO text",
    ...     raw_input="Replace the blue one with the new thingamajig",
    ... )
    """

    def __init__(
        self,
        message: str,
        raw_input: str,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail)
        self.raw_input: str = raw_input

    def __repr__(self) -> str:  # pragma: no cover
        cls = type(self).__name__
        snippet = self.raw_input[:80] + ("…" if len(self.raw_input) > 80 else "")
        return (
            f"{cls}(message={self.message!r}, "
            f"raw_input={snippet!r}, detail={self.detail!r})"
        )


# ---------------------------------------------------------------------------
# Maliyet Hesaplama Hataları
# ---------------------------------------------------------------------------

class CostCalculationError(CadencePLMException):
    """
    Maliyet hesaplama motoru geçersiz girdi ile karşılaştığında fırlatılır.

    Kullanım senaryoları:
    - Negatif stok miktarı — fiziksel olarak imkânsız durum.
    - Tanımsız (None/NaN) birim maliyet — hesaplama yapılamaz.
    - Sıfıra bölme (örn. tüketim hızı sıfırken stok tükenme süresi hesabı).
    - Yuvarlama sonrası Decimal hassasiyet ihlali.

    Example
    -------
    >>> raise CostCalculationError(
    ...     message="Negative stock quantity is not allowed",
    ...     detail="part_id=P-042, stock=-15",
    ... )
    """
