"""
仝娘之家 · 通用业务核心库（Core Library）
============================================
v0.6 · 搜索支持 "-" 排除语义：
    输入 "开源 -国产" → 命中的含"开源"，但不含"国产"
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple
from urllib.parse import urlparse
import html as _html
import time


__version__ = "0.6.0"

__all__ = [
    "DomainError", "NotFound",
    "CharacterVersion", "AiCharacter", "NewsItem", "Term",
    "Prompt", "PromptScene", "Fighter", "Battle",
    "ExternalSite", "AboutItem", "SectionMeta",
    "CharacterService", "NewsService", "TermService",
    "PromptService", "BattleService",
    "WeightedField", "SearchHit", "SearchQuery", "Page",
    "SearchResult", "SearchHistory",
    "Searchable", "SynonymMap", "SearchSource", "SearchService",
    "Suggester", "score_object", "split_keywords", "parse_query", "highlight",
]


class DomainError(Exception):
    """业务异常基类。"""


class NotFound(DomainError):
    """请求的资源不存在。"""


# ============================================================
# 搜索子系统
# ============================================================
WEIGHT_HIGH = 3
WEIGHT_MID  = 2
WEIGHT_LOW  = 1

_EXACT = 60
_PREFIX = 40
_SUBSTR = 20
_MAX_SCORE = 100


@dataclass
class WeightedField:
    label: str
    value: str
    weight: int = 1


@dataclass
class SearchHit:
    type: str
    item: Any
    score: int
    matched_fields: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    preview: Dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.score > 0

    @property
    def display_name(self) -> str:
        return (
            getattr(self.item, "name", "")
            or getattr(self.item, "title", "")
            or getattr(self.item, "id", "")
        )


def parse_query(raw: str) -> Tuple[List[str], List[str]]:
    """
    解析查询字符串。

    规则：
        - 以 "-" 开头的词进入 exclude（排除）
        - 其余词进入 include（包含）
        - 单独的 "-" 或 "--" 忽略
        - 全角空格和半角空格都兼容

    例：
        "开源 -国产"        -> (["开源"], ["国产"])
        "GPT -2023 -闭源"   -> (["GPT"], ["2023", "闭源"])
        "GPT-4"            -> (["GPT-4"], [])   # "-" 不在开头，不解析为排除
    """
    if not raw:
        return [], []
    tokens = raw.replace("\u3000", " ").split()
    include: List[str] = []
    exclude: List[str] = []
    for t in tokens:
        if not t:
            continue
        if t.startswith("-") and len(t) > 1:
            exclude.append(t[1:])
        else:
            include.append(t)
    return include, exclude


def split_keywords(raw: str) -> List[str]:
    """纯分词，不做 include/exclude 分类。保留给老代码兼容。"""
    if not raw:
        return []
    return [k for k in raw.replace("\u3000", " ").split() if k]


@dataclass
class SearchQuery:
    """结构化查询对象：包含词 + 排除词 + 类型过滤 + 分页。"""
    raw: str
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    types: Optional[List[str]] = None
    page: int = 1
    per_page: int = 0

    def __post_init__(self):
        if not self.include and not self.exclude:
            self.include, self.exclude = parse_query(self.raw)

    @property
    def keywords(self) -> List[str]:
        return self.include

    @property
    def is_empty(self) -> bool:
        # 只有排除词、没有正向词：视为空查询（避免"搜全部再排除"的歧义）
        return not self.include

    @property
    def offset(self) -> int:
        return max(0, (self.page - 1) * self.per_page) if self.per_page > 0 else 0


@dataclass
class Page:
    items: List[Any]
    total: int
    page: int
    per_page: int

    @property
    def total_pages(self) -> int:
        if self.per_page <= 0:
            return 1
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def prev_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.total_pages, self.page + 1)


@dataclass
class SearchResult:
    grouped: Dict[str, List[SearchHit]]
    total: int
    elapsed_ms: float
    page: int = 1
    per_page: int = 0
    query: str = ""

    @property
    def is_empty(self) -> bool:
        return self.total == 0

    def flat_hits(self, order: Optional[List[str]] = None) -> List[SearchHit]:
        keys = order or list(self.grouped.keys())
        out: List[SearchHit] = []
        for k in keys:
            out.extend(self.grouped.get(k, []))
        return out


class Searchable(Protocol):
    def search_fields(self) -> List[WeightedField]: ...


class SynonymMap:
    def __init__(self, mapping: Optional[Dict[str, List[str]]] = None):
        self._map: Dict[str, List[str]] = {}
        if mapping:
            for key, aliases in mapping.items():
                group = sorted({key.lower(), *(a.lower() for a in aliases)})
                for word in group:
                    self._map[word] = group

    def expand(self, keyword: str) -> List[str]:
        return self._map.get(keyword.lower(), [keyword])


def highlight(text: str, keywords: List[str]) -> str:
    if not text:
        return ""
    if not keywords:
        return _html.escape(text)

    escaped = _html.escape(text)
    kws = sorted({k for k in keywords if k}, key=len, reverse=True)

    for kw in kws:
        e_kw = _html.escape(kw)
        if not e_kw:
            continue
        low = escaped.lower()
        tgt = e_kw.lower()
        out, i = [], 0
        while True:
            j = low.find(tgt, i)
            if j == -1:
                out.append(escaped[i:])
                break
            out.append(escaped[i:j])
            out.append(f"<mark>{escaped[j:j + len(e_kw)]}</mark>")
            i = j + len(e_kw)
        escaped = "".join(out)
    return escaped


def score_object(
    type_name: str,
    item: Any,
    fields: List[WeightedField],
    keyword_groups: List[List[str]],
    exclude_groups: Optional[List[List[str]]] = None,
) -> Optional[SearchHit]:
    """
    通用打分函数。

    先做排除检查：任意一个排除词组命中任意字段，直接出局（返回 None）。
    再做包含检查：每个包含词组必须至少命中一个字段（AND 语义）。
    """
    if not keyword_groups:
        return None

    # ---- 1. 排除检查 ----
    if exclude_groups:
        for group in exclude_groups:
            for f in fields:
                text = (f.value or "").lower()
                if not text:
                    continue
                for kw in group:
                    kl = kw.lower()
                    if kl and kl in text:
                        return None

    # ---- 2. 包含打分 ----
    matched_fields: List[str] = []
    matched_keywords: List[str] = []
    total = 0

    for group in keyword_groups:
        primary = group[0]
        group_hit = False
        for f in fields:
            text = (f.value or "").lower()
            if not text:
                continue
            for kw in group:
                kl = kw.lower()
                if not kl:
                    continue
                if text == kl:
                    total += _EXACT * f.weight
                    group_hit = True
                elif text.startswith(kl):
                    total += _PREFIX * f.weight
                    group_hit = True
                elif kl in text:
                    total += _SUBSTR * f.weight
                    group_hit = True
                else:
                    continue
                if f.label not in matched_fields:
                    matched_fields.append(f.label)
                break
        if not group_hit:
            return None
        matched_keywords.append(primary)

    return SearchHit(
        type=type_name,
        item=item,
        score=min(total, _MAX_SCORE),
        matched_fields=matched_fields,
        matched_keywords=matched_keywords,
    )


def _hit_sort_key(hit: SearchHit) -> str:
    return getattr(hit.item, "name", "") or getattr(hit.item, "title", "") or ""


class SearchSource:
    PREVIEW_FIELDS = 3

    def __init__(self, type_name: str, items: List[Any]):
        self.type_name = type_name
        self._items = items

    def _preview(self, item: Any, keywords: List[str]) -> Dict[str, str]:
        getter = getattr(item, "search_fields", None)
        if not callable(getter):
            return {}
        fields = sorted(getter(), key=lambda f: -f.weight)
        preview: Dict[str, str] = {}
        for f in fields:
            if len(preview) >= self.PREVIEW_FIELDS:
                break
            hl = highlight(f.value, keywords)
            if "<mark>" in hl:
                preview[f.label] = hl
        return preview

    def search(
        self,
        keyword_groups: List[List[str]],
        exclude_groups: Optional[List[List[str]]] = None,
    ) -> List[SearchHit]:
        hits: List[SearchHit] = []
        flat_kws = [g[0] for g in keyword_groups]
        for item in self._items:
            getter = getattr(item, "search_fields", None)
            if not callable(getter):
                continue
            hit = score_object(
                self.type_name, item, getter(),
                keyword_groups, exclude_groups,
            )
            if hit is not None:
                hit.preview = self._preview(item, flat_kws)
                hits.append(hit)
        hits.sort(key=lambda h: (-h.score, _hit_sort_key(h)))
        return hits


class SearchService:
    def __init__(
        self,
        sources: List[SearchSource],
        synonyms: Optional[SynonymMap] = None,
        type_order: Optional[List[str]] = None,
    ):
        self._sources: Dict[str, SearchSource] = {s.type_name: s for s in sources}
        self._synonyms = synonyms or SynonymMap()
        self._type_order = type_order or list(self._sources.keys())

    @classmethod
    def from_services(
        cls,
        characters: "CharacterService",
        news: "NewsService",
        terms: "TermService",
        synonyms: Optional[SynonymMap] = None,
    ) -> "SearchService":
        return cls(
            [
                SearchSource("characters", characters.all()),
                SearchSource("news", news.all()),
                SearchSource("terms", terms.all_terms()),
            ],
            synonyms=synonyms,
            type_order=["characters", "news", "terms"],
        )

    def _run(self, query: SearchQuery) -> Dict[str, List[SearchHit]]:
        groups = [self._synonyms.expand(k) for k in query.include]
        exgroups = [self._synonyms.expand(k) for k in query.exclude]
        target = query.types or list(self._sources.keys())
        return {
            name: self._sources[name].search(groups, exgroups)
            for name in self._type_order
            if name in target and name in self._sources
        }

    def search(self, q: str, types: Optional[List[str]] = None) -> Dict[str, List[Any]]:
        detailed = self.search_detailed(q, types)
        return {n: [h.item for h in hits] for n, hits in detailed.items()}

    def search_detailed(self, q: str, types: Optional[List[str]] = None) -> Dict[str, List[SearchHit]]:
        query = SearchQuery(raw=q, types=types)
        if query.is_empty:
            return {n: [] for n in self._sources}
        return self._run(query)

    def search_full(self, q: str, page: int = 1, per_page: int = 0) -> SearchResult:
        t0 = time.perf_counter()
        query = SearchQuery(raw=q, page=page, per_page=per_page)
        if query.is_empty:
            return SearchResult(grouped={}, total=0, elapsed_ms=0.0, query=q)

        grouped = self._run(query)
        total = sum(len(v) for v in grouped.values())

        if per_page > 0:
            grouped = self._paginate_groups(grouped, query.offset, per_page)

        elapsed = (time.perf_counter() - t0) * 1000
        return SearchResult(
            grouped=grouped, total=total, elapsed_ms=elapsed,
            page=page, per_page=per_page, query=q,
        )

    def _paginate_groups(
        self,
        grouped: Dict[str, List[SearchHit]],
        offset: int,
        per_page: int,
    ) -> Dict[str, List[SearchHit]]:
        flat: List[SearchHit] = []
        for name in self._type_order:
            flat.extend(grouped.get(name, []))
        flat.sort(key=lambda h: (-h.score, _hit_sort_key(h)))
        chunk = flat[offset: offset + per_page]
        out: Dict[str, List[SearchHit]] = {n: [] for n in grouped}
        for h in chunk:
            out[h.type].append(h)
        return out

    def available_types(self) -> List[str]:
        return list(self._type_order)


class Suggester:
    def __init__(self, sources: List[SearchSource], max_words: int = 3000):
        self._vocab: set = set()
        for src in sources:
            for item in src._items:
                getter = getattr(item, "search_fields", None)
                if not callable(getter):
                    continue
                for f in getter():
                    for w in self._tokenize(f.value):
                        self._vocab.add(w)
                        if len(self._vocab) >= max_words:
                            break

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        if not text:
            return []
        seps = " \t\n\r，。！？；：、,.!?;:()（）[]【】《》<>\"'`~@#$%^&*+=|\\/-"
        buf, out = [], []
        for ch in text:
            if ch in seps:
                if buf:
                    out.append("".join(buf)); buf = []
            else:
                buf.append(ch)
        if buf:
            out.append("".join(buf))
        return [w for w in out if 1 <= len(w) <= 20]

    def suggest(self, prefix: str, limit: int = 8) -> List[str]:
        if not prefix:
            return []
        p = prefix.lower()
        starts = [w for w in self._vocab if w.lower().startswith(p)]
        starts.sort(key=lambda w: (len(w), w.lower()))
        return starts[:limit]


class SearchHistory:
    def __init__(self, max_items: int = 10):
        self._items: List[str] = []
        self._max = max_items

    def push(self, q: str) -> None:
        if not q:
            return
        q = q.strip()
        if not q:
            return
        if q in self._items:
            self._items.remove(q)
        self._items.insert(0, q)
        del self._items[self._max:]

    def all(self) -> List[str]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()


# ============================================================
# 领域模型
# ============================================================
@dataclass
class CharacterVersion:
    name: str
    params: str
    context: str
    price: str


@dataclass
class AiCharacter:
    id: str
    name: str
    code: str
    title: str = ""
    company: str = ""
    nationality: str = ""
    birthday: str = ""
    main_tags: List[str] = field(default_factory=list)
    modality_tags: List[str] = field(default_factory=list)
    quote: str = ""
    bio: str = ""
    stats: Dict[str, int] = field(default_factory=dict)
    versions: List[CharacterVersion] = field(default_factory=list)

    @property
    def logo_url(self) -> str:
        return f"imgs/{self.id}logo.png"

    @property
    def char_url(self) -> str:
        return f"imgs/{self.id}char.png"

    @property
    def search_type(self) -> str:
        return "character"

    def search_fields(self) -> List[WeightedField]:
        return [
            WeightedField("名称", self.name, WEIGHT_HIGH),
            WeightedField("称号", self.title, WEIGHT_HIGH),
            WeightedField("公司", self.company, WEIGHT_MID),
            WeightedField("国籍", self.nationality, WEIGHT_MID),
            WeightedField("引语", self.quote, WEIGHT_MID),
            WeightedField("主标签", " ".join(self.main_tags), WEIGHT_MID),
            WeightedField("模态", " ".join(self.modality_tags), WEIGHT_MID),
            WeightedField("版本",
                          " ".join(f"{v.name} {v.params} {v.context}" for v in self.versions),
                          WEIGHT_MID),
            WeightedField("简介", self.bio, WEIGHT_LOW),
        ]

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        return score_object(self.search_type, self, self.search_fields(), [[keyword]]) is not None


@dataclass
class NewsItem:
    id: int
    img: str
    date: str
    title: str
    desc: str
    is_archive: bool = False
    url: str = ""

    @property
    def search_type(self) -> str:
        return "news"

    def search_fields(self) -> List[WeightedField]:
        return [
            WeightedField("标题", self.title, WEIGHT_HIGH),
            WeightedField("摘要", self.desc, WEIGHT_LOW),
        ]

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        return score_object(self.search_type, self, self.search_fields(), [[keyword]]) is not None


@dataclass
class Term:
    name: str
    plain: str

    @property
    def search_type(self) -> str:
        return "term"

    def search_fields(self) -> List[WeightedField]:
        return [
            WeightedField("术语", self.name, WEIGHT_HIGH),
            WeightedField("解释", self.plain, WEIGHT_LOW),
        ]

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        return score_object(self.search_type, self, self.search_fields(), [[keyword]]) is not None


@dataclass
class Prompt:
    scene: str
    name: str
    when: str
    prompt: str
    tips: str


@dataclass
class PromptScene:
    key: str
    title: str
    code: str
    img: str
    desc: str
    prompts: List[Prompt] = field(default_factory=list)


@dataclass
class Fighter:
    id: str
    name: str
    response: str


@dataclass
class Battle:
    id: int
    question: str
    fighter_a: Fighter
    fighter_b: Fighter
    winner: str
    commentary: str

    @property
    def a_wins(self) -> bool:
        return self.winner == self.fighter_a.name

    @property
    def b_wins(self) -> bool:
        return self.winner == self.fighter_b.name


@dataclass
class ExternalSite:
    name: str
    tagline: str
    url: str
    icon: str = ""
    img: str = ""

    @property
    def hostname(self) -> str:
        try:
            h = urlparse(self.url).hostname or self.url
            return h.removeprefix("www.")
        except Exception:
            return self.url


@dataclass
class AboutItem:
    label: str
    value: str


@dataclass
class SectionMeta:
    key: str
    title: str
    code: str
    bg: str


# ============================================================
# 业务服务
# ============================================================
class CharacterService:
    def __init__(self, characters: List[AiCharacter]):
        self._characters = characters
        self._by_id = {c.id: c for c in characters}

    def all(self) -> List[AiCharacter]:
        return self._characters

    def featured(self, n: int = 4) -> List[AiCharacter]:
        return self._characters[:n]

    def get(self, char_id: str) -> AiCharacter:
        c = self._by_id.get(char_id)
        if c is None:
            raise NotFound(f"角色 {char_id} 不存在")
        return c

    def search(self, keyword: str) -> List[AiCharacter]:
        return [c for c in self._characters if c.matches(keyword)]

    def count(self) -> int:
        return len(self._characters)


class NewsService:
    def __init__(self, news: List[NewsItem]):
        self._news = news

    def all(self) -> List[NewsItem]:
        return self._news

    def latest(self, n: int = 3) -> List[NewsItem]:
        return self._news[:n]

    def search(self, keyword: str) -> List[NewsItem]:
        return [n for n in self._news if n.matches(keyword)]


class TermService:
    def __init__(self, terms: Dict[str, List[Term]], meta: Dict[str, Dict[str, str]]):
        self._terms = terms
        self._meta = meta

    def levels(self) -> Dict[str, Dict[str, str]]:
        return self._meta

    def list_by_level(self, level: str) -> List[Term]:
        return self._terms.get(level, [])

    def all_terms(self) -> List[Term]:
        return [t for items in self._terms.values() for t in items]

    def search(self, keyword: str) -> List[Term]:
        return [t for t in self.all_terms() if t.matches(keyword)]


class PromptService:
    def __init__(self, scenes: List[PromptScene]):
        self._scenes = scenes
        self._by_key = {s.key: s for s in scenes}

    def all_scenes(self) -> List[PromptScene]:
        return self._scenes

    def get(self, key: str) -> Optional[PromptScene]:
        return self._by_key.get(key)


class BattleService:
    def __init__(self, battles: List[Battle]):
        self._battles = battles

    def all(self) -> List[Battle]:
        return self._battles