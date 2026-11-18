# ============================================================
# 仝娘之家 · GLM聊天室（ChatService）
# ------------------------------------------------------------
# 设计原则与 core.py 一致：
#   * 本文件不依赖 Flask、不含任何 API Key（密钥走环境变量）
#   * 通过构造函数注入配置，方便替换服务商 / 写测试
#   * 复用 data.py 里的角色字段拼 system prompt，不额外维护数据
#
# 默认接智谱 GLM 免费模型（glm-4-flash，OpenAI 兼容接口）。
# 想换硅基流动 / ModelScope，只需改 base_url + model + key。
#
# 环境变量：
#   ZAI_API_KEY    智谱开放平台密钥（必填，没有则聊天室自动降级为“未配置”）
#   CHAT_BASE_URL  兼容接口地址，默认 https://open.bigmodel.cn/api/paas/v4
#   CHAT_MODEL     模型名，默认 glm-4-flash
# ============================================================
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

__all__ = ["ChatConfig", "ChatMessage", "ChatService", "persona_from_character"]


@dataclass
class ChatConfig:
    """聊天服务配置。所有敏感信息从环境变量读取，绝不写进代码。"""
    api_key: str = field(default_factory=lambda: os.environ.get("ZAI_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.environ.get(
            "CHAT_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
        )
    )
    model: str = field(
        default_factory=lambda: os.environ.get("CHAT_MODEL", "glm-4-flash")
    )
    timeout: int = 60
    max_history: int = 12          # 最多带回多少轮，防止 token 爆掉
    max_tokens: int = 512
    temperature: float = 0.8

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    @property
    def available(self) -> bool:
        return bool(self.api_key)


@dataclass
class ChatMessage:
    role: str        # system / user / assistant
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


def persona_from_character(char) -> str:
    """把 AiCharacter 的既有字段拼成 system prompt，不新增数据。

    这样每个仝娘的说话风格都来自 data.py 里已经写好的设定，
    新增角色无需为聊天单独维护任何东西。
    """
    name = getattr(char, "name", "") or "AI 助手"
    title = getattr(char, "title", "") or ""
    quote = getattr(char, "quote", "") or ""
    bio = getattr(char, "bio", "") or ""
    # bio 太长，取前 200 字作为人设锚点即可
    bio_short = bio[:200] + ("…" if len(bio) > 200 else "")
    return (
        f"你现在扮演「{name}」（外号：{title}），一个被拟人化的 AI 角色。"
        f"你的口头禅是：“{quote}”。\n"
        f"背景设定：{bio_short}\n"
        "请以这个角色的口吻、性格和说话习惯来回应用户，"
        "保持人设一致、轻松有趣；遇到知识性问题时仍要准确，"
        "不要编造不存在的事实。每次回复控制在 150 字以内。"
    )


class ChatService:
    """GLM聊天室服务。不依赖 Flask，可被任意入口复用。"""

    def __init__(self, config: Optional[ChatConfig] = None,
                 session: Optional[requests.Session] = None):
        self.config = config or ChatConfig()
        self._session = session or requests.Session()

    # ---- 对外主方法：返回助手回复文本 ----
    def reply(self, persona: str, history: List[ChatMessage],
              user_text: str) -> str:
        if not self.config.available:
            raise RuntimeError("未配置 ZAI_API_KEY，GLM聊天室不可用。")
        if not user_text.strip():
            return ""

        messages: List[Dict[str, str]] = [ChatMessage("system", persona).to_dict()]
        # 只截取最近 max_history 条，避免上下文无限增长
        for m in history[-self.config.max_history:]:
            messages.append(m.to_dict())
        messages.append(ChatMessage("user", user_text).to_dict())

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        resp = self._session.post(
            self.config.endpoint, headers=headers, json=payload,
            timeout=self.config.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"上游 API 返回 {resp.status_code}：{resp.text[:200]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"上游返回格式异常：{data}") from exc
