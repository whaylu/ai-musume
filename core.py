"""
仝娘之家 · 通用业务核心库（Core Library）
============================================

这个模块提供一套可复用的 OOP 骨架：
    - 领域模型（AiCharacter, NewsItem, Term, ...）
    - 业务服务（CharacterService, NewsService, ...）

它 **不包含任何具体数据**，也 **不依赖 Flask 或任何 Web 框架**。
任何人只要传入自己的数据列表，就能直接使用这些服务类。

快速上手：
    from core import AiCharacter, CharacterService

    chars = [AiCharacter(id="a", name="A", code="01", title="...")]
    svc = CharacterService(chars)
    svc.search("开源")     # -> [AiCharacter(...)]

版本：0.3.0
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

__version__ = "0.3.0"

__all__ = [
    # 异常
    "DomainError", "NotFound",
    # 模型
    "CharacterVersion", "AiCharacter",
    "NewsItem", "Term",
    "Prompt", "PromptScene",
    "Fighter", "Battle",
    "ExternalSite", "AboutItem", "SectionMeta",
    # 服务
    "CharacterService", "NewsService", "TermService",
    "PromptService", "BattleService", "SearchService",
]


# ============================================================
# 异常
# ============================================================
class DomainError(Exception):
    """业务异常基类。任何业务规则的违反，都应抛它的子类。"""


class NotFound(DomainError):
    """请求的资源不存在。"""


# ============================================================
# 领域模型
# ============================================================
@dataclass
class CharacterVersion:
    """角色某一代模型版本的规格。"""
    name: str
    params: str
    context: str
    price: str


@dataclass
class AiCharacter:
    """
    通用角色模型。

    只要字段齐全，你可以用它描述任何"拟人化对象"——AI 模型、游戏角色、
    动物图鉴、甚至公司员工档案。方法与字段无关，只与语义相关。
    """
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

    # ---- 派生属性：从 id 推导资源路径，不需要在数据里重复写 ----
    @property
    def logo_url(self) -> str:
        return f"imgs/{self.id}logo.png"

    @property
    def char_url(self) -> str:
        return f"imgs/{self.id}char.png"

    # ---- 业务方法：把"匹配规则"收进模型里，而不是散在路由 ----
    def matches(self, keyword: str) -> bool:
        """
        全字段模糊匹配。任何一处命中即返回 True。
        keyword 为空时视为"不过滤"，返回 True。
        """
        if not keyword:
            return True
        kw = keyword.lower()

        texts = [self.name, self.title, self.id, self.company,
                 self.nationality, self.quote, self.bio]
        if any(kw in (t or "").lower() for t in texts):
            return True
        if any(kw in t.lower() for t in self.main_tags):
            return True
        if any(kw in t.lower() for t in self.modality_tags):
            return True
        return any(
            kw in v.name.lower() or kw in v.params.lower() or kw in v.context.lower()
            for v in self.versions
        )


@dataclass
class NewsItem:
    """通用新闻 / 公告条目。"""
    id: int
    img: str
    date: str
    title: str
    desc: str
    is_archive: bool = False
    url: str = ""

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        kw = keyword.lower()
        return kw in self.title.lower() or kw in self.desc.lower()


@dataclass
class Term:
    """通用术语条目：术语名 + 大白话解释。"""
    name: str
    plain: str

    def matches(self, keyword: str) -> bool:
        if not keyword:
            return True
        kw = keyword.lower()
        return kw in self.name.lower() or kw in self.plain.lower()


@dataclass
class Prompt:
    """单条提示词模板。"""
    scene: str
    name: str
    when: str
    prompt: str
    tips: str


@dataclass
class PromptScene:
    """提示词场景：一组同主题的提示词。"""
    key: str
    title: str
    code: str
    img: str
    desc: str
    prompts: List[Prompt] = field(default_factory=list)


@dataclass
class Fighter:
    """对决一方。"""
    id: str
    name: str
    response: str


@dataclass
class Battle:
    """一场对决：问题 + A/B 双方 + 裁决。"""
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
    """站外推荐站点。"""
    name: str
    tagline: str
    url: str
    icon: str = ""
    img: str = ""

    @property
    def hostname(self) -> str:
        """从 URL 自动解析出显示用的域名。"""
        try:
            h = urlparse(self.url).hostname or self.url
            return h.removeprefix("www.")
        except Exception:
            return self.url


@dataclass
class AboutItem:
    """关于页的「标签 / 说明」条目。"""
    label: str
    value: str


@dataclass
class SectionMeta:
    """特别栏目的元信息。"""
    key: str
    title: str
    code: str
    bg: str


# ============================================================
# 业务服务
# ============================================================
class CharacterService:
    """
    角色数据访问服务。

    构造时接收一个角色列表（可以是内存数据、也可以从数据库读来），
    内部建立 id 索引，对外只暴露 all / featured / get / search / count。
    """

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
    """新闻数据访问服务。"""

    def __init__(self, news: List[NewsItem]):
        self._news = news

    def all(self) -> List[NewsItem]:
        return self._news

    def latest(self, n: int = 3) -> List[NewsItem]:
        return self._news[:n]

    def search(self, keyword: str) -> List[NewsItem]:
        return [n for n in self._news if n.matches(keyword)]


class TermService:
    """术语数据访问服务。按层级组织。"""

    def __init__(self, terms: Dict[str, List[Term]],
                 meta: Dict[str, Dict[str, str]]):
        self._terms = terms
        self._meta = meta

    def levels(self) -> Dict[str, Dict[str, str]]:
        return self._meta

    def list_by_level(self, level: str) -> List[Term]:
        return self._terms.get(level, [])

    def search(self, keyword: str) -> List[Term]:
        hits: List[Term] = []
        for items in self._terms.values():
            hits.extend(t for t in items if t.matches(keyword))
        return hits


class PromptService:
    """提示词场景访问服务。"""

    def __init__(self, scenes: List[PromptScene]):
        self._scenes = scenes
        self._by_key = {s.key: s for s in scenes}

    def all_scenes(self) -> List[PromptScene]:
        return self._scenes

    def get(self, key: str) -> Optional[PromptScene]:
        return self._by_key.get(key)


class BattleService:
    """对决数据访问服务。"""

    def __init__(self, battles: List[Battle]):
        self._battles = battles

    def all(self) -> List[Battle]:
        return self._battles


class SearchService:
    """
    聚合搜索服务。

    把多个可搜对象聚合成一个统一入口，返回分类结果。
    以后加新的可搜对象，只需在构造函数里多注入一个服务。
    """

    def __init__(self,
                 characters: CharacterService,
                 news: NewsService,
                 terms: TermService):
        self.characters = characters
        self.news = news
        self.terms = terms

    def search(self, keyword: str) -> Dict[str, list]:
        if not keyword:
            return {"characters": [], "news": [], "terms": []}
        return {
            "characters": self.characters.search(keyword),
            "news": self.news.search(keyword),
            "terms": self.terms.search(keyword),
        }