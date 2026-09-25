# 仝娘之家 · The Home of AI-musume

> 把主流 AI 大模型拟人化成角色，用图鉴、能力雷达、术语翻译、模型对比的方式，让技术不再枯燥。

一个 **Python (Flask + Jinja2) + 原生 HTML/CSS/JS** 的科普站点。
核心逻辑以**面向对象**方式组织，且**库与数据严格分离**——`core.py` 不含任何本项目数据，可以直接复用到别的项目。

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

**环境要求**：Python 3.11+（用到了 `dataclass`、`removeprefix`、类型注解）。

---

## 目录结构

```
.
├── app.py                   Flask 入口：组装依赖 + 定义路由（很薄）
├── core.py                  通用 OOP 库：所有领域模型与服务（不含数据）
├── data.py                  项目数据：角色 / 新闻 / 术语 / 提示词 / 对决
├── intro.html               项目文档（独立打印用，不参与 Web 服务）
├── templates/               Jinja2 模板
│   ├── base.html            所有页面的骨架
│   ├── home.html            首页
│   ├── gallery.html         图鉴 + 搜索结果
│   ├── detail.html          角色详情
│   ├── news.html            新闻列表
│   ├── terms.html           术语列表
│   ├── prompts.html         提示词档案
│   ├── section.html         特别栏目（八角笼等）
│   ├── about.html           关于页
│   ├── _character_card.html 角色卡片局部模板
│   └── _news_card.html      新闻卡片局部模板
└── static/
    ├── style.css            全站样式
    ├── app.js               最小交互脚本（约 90 行）
    └── imgs/                所有图片
```

---

## 三层架构

| 文件 | 类型 | 职责 | 复用性 |
|---|---|---|---|
| `core.py` | 通用库 | 领域模型 + 业务服务，**不依赖 Flask、不含具体数据** | ★★★★★ |
| `data.py` | 项目数据 | import core 后填充具体内容 | ★★☆☆☆ |
| `app.py` | Web 应用 | 组装依赖 + 定义路由，**不含业务逻辑** | ★☆☆☆☆ |

**核心原则**：`core.py` 里如果混着"DeepSeek""ChatGPT"这些具体数据，别人想用它就必须改源码——那就叫"可复制"而不是"可复用"。

---

## 核心模块

### `core.py` — 通用 OOP 库

**领域模型**（`@dataclass`）

| 类 | 用途 |
|---|---|
| `AiCharacter` | 角色模型，含 `matches()` 全字段模糊匹配 |
| `NewsItem` | 新闻条目 |
| `Term` | 术语条目 |
| `PromptScene` / `Prompt` | 提示词场景与单条提示词 |
| `Battle` / `Fighter` | 八角笼对决 |
| `ExternalSite` | 站外推荐站点，带 `hostname` 派生属性 |
| `AboutItem` | 关于页条目 |
| `SectionMeta` | 特别栏目元信息 |

**业务服务**

| 类 | 用途 |
|---|---|
| `CharacterService` | 角色：`all / featured / get / search / count` |
| `NewsService` | 新闻：`all / latest / search` |
| `TermService` | 术语：`levels / list_by_level / search` |
| `PromptService` | 提示词：`all_scenes / get` |
| `BattleService` | 对决：`all` |
| `SearchService` | **聚合搜索**：一次调用查角色 + 新闻 + 术语 |

所有服务都通过**构造函数注入依赖**，不自己 new 任何东西。想换数据源（内存 / JSON / SQLite / API）只换传入对象，服务类本身不动。

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
- **依赖注入**：服务不自己 new 依赖，全部构造时传入
- **聚合服务**：`SearchService` 把多个可搜对象聚合成一个入口
- **工厂函数**：`create_app()` 让"创建"与"配置"分离，方便测试
- **Jinja2 自动转义**：不需要手写 `escapeHTML()`
- **前端只做交互**：JS 仅约 90 行，负责新闻滑动、复制按钮、页面过渡

---

## 页面一览

| 路径 | 页面 |
|---|---|
| `/` | 首页（看板 / 精选 / 术语入口 / 特别栏目 / 站外推荐） |
| `/gallery` | 图鉴全集 |
| `/search?q=…` | 聚合搜索结果 |
| `/character/<id>` | 角色详情 |
| `/news` | 新闻列表 |
| `/terms/<level>` | 术语（entry / advanced / hardcore / meme） |
| `/prompts/<key>` | 提示词档案 |
| `/section/<key>` | 特别栏目（octagon / prediction / moments / catchphrase） |
| `/about` | 关于 |

---

## 常见问题

**Q：为什么把数据放在 `data.py` 而不是 `core.py`？**
A：为了"库与数据分离"。`core.py` 保持通用，别人 import 它时不会被卷入一堆无关的仝娘数据。

**Q：`core.py` 里的服务不读数据库，那数据从哪来？**
A：由 `app.py` 在 `create_app()` 里组装：从 `data.py` 取常量 → 传给服务构造函数。要换数据库时只改这一步。

**Q：前端为什么几乎不写 JS？**
A：内容渲染交给 Jinja2，路由交给 Flask，交互才轮到 JS。这样前后端职责清晰，Python 占比最重，也符合课程要求。

---

## 版权说明

站内所有 AI 模型名称、Logo 与商标归各自公司所有；本项目仅作学习与演示用途，不构成任何商业推荐。
