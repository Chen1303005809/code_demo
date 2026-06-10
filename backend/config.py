"""环境变数读取，单例配置。"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# prompts.yaml 固定路径：与 config.py 同目录
_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.yaml"


def _load_prompts() -> dict:
    """读取固定位置的 prompts.yaml，文件不存在时返回空字典。"""
    if _PROMPTS_PATH.is_file():
        with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    return {}


class Config:
    def __init__(self) -> None:
        _prompts = _load_prompts()

        # LightRag 基础地址（不含 /query/stream，代码内拼接）
        self.llm_api_url: str = os.environ["LLM_API_URL"]
        # Bearer Token（LightRag 如不需要则不设此变量；代码空值时不发送 Authorization 头）
        self.llm_api_key: str = os.environ.get("LLM_API_KEY", "")
        # LightRag 查询模式（mix / hybrid / local / global / naive）
        self.llm_query_mode: str = os.environ.get("LLM_QUERY_MODE", "mix")
        self.llm_timeout_ms: int = int(os.environ.get("LLM_TIMEOUT_MS", "60000"))
        # 用户提示词模板 —— 从 prompts.yaml 读取，默认纯透传
        self.llm_user_prompt_template: str = _prompts.get(
            "user_prompt_template", "{query}"
        )
        self.max_concurrency: int = int(os.environ.get("MAX_CONCURRENCY", "3"))
        self.db_path: str = os.environ.get("DB_PATH", "./data/history.db")


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


# ── 项目级配置解析 ─────────────────────────────────

class EffectiveConfig:
    """合并全局配置与项目级覆盖后的有效配置。"""

    def __init__(self, project: dict | None = None) -> None:
        base = get_config()
        if project:
            self.llm_api_url = project.get("llm_api_url") or base.llm_api_url
        else:
            self.llm_api_url = base.llm_api_url

        self.llm_api_key: str = (
            project.get("llm_api_key") if project and project.get("llm_api_key")
            else base.llm_api_key
        )

        if project:
            self.llm_query_mode = project.get("llm_query_mode") or base.llm_query_mode
        else:
            self.llm_query_mode = base.llm_query_mode

        self.llm_timeout_ms: int = base.llm_timeout_ms

        if project:
            self.llm_user_prompt_template = project.get("prompt_template") or base.llm_user_prompt_template
        else:
            self.llm_user_prompt_template = base.llm_user_prompt_template

        self.max_concurrency: int = base.max_concurrency
        self.db_path: str = base.db_path