<div align="center">

# 仝娘之家 · The Home of AI-musume

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![在线访问](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E8%AE%BF%E9%97%AE-ai--musume-f46f3f?logo=github&logoColor=white)](https://whaylu.github.io/ai-musume/)

[![GitHub stars](https://img.shields.io/github/stars/whaylu/ai-musume?style=social)](https://github.com/whaylu/ai-musume/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/whaylu/ai-musume?style=social)](https://github.com/whaylu/ai-musume/network/members)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/whaylu/ai-musume/pulls)

</div>

> 把主流 AI 大模型拟人化成角色，用图鉴、能力雷达、术语翻译、命运邂逅、知识测试的方式，让技术不再枯燥。

一个 **Python (Flask + Jinja2) + 原生 HTML/CSS/JS** 的科普站点。
收录 **19 位**国内外主流 AI 大模型，核心逻辑以**面向对象**方式组织，
且**库与数据严格分离**——`core.py` 不含任何本项目数据，可以直接复用到别的项目。

---

## 快速开始

```bash
# 1. 安装唯一依赖
pip install flask

# 2. 启动
python app.py

# 3. 浏览器打开
# http://127.0.0.1:5000
```

**环境要求**：Python 3.11+（用到了 `dataclass`、`Protocol`、`removeprefix`、类型注解）。

---

## 目录结构

```
.
├── app.py                    Flask 入口：组装依赖 + 定义路由（很薄）
├── core.py                   通用 OOP 库：所有领域模型、服务、搜索子系统（不含数据）
├── data.py                   项目数据：19 位角色 / 新闻 / 术语 / 对决 / 测试题 / 预言
├── intro.html                网站介绍（独立打印用，不参与 Web 服务）
├── LICENSE                   本项目采用的 MIT 协议
├── THIRD_PARTY_LICENSES      命运邂逅所参考项目的 MIT 许可全文
├── templates/                Jinja2 模板
│   ├── base.html             所有页面的骨架
│   ├── home.html             首页
│   ├── gallery.html          图鉴 + 搜索结果
│   ├── detail.html           角色详情
│   ├── discover.html         命运邂逅
│   ├── news.html             新闻列表
│   ├── terms.html            大白话术语
│   ├── section.html          特别栏目（八角笼 / 大测试 / 大模型预言）
│   ├── about.html            关于页
│   ├── _character_card.html  角色卡片局部模板
│   └── _news_card.html       新闻卡片局部模板
└── static/
    ├── style.css             全站样式
    ├── app.js                最小交互脚本（约 150 行）
    └── imgs/                 所有图片
```

---

## 三层架构

| 文件 | 类型 | 职责 | 复用性 |
|---|---|---|---|
| `core.py` | 通用库 | 领域模型 + 业务服务 + 搜索子系统，**不依赖 Flask、不含具体数据** | ★★★★★ |
| `data.py` | 项目数据 | import core 后填充具体内容 | ★★☆☆☆ |
| `app.py` | Web 应用 | 组装依赖 + 定义路由，**不含业务逻辑** | ★☆☆☆☆ |

**核心原则**：`core.py` 里如果混着"DeepSeek""ChatGPT"这些具体数据，别人想用它就必须改源码——那就叫"可复制"而不是"可复用"。

---

## 核心模块

### 领域模型

| 类 | 用途 |
|---|---|
| `AiCharacter` | 角色模型，含 `search_fields()` 与 `matches()` |
| `NewsItem` | 新闻条目 |
| `Term` | 术语条目 |
| `Battle` / `Fighter` | 八角笼对决 |
| `QuizOption` / `QuizQuestion` | 测试题与选项 |
| `Prediction` | 预言条目（三态：已应验 / 待观察 / 已打脸） |
| `FilterTag` / `DiscoverHit` | 命运邂逅的标签与命中结果 |
| `ExternalSite` / `AboutItem` / `SectionMeta` | 辅助模型 |

### 业务服务

| 类 | 用途 |
|---|---|
| `CharacterService` | 角色：`all / featured / get / search / count` |
| `NewsService` | 新闻：`all / latest / search` |
| `TermService` | 术语：`levels / list_by_level / all_terms / search` |
| `BattleService` | 对决：`all` |
| `DiscoverService` | **命运邂逅**：按标签分制推荐 |
| `QuizService` | **大测试**：随机抽题、判分、给点评 |
| `PredictionService` | **大模型预言**：按三态过滤、统计 |
| `SearchService` | **聚合搜索**：一次查角色 + 新闻 + 术语 |

所有服务都通过**构造函数注入依赖**，不自己 new 任何东西。

---

## 搜索子系统

搜索不是 `if keyword in text` 那么简单。`core.py` 里有一整套独立的搜索子系统：

| 组件 | 职责 |
|---|---|
| `Searchable`（Protocol） | 定义"什么叫可搜"——只要实现 `search_fields()` 就行 |
| `WeightedField` | 带权重的可搜字段（名称 3x / 标签 2x / 正文 1x） |
| `SearchHit` | 单条命中：对象 + 分数 + 命中字段 + 高亮预览 |
| `SearchQuery` | 结构化查询：包含词 / 排除词 / 分页 |
| `Page` / `SearchResult` | 分页结果与完整结果容器 |
| `SynonymMap` | 同义词策略：搜 `DS` 也能找到 DeepSeek |
| `score_object` | 打分器：完全匹配 60 / 前缀 40 / 子串 20，封顶 100 |
| `SearchSource` | 单一类型搜索源 |
| `SearchService` | 聚合多个源，按相关度排序 |
| `Suggester` | 自动补全 |
| `SearchHistory` | 搜索历史 |

**支持的语法**：
- 多关键词 AND：`开源 中国`
- 排除：`开源 -国产`
- 同义词扩展：`DS` → `deepseek / 深度求索`

---

## 复用 `core.py`

`core.py` 不依赖 Flask、不含任何本项目数据，可以独立使用：

```python
from core import AiCharacter, CharacterService

# 造几个你自己的角色
chars = [
    AiCharacter(id="cat", name="猫娘", code="01", title="家里蹲"),
    AiCharacter(id="dog", name="犬娘", code="02", title="忠诚卫士"),
]

svc = CharacterService(chars)

svc.all()              # → [猫娘, 犬娘]
svc.get("cat")         # → 猫娘对象
svc.search("忠诚")     # → [犬娘]
svc.count()            # → 2
```

`core.py` 顶部声明了 `__version__` 和 `__all__`，明确告知哪些名字是公开 API。

---

## 技术要点

- **`@dataclass`**：自动生成 `__init__ / __repr__ / __eq__`，字段即文档
- **`@property`**：`logo_url`、`a_wins`、`hostname` 等派生值不存数据，按需计算
- **`Protocol`**：`Searchable` 用结构化类型定义"可搜"，不强制继承
- **依赖注入**：服务不自己 new 依赖，全部构造时传入
- **组合模式**：`SearchService` 组合多个 `SearchSource`
- **工厂方法**：`SearchService.from_services()` 一行组装三件套
- **工厂函数**：`create_app()` 让"创建"与"配置"分离，方便测试
- **Jinja2 自动转义**：不需要手写 `escapeHTML()`
- **前端只做交互**：JS 约 150 行，负责新闻滑动、复制按钮、自动补全、页面过渡

---

## 页面一览

| 路径 | 页面 |
|---|---|
| `/` | 首页（看板 / 精选 / 命运邂逅 / 术语入口 / 特别栏目 / 站外推荐） |
| `/gallery` | 图鉴全集 |
| `/discover?tags=…` | 命运邂逅（分制推荐） |
| `/search?q=…` | 聚合搜索结果 |
| `/character/<id>` | 角色详情 |
| `/news` | 新闻列表 |
| `/terms/<level>` | 大白话术语（entry / advanced / hardcore / meme） |
| `/section/octagon` | 虚拟八角笼 |
| `/section/quiz` | 仝娘大测试（GET 抽题 / POST 判分） |
| `/section/prediction` | 大模型预言 |
| `/about` | 关于 |

---

## 常见问题

**Q：为什么把数据放在 `data.py` 而不是 `core.py`？**
A：为了"库与数据分离"。`core.py` 保持通用，别人 import 它时不会被卷入一堆无关的仝娘数据。

**Q：`core.py` 里的服务不读数据库，那数据从哪来？**
A：由 `app.py` 在 `create_app()` 里组装：从 `data.py` 取常量 → 传给服务构造函数。要换数据库时只改这一步。

**Q：前端为什么几乎不写 JS？**
A：内容渲染交给 Jinja2，路由交给 Flask，交互才轮到 JS。这样前后端职责清晰，Python 占比最重。

**Q：命运邂逅是怎么做的？**
A：选中的标签是加分项，不是必须项——命中越多分越高，一个都不命中的角色不出现。标签从角色的 `main_tags / nationality / versions.price / stats` 自动派生，新增角色无需手动维护。

**Q：大测试的题是固定的吗？**
A：题库 25 道，每次随机抽 10 道。表单里藏 `question_ids`，保证"用户看到的就是判分用的"。

---

## 致谢与许可

- 本项目采用 **MIT** 协议开源，详见根目录的 [`LICENSE`](LICENSE)。
- 「命运邂逅」模块参考并修改自开源项目 [柚子社攻略站（TigerFong / Yuzusoft_Guide）](https://github.com/TigerFong/Yuzusoft_Guide)，该项目采用 MIT 协议。按 MIT 协议要求，原项目的许可全文已保留在 [`THIRD_PARTY_LICENSES`](THIRD_PARTY_LICENSES) 中，相关源文件头部也保留了原作者的版权声明。
- 站内所有 AI 模型名称、Logo 与商标归各自公司所有；本项目仅作学习与演示用途，不构成任何商业推荐。