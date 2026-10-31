# ============================================================
# 本站「命运邂逅」路由（/discover）的交互概念基于以下开源项目修改：
#
#     Yuzusoft_Guide · https://github.com/TigerFong/Yuzusoft_Guide
#     Copyright (c) TigerFong
#     Licensed under the MIT License
#
# 开源项目 LICENSE 文件已保留在仓库根目录（THIRD_PARTY_LICENSES）。
# ============================================================
"""仝娘之家 · Flask 入口（很薄，只做转接）"""
from datetime import date

from flask import Flask, render_template, abort, request, jsonify, redirect, url_for

from core import (
    CharacterService, NewsService, TermService,
    BattleService, SearchService, Suggester, SynonymMap, SearchHistory,
    SearchSource, DiscoverService, QuizService, PredictionService,
    NotFound,
)
from data import (
    CHARACTERS, NEWS, TERMS, TERM_META, BATTLES,
    EXTERNAL_SITES, ABOUT_ITEMS, SECTIONS,
    QUIZ_QUESTIONS, PREDICTIONS,
)

START_DATE = date(2026, 9, 8)
PER_PAGE = 12


SYNONYMS = SynonymMap({
    "ds":       ["deepseek", "深度求索"],
    "gpt":      ["chatgpt", "openai"],
    "ai":       ["人工智能"],
    "llm":      ["大语言模型", "大模型"],
    "rag":      ["检索增强生成"],
    "开源":     ["open source", "open-source"],
    "闭源":     ["closed source"],
    "长文本":   ["长上下文", "长文"],
})


def _build_tag_views(tags_grouped, selected_keys):
    selected_set = set(selected_keys)
    result = {}
    for group, tags in tags_grouped.items():
        result[group] = []
        for t in tags:
            is_selected = t.key in selected_set
            if is_selected:
                new_keys = [k for k in selected_keys if k != t.key]
            else:
                new_keys = list(selected_keys) + [t.key]
            result[group].append({
                "key": t.key,
                "label": t.label,
                "count": t.count,
                "is_selected": is_selected,
                "next_query": ",".join(new_keys),
            })
    return result


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "ai-musume-dev-key"

    char_service = CharacterService(CHARACTERS)
    news_service = NewsService(NEWS)
    term_service = TermService(TERMS, TERM_META)
    battle_service = BattleService(BATTLES)
    discover_service = DiscoverService(CHARACTERS)
    quiz_service = QuizService(QUIZ_QUESTIONS)
    prediction_service = PredictionService(PREDICTIONS)

    search_service = SearchService.from_services(
        char_service, news_service, term_service, synonyms=SYNONYMS,
    )

    suggester = Suggester([
        SearchSource("characters", char_service.all()),
        SearchSource("news", news_service.all()),
        SearchSource("terms", term_service.all_terms()),
    ])

    history = SearchHistory(max_items=10)

    # ---------- 首页 ----------
    @app.route("/")
    def home():
        days = (date.today() - START_DATE).days

        grouped = discover_service.all_tags_grouped()
        all_tags = [t for tags in grouped.values() for t in tags]
        all_tags.sort(key=lambda t: (-t.count, t.label))
        quick_tags = all_tags[:5]

        return render_template(
            "home.html",
            nav="home",
            days=max(0, days),
            total=char_service.count(),
            characters=char_service.featured(4),
            news=news_service.latest(3),
            term_meta=term_service.levels(),
            sections=[SECTIONS[k] for k in ("octagon", "prediction", "quiz", "catchphrase")],
            external_sites=EXTERNAL_SITES,
            discover_quick_tags=quick_tags,
            history=history.all(),
        )

    # ---------- 命运邂逅 ----------
    @app.route("/discover")
    def discover():
        raw = request.args.get("tags", "")
        selected_keys = [t.strip() for t in raw.split(",") if t.strip()]

        hits = discover_service.rank(selected_keys)
        tags_grouped = discover_service.all_tags_grouped()
        selected_tags = discover_service.tag_labels(selected_keys)

        return render_template(
            "discover.html",
            nav=None,
            hits=hits,
            tag_views=_build_tag_views(tags_grouped, selected_keys),
            selected_tags=selected_tags,
            total=len(hits),
        )

    # ---------- 仝娘大测试（GET 随机抽题 / POST 判分）----------
    @app.route("/section/quiz", methods=["GET", "POST"])
    def section_quiz():
        meta = SECTIONS["quiz"]

        if request.method == "POST":
            raw_ids = request.form.get("question_ids", "")
            try:
                ids = [int(x) for x in raw_ids.split(",") if x.strip()]
            except ValueError:
                ids = []

            questions = (
                quiz_service.by_ids(ids) if ids
                else quiz_service.draw(10)
            )

            answers = {}
            for q in questions:
                v = request.form.get(f"q{q.id}")
                if v is not None:
                    try:
                        answers[q.id] = int(v)
                    except (ValueError, TypeError):
                        pass

            result = quiz_service.grade(questions, answers)
            return render_template(
                "section.html",
                nav=None,
                meta=meta,
                quiz_questions=questions,
                quiz_result=result,
            )

        questions = quiz_service.draw(10)
        return render_template(
            "section.html",
            nav=None,
            meta=meta,
            quiz_questions=questions,
            quiz_result=None,
        )

    # ---------- 图鉴 ----------
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
            search_result=None,
            history=history.all(),
        )

    # ---------- 搜索 ----------
    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)

        if not q:
            return gallery()

        history.push(q)

        result = search_service.search_full(q, page=page, per_page=PER_PAGE)

        return render_template(
            "gallery.html",
            nav=None,
            characters=[],
            q=q,
            title=f"搜索结果：{q}",
            en_title="SEARCH RESULTS",
            code="SEARCH RESULTS",
            search_result=result,
            history=history.all(),
        )

    @app.route("/search/history/clear", methods=["POST"])
    def clear_history():
        history.clear()
        return redirect(request.referrer or url_for("home"))

    # ---------- 自动补全 API ----------
    @app.route("/api/suggest")
    def api_suggest():
        q = request.args.get("q", "").strip()
        return jsonify(suggester.suggest(q, limit=8))

    # ---------- 搜索结果详情 API ----------
    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"total": 0, "elapsed_ms": 0, "groups": {}})
        result = search_service.search_full(q)
        return jsonify({
            "total": result.total,
            "elapsed_ms": round(result.elapsed_ms, 2),
            "groups": {
                name: [
                    {
                        "name": h.display_name,
                        "score": h.score,
                        "matched_fields": h.matched_fields,
                        "matched_keywords": h.matched_keywords,
                    }
                    for h in hits
                ]
                for name, hits in result.grouped.items()
            },
        })

    # ---------- 角色详情 ----------
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

    # ---------- 特别栏目（八角笼 / 预言 / 口头禅）----------
    @app.route("/section/<key>")
    def section(key):
        if key == "quiz":
            return section_quiz()

        meta = SECTIONS.get(key)
        if not meta:
            abort(404)

        battles = battle_service.all() if key == "octagon" else None
        predictions = prediction_service.all() if key == "prediction" else None
        prediction_stats = prediction_service.stats() if key == "prediction" else None

        return render_template(
            "section.html",
            nav=None,
            meta=meta,
            battles=battles,
            predictions=predictions,
            prediction_stats=prediction_stats,
        )

    # ---------- 关于 ----------
    @app.route("/about")
    def about():
        return render_template("about.html", nav="about", items=ABOUT_ITEMS)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)