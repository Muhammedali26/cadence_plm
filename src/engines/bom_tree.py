"""
src/engines/bom_tree.py
=======================
BOM ağaç motortu — DAG tabanlı, tamamen deterministik.

Kurallar (.antigravityrules §1 & §2):
- Sıfır LLM / harici API bağımlılığı.
- Sıfır FastAPI bağımlılığı.
- Döngüsel bağımlılık tespiti için `visited` kümesi zorunludur.
- Döngü veya eksik parent tespit edildiğinde `BOMStructureError` fırlatılır;
  sessiz `pass` kesinlikle yasaktır.
- `Any` tipi kullanımı yasaktır.
"""

from __future__ import annotations

import io
from collections import defaultdict

import pandas as pd

from src.core.exceptions import BOMStructureError, PartNotFoundError
from src.schemas.bom import BOMItem
from src.schemas.simulation import WhereUsedDetail

# CSV'de beklenen sütun adları — kaynak verilerle eşleşmeli.
_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "part_number",
        "part_name",
        "revision",
        "parent_part_number",
        "quantity",
        "unit_cost",
        "supplier_id",
    }
)


class BOMTreeEngine:
    """
    BOM verisini belleğe yükler ve DAG gezintisiyle etki analizini yapar.

    Dahili Veri Yapıları
    --------------------
    _parts : dict[str, BOMItem]
        Parça numarası → BOMItem eşlemesi (hızlı O(1) erişim).
    _children : dict[str, list[str]]
        Parça numarası → doğrudan çocuk parça numaraları listesi.
        BOM hiyerarşisini aşağı yönde gezmek için kullanılır.

    Thread Safety
    -------------
    Engine nesnesi immutable BOMItem'lar depolar; aynı anda birden fazla
    thread'den `get_affected_subassemblies` çağrılabilir.
    """

    def __init__(self) -> None:
        self._parts: dict[str, BOMItem] = {}
        self._children: dict[str, list[str]] = defaultdict(list)
        self._parents: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Yükleme Arayüzleri
    # ------------------------------------------------------------------

    def load_from_dataframe(self, df: pd.DataFrame) -> None:
        """
        Pandas DataFrame'den BOM yükler.

        Her satır bir BOMItem'a dönüştürülür; `parent_part_number` NaN
        ise ``None`` olarak yorumlanır (kök parça).

        Parameters
        ----------
        df : pd.DataFrame
            En az şu sütunları içermeli: part_number, part_name, revision,
            parent_part_number, quantity, unit_cost, supplier_id.
            İsteğe bağlı: tooling_id.

        Raises
        ------
        BOMStructureError
            Zorunlu sütun eksikse veya yükleme sonrası döngü tespit edilirse.
        """
        missing = _REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise BOMStructureError(
                "DataFrame zorunlu sütunları içermiyor",
                detail=f"Eksik sütunlar: {sorted(missing)}",
            )

        self._parts.clear()
        self._children.clear()
        self._parents.clear()

        for _, row in df.iterrows():
            parent: str | None = (
                None
                if pd.isna(row.get("parent_part_number"))
                else str(row["parent_part_number"]).strip()
            )
            tooling: str | None = (
                None
                if pd.isna(row.get("tooling_id", float("nan")))
                else str(row["tooling_id"]).strip()
            )

            item = BOMItem(
                part_number=str(row["part_number"]).strip(),
                part_name=str(row["part_name"]).strip(),
                revision=str(row["revision"]).strip(),
                parent_part_number=parent,
                quantity=float(row["quantity"]),
                unit_cost=round(float(row["unit_cost"]), 2),
                supplier_id=str(row["supplier_id"]).strip(),
                tooling_id=tooling,
            )
            self._parts[item.part_number] = item
            if parent is not None:
                self._children[parent].append(item.part_number)
                self._parents[item.part_number].append(parent)

        self._validate_no_cycles()

    def load_from_csv(self, csv_source: str | io.StringIO) -> None:
        """
        CSV dosyasından veya bellek içi StringIO'dan BOM yükler.

        Parameters
        ----------
        csv_source : str | io.StringIO
            Dosya yolu (str) veya bellek içi akış (io.StringIO).
            Sunucu üzerinde geçici dosya bırakmaktan kaçınmak için
            io.StringIO tercih edilir (.antigravityrules §5).

        Raises
        ------
        BOMStructureError
            Zorunlu sütun eksikse veya döngü tespit edilirse.
        """
        df = pd.read_csv(csv_source, dtype=str, keep_default_na=True)
        # Sayısal sütunları doğru tipe dönüştür
        for col in ("quantity", "unit_cost"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="raise")
        self.load_from_dataframe(df)

    # ------------------------------------------------------------------
    # Sorgulama Arayüzü
    # ------------------------------------------------------------------

    def get_affected_subassemblies(self, root_part_number: str) -> list[BOMItem]:
        """
        Verilen parçadan aşağı doğru DAG gezintisiyle etkilenen tüm parçaları
        döndürür.

        Algoritma: Yinelemeli BFS (Breadth-First Search) + `visited` kümesi.
        Kök parçanın kendisi de sonuca dahildir.

        Parameters
        ----------
        root_part_number : str
            Değişikliğin başladığı (kök) parçanın numarası.

        Returns
        -------
        list[BOMItem]
            BFS sırasına göre sıralanmış etkilenen parçalar.
            Kök parça listenin ilk elemanıdır.

        Raises
        ------
        PartNotFoundError
            `root_part_number` yüklü BOM'da bulunamazsa.
        BOMStructureError
            Gezinti sırasında beklenmedik bir döngü tespit edilirse.
            (Normal yükte `load` sırasında yakalanır; bu kontrol ek güvencedir.)
        """
        if root_part_number not in self._parts:
            raise PartNotFoundError(
                f"Parça BOM'da bulunamadı: {root_part_number!r}",
                part_id=root_part_number,
            )

        result: list[BOMItem] = []
        visited: set[str] = set()
        queue: list[str] = [root_part_number]

        while queue:
            current_pn = queue.pop(0)

            if current_pn in visited:
                # İkincil döngü güvencesi — load sırasında zaten yakalanmış
                # olmalı; burada da fırlatılır (sessiz pass yasak).
                raise BOMStructureError(
                    "Traversal sırasında döngü tespit edildi",
                    detail=f"Tekrar ziyaret edilen parça: {current_pn!r}",
                )
            visited.add(current_pn)

            part = self._parts.get(current_pn)
            if part is None:
                raise BOMStructureError(
                    "BOM'da tanımsız çocuk parça referansı",
                    detail=f"Tanımsız parça numarası: {current_pn!r}",
                )

            result.append(part)
            queue.extend(self._children.get(current_pn, []))

        return result

    def get_where_used(self, child_part_number: str) -> list[WhereUsedDetail]:
        """
        Hedef parçadan başlayarak kök montaja kadar yukarı yönlü (bottom-up) gezinti
        yapar ve etkilenen tüm üst sistemleri hiyerarşik seviyesiyle döner.

        Parameters
        ----------
        child_part_number : str
            Kullanım yerleri aranacak alt parçanın numarası.

        Returns
        -------
        list[WhereUsedDetail]
            Alt parçanın dahil olduğu tüm üst montajlar (seviye 1: doğrudan üst parça,
            seviye 2: bir üstü, vb.).

        Raises
        ------
        PartNotFoundError
            Parça yüklü BOM'da yoksa.
        BOMStructureError
            Yukarı yönlü gezinti sırasında beklenmedik bir döngü tespit edilirse.
        """
        if child_part_number not in self._parts:
            raise PartNotFoundError(
                f"Parça BOM'da bulunamadı: {child_part_number!r}",
                part_id=child_part_number,
            )

        result: list[WhereUsedDetail] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = []

        # Doğrudan üst montajları Seviye 1 olarak kuyruğa ekle
        for parent_pn in self._parents.get(child_part_number, []):
            queue.append((parent_pn, 1))

        while queue:
            current_pn, level = queue.pop(0)

            if current_pn in visited:
                raise BOMStructureError(
                    "Where-used gezintisi sırasında döngüsel bağımlılık tespit edildi",
                    detail=f"Döngü oluşturan üst parça: {current_pn!r}",
                )
            visited.add(current_pn)

            parent_item = self._parts.get(current_pn)
            if parent_item is None:
                raise BOMStructureError(
                    "BOM'da tanımsız üst montaj referansı",
                    detail=f"Tanımsız üst parça numarası: {current_pn!r}",
                )

            result.append(
                WhereUsedDetail(
                    parent_part_number=parent_item.part_number,
                    parent_part_name=parent_item.part_name,
                    assembly_level=level,
                )
            )

            # Bir üst seviye ebeveynleri kuyruğa ekle
            for next_parent in self._parents.get(current_pn, []):
                queue.append((next_parent, level + 1))

        return result

    # ------------------------------------------------------------------
    # Yardımcı Yöntemler
    # ------------------------------------------------------------------

    def get_part(self, part_number: str) -> BOMItem:
        """
        Parça numarasına göre tek bir BOMItem döndürür.

        Raises
        ------
        PartNotFoundError
            Parça yüklü BOM'da yoksa.
        """
        part = self._parts.get(part_number)
        if part is None:
            raise PartNotFoundError(
                f"Parça bulunamadı: {part_number!r}",
                part_id=part_number,
            )
        return part

    @property
    def part_count(self) -> int:
        """Yüklü toplam parça sayısı."""
        return len(self._parts)

    @property
    def all_part_numbers(self) -> set[str]:
        """Yüklü tüm parça numaraları kümesi."""
        return set(self._parts.keys())

    # ------------------------------------------------------------------
    # Dahili Doğrulama
    # ------------------------------------------------------------------

    def _validate_no_cycles(self) -> None:
        """
        Tüm BOM üzerinde döngü (cycle) kontrolü yapar.

        DFS ile her parçadan başlayarak `ancestor_stack` kümesiyle
        döngü arar. İlk döngüde `BOMStructureError` fırlatır.

        Raises
        ------
        BOMStructureError
            Herhangi bir döngüsel bağımlılık tespit edilirse.
        """
        globally_visited: set[str] = set()

        def _dfs(pn: str, ancestor_stack: set[str]) -> None:
            if pn in ancestor_stack:
                raise BOMStructureError(
                    "Döngüsel bağımlılık tespit edildi (load sırasında)",
                    detail=f"Döngü oluşturan parça: {pn!r}",
                )
            if pn in globally_visited:
                return

            globally_visited.add(pn)
            ancestor_stack.add(pn)
            for child_pn in self._children.get(pn, []):
                _dfs(child_pn, ancestor_stack)
            ancestor_stack.discard(pn)

        for part_number in self._parts:
            _dfs(part_number, set())
