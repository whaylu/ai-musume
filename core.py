# ============================================================
# 命运邂逅模块（DiscoverService / FilterTag / DiscoverHit）
# 的交互概念基于以下开源项目修改：
#
#     Yuzusoft_Guide · https://github.com/TigerFong/Yuzusoft_Guide
#     Copyright (c) TigerFong
#     Licensed under the MIT License
#
# 原项目 LICENSE 文件已保留在仓库根目录（THIRD_PARTY_LICENSES）。
# 本站仅对标签维度、筛选机制与数据结构做了重构，未直接复制原项目代码。
# ============================================================
"""
仝娘之家 · 通用业务核心库（Core Library）
============================================
v0.7 · 新增命运邂逅：按标签筛选角色
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple
from urllib.parse import urlparse
import html as _html
import random
import time


__version__ = "0.7.0"

__all__ = [
    "DomainError", "NotFound",
    "CharacterVersion", "AiCharacter", "NewsItem", "Term",
    "Fighter", "Battle",
    "ExternalSite", "AboutItem", "SectionMeta",
    "CharacterService", "NewsService", "TermService",
    "BattleService", "DiscoverService",
    "QuizOption", "QuizQuestion", "QuizService",
    "Prediction", "PredictionService",
    "FilterTag", "DiscoverHit",
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
    """解析 "-" 排除语义。"""
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
    if not raw:
        return []
    return [k for k in raw.replace("\u3000", " ").split() if k]


@dataclass
class SearchQuery:
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
    if not keyword_groups:
        return None

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
# 命运邂逅：分制推荐
# ============================================================
GROUP_WEIGHTS = {
    "许可": 1.0,
    "地区": 0.8,
    "价格": 1.2,
    "场景": 1.5,
}


@dataclass
class FilterTag:
    """筛选标签。值对象。"""
    key: str
    label: str
    group: str
    count: int = 0


@dataclass
class DiscoverHit:
    """命运邂逅的一条推荐结果。值对象。"""
    character: "AiCharacter"
    score: float
    max_score: float
    matched_tags: List["FilterTag"] = field(default_factory=list)

    @property
    def percent(self) -> int:
        if self.max_score <= 0:
            return 0
        return round(self.score / self.max_score * 100)

    @property
    def matched_count(self) -> int:
        return len(self.matched_tags)


class DiscoverService:
    """
    命运邂逅服务：分制推荐。

    - 每个选中标签有基础分 10，乘以所属维度的权重
    - 角色每命中一个标签，累加对应分数
    - 一个标签都没命中的角色不出现
    - 按总分降序，同分按名字字母序

    标签从角色的现有字段自动派生——main_tags 决定许可，
    nationality 决定地区，versions 的 price 决定价格档，
    stats 决定场景能力。新增角色时无需手动维护标签映射。
    """

    def __init__(self, characters: List["AiCharacter"]):
        self._characters = characters
        self._tag_defs = self._build_tag_defs()
        self._char_tags: Dict[str, Set[str]] = {
            c.id: self._derive_tags(c) for c in characters
        }

    def _build_tag_defs(self) -> List[FilterTag]:
        return [
            FilterTag("open-source",   "开源",       "许可"),
            FilterTag("closed-source", "闭源",       "许可"),
            FilterTag("china",         "国产",       "地区"),
            FilterTag("overseas",      "海外",       "地区"),
            FilterTag("free",          "免费可用",   "价格"),
            FilterTag("low-cost",      "低价 API",   "价格"),
            FilterTag("subscription",  "订阅制",     "价格"),
            FilterTag("coding",        "擅长编程",   "场景"),
            FilterTag("writing",       "中文写作",   "场景"),
            FilterTag("long-text",     "超长上下文", "场景"),
            FilterTag("multimodal",    "多模态",     "场景"),
            FilterTag("reasoning",     "深度推理",   "场景"),
        ]

    def _derive_tags(self, char: "AiCharacter") -> Set[str]:
        tags: Set[str] = set()
        mt = " ".join(char.main_tags)
        prices = " ".join(v.price for v in char.versions)

        if "开源" in mt: tags.add("open-source")
        if "闭源" in mt: tags.add("closed-source")

        if char.nationality == "中国": tags.add("china")
        elif char.nationality: tags.add("overseas")

        if "免费" in prices: tags.add("free")
        if "低价" in prices or "极低" in prices: tags.add("low-cost")
        if "订阅" in prices: tags.add("subscription")

        if char.stats.get("代码构建", 0) >= 90: tags.add("coding")
        if char.stats.get("中文理解", 0) >= 95: tags.add("writing")
        if char.stats.get("长文本处理", 0) >= 95: tags.add("long-text")
        if char.stats.get("多模态", 0) >= 90: tags.add("multimodal")
        if char.stats.get("逻辑推理", 0) >= 95: tags.add("reasoning")

        return tags

    def all_tags_grouped(self) -> Dict[str, List[FilterTag]]:
        """
        按维度分组返回全部标签，带匹配数。

        分组顺序按 GROUP_WEIGHTS 降序（场景 > 价格 > 许可 > 地区），
        组内按匹配数降序，让最可能被点的标签排前面。
        """
        raw: Dict[str, List[FilterTag]] = {}
        for tag in self._tag_defs:
            count = sum(1 for tags in self._char_tags.values() if tag.key in tags)
            if count == 0:
                continue
            raw.setdefault(tag.group, []).append(
                FilterTag(tag.key, tag.label, tag.group, count)
            )

        ordered: Dict[str, List[FilterTag]] = {}
        for group in sorted(raw.keys(), key=lambda g: -GROUP_WEIGHTS.get(g, 1.0)):
            ordered[group] = sorted(raw[group], key=lambda t: (-t.count, t.label))
        return ordered

    def rank(self, selected_keys: List[str]) -> List[DiscoverHit]:
        """按分制排序。没选标签时返回全部角色（分数为 0）。"""
        if not selected_keys:
            return [DiscoverHit(c, 0.0, 0.0) for c in self._characters]

        by_key = {t.key: t for t in self._tag_defs}
        selected = [by_key[k] for k in selected_keys if k in by_key]
        if not selected:
            return [DiscoverHit(c, 0.0, 0.0) for c in self._characters]

        max_score = sum(10.0 * GROUP_WEIGHTS.get(t.group, 1.0) for t in selected)

        hits: List[DiscoverHit] = []
        for c in self._characters:
            char_tags = self._char_tags[c.id]
            matched = [t for t in selected if t.key in char_tags]
            if not matched:
                continue
            score = sum(10.0 * GROUP_WEIGHTS.get(t.group, 1.0) for t in matched)
            hits.append(DiscoverHit(c, score, max_score, matched))

        hits.sort(key=lambda h: (-h.score, h.character.name))
        return hits

    def tag_labels(self, keys: List[str]) -> List[FilterTag]:
        by_key = {t.key: t for t in self._tag_defs}
        return [by_key[k] for k in keys if k in by_key]

# ============================================================
# 仝娘大测试
# ============================================================
@dataclass
class QuizOption:
    """测试题的一个选项。"""
    text: str
    is_correct: bool = False


@dataclass
class QuizQuestion:
    """一道测试题：题干 + 4 个选项 + 正确答案解释。"""
    id: int
    question: str
    options: List[QuizOption]
    explanation: str = ""

    def correct_index(self) -> int:
        for i, o in enumerate(self.options):
            if o.is_correct:
                return i
        return -1


class QuizService:
    """
    仝娘大测试服务。

    - `all()`：拿全部题目
    - `draw(n)`：从题库随机抽 n 题
    - `by_ids(ids)`：按 id 列表还原题目（判分时用）
    - `grade(questions, answers)`：对指定题目判分
    """

    def __init__(self, questions: List[QuizQuestion]):
        self._questions = questions
        self._by_id = {q.id: q for q in questions}

    def all(self) -> List[QuizQuestion]:
        return self._questions

    def total(self) -> int:
        return len(self._questions)

    def draw(self, n: int = 10) -> List[QuizQuestion]:
        """随机抽 n 题，n 大于题库时返回全部。"""
        n = min(n, len(self._questions))
        return random.sample(self._questions, n)

    def by_ids(self, ids: List[int]) -> List[QuizQuestion]:
        """按 id 列表还原题目，保持传入顺序。"""
        return [self._by_id[i] for i in ids if i in self._by_id]

    def grade(
        self,
        questions: List[QuizQuestion],
        answers: Dict[int, int],
    ) -> Dict[str, Any]:
        if not questions:
            return {"total": 0, "correct": 0, "score": 0,
                    "results": [], "comment": "没有题目"}

        results = []
        correct = 0
        for q in questions:
            chosen = answers.get(q.id, -1)
            ci = q.correct_index()
            ok = (chosen == ci)
            if ok:
                correct += 1
            results.append({
                "question": q,
                "chosen": chosen,
                "correct_index": ci,
                "is_correct": ok,
            })

        score = round(correct / len(questions) * 100)

        if score == 100:
            comment = "满分！你是 AI 圈真·大佬。"
        elif score >= 75:
            comment = "很棒，你对 AI 的理解已经很到位了。"
        elif score >= 50:
            comment = "及格线，基础还在，还能再补补。"
        elif score >= 25:
            comment = "还需努力，去「大白话术语」补补课吧。"
        else:
            comment = "来都来了，先去看看术语页再回来。"

        return {
            "total": len(questions),
            "correct": correct,
            "score": score,
            "results": results,
            "comment": comment,
        }

# ============================================================
# 大模型预言
# ============================================================
@dataclass
class Prediction:
    """
    一条关于 AI 未来的预言。

    status 三态：
        fulfilled —— 已应验
        pending   —— 待观察
        failed    —— 已打脸
    """
    id: int
    content: str
    source: str
    source_type: str          # 公司 / 人物 / 模型
    year: str                 # 预言时间
    target_year: str          # 预言目标年份
    confidence: int           # 可信度 0-100
    status: str
    commentary: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def status_label(self) -> str:
        return {"fulfilled": "已应验", "pending": "待观察", "failed": "已打脸"}.get(self.status, self.status)


class PredictionService:
    """大模型预言服务。"""

    def __init__(self, predictions: List[Prediction]):
        self._predictions = predictions

    def all(self) -> List[Prediction]:
        return self._predictions

    def by_status(self, status: str) -> List[Prediction]:
        return [p for p in self._predictions if p.status == status]

    def stats(self) -> Dict[str, int]:
        total = len(self._predictions)
        return {
            "total": total,
            "fulfilled": sum(1 for p in self._predictions if p.status == "fulfilled"),
            "pending": sum(1 for p in self._predictions if p.status == "pending"),
            "failed": sum(1 for p in self._predictions if p.status == "failed"),
        }

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


class BattleService:
    def __init__(self, battles: List[Battle]):
        self._battles = battles

    def all(self) -> List[Battle]:
        return self._battles