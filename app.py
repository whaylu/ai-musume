"""仝娘之家 · Flask 入口（很薄，只做转接）"""
from datetime import date

from flask import Flask, render_template, abort, request

from core import (
    CharacterService, NewsService, TermService, PromptService,
    BattleService, SearchService,
    NotFound,
)
from data import (
    CHARACTERS, NEWS, TERMS, TERM_META, PROMPT_SCENES, BATTLES,
    EXTERNAL_SITES, ABOUT_ITEMS, SECTIONS,
)

START_DATE = date(2026, 9, 8)


def create_app() -> Flask:
    app = Flask(__name__)

    # 依赖组装（一个地方集中 new，方便以后换实现）
    char_service = CharacterService(CHARACTERS)
    news_service = NewsService(NEWS)
    term_service = TermService(TERMS, TERM_META)
    prompt_service = PromptService(PROMPT_SCENES)
    battle_service = BattleService(BATTLES)
    search_service = SearchService(char_service, news_service, term_service)

    # ---------- 首页 ----------
    @app.route("/")
    def home():
        days = (date.today() - START_DATE).days
        return render_template(
            "home.html",
            nav="home",
            days=max(0, days),
            total=char_service.count(),
            characters=char_service.featured(4),
            news=news_service.latest(3),
            term_meta=term_service.levels(),
            sections=[SECTIONS[k] for k in ("octagon", "prediction", "moments", "catchphrase")],
            external_sites=EXTERNAL_SITES,
        )

    # ---------- 图鉴 / 搜索 ----------
    @app.route("/gallery")
    def gallery():
        return render_template(
            "gallery.html",
            nav="gallery",
            characters=char_service.all(),
            q="",
            title="仝娘图鉴全集",
            en_title="CHARACTER ARCHIVES",
            code="ALL ARCHIVES",
            extra_html=None,
        )

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        if not q:
            return gallery()
        result = search_service.search(q)
        return render_template(
            "gallery.html",
            nav=None,
            characters=result["characters"],
            q=q,
            title=f"搜索结果：{q}",
            en_title="SEARCH RESULTS",
            code="SEARCH RESULTS",
            extra_html=None,
            matched_news=result["news"],
            matched_terms=result["terms"],
        )

    @app.route("/character/<char_id>")
    def character_detail(char_id):
        try:
            char = char_service.get(char_id)
        except NotFound:
            abort(404)
        return render_template("detail.html", nav=None, char=char)

    # ---------- 新闻 ----------
    @app.route("/news")
    def news_gallery():
        return render_template("news.html", nav="news", news=news_service.all())

    # ---------- 术语 ----------
    @app.route("/terms")
    @app.route("/terms/<level>")
    def terms(level: str = "entry"):
        meta = term_service.levels().get(level)
        if not meta:
            level = "entry"
            meta = term_service.levels()[level]
        return render_template(
            "terms.html",
            nav=None,
            levels=term_service.levels(),
            active=level,
            meta=meta,
            terms=term_service.list_by_level(level),
        )

    # ---------- 提示词 ----------
    @app.route("/prompts")
    @app.route("/prompts/<key>")
    def prompts(key: str = None):
        scenes = prompt_service.all_scenes()
        if not scenes:
            abort(404)
        if key is None:
            key = scenes[0].key
        scene = prompt_service.get(key)
        if not scene:
            abort(404)
        return render_template(
            "prompts.html", nav=None, scenes=scenes, active=scene,
        )

    # ---------- 特别栏目 ----------
    @app.route("/section/<key>")
    def section(key):
        meta = SECTIONS.get(key)
        if not meta:
            abort(404)
        battles = battle_service.all() if key == "octagon" else None
        return render_template("section.html", nav=None, meta=meta, battles=battles)

    # ---------- 关于 ----------
    @app.route("/about")
    def about():
        return render_template("about.html", nav="about", items=ABOUT_ITEMS)

    return app

# 供 Gunicorn 在服务器上直接调用
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)