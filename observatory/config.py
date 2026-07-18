"""Environment configuration for the LLM endpoint.

The app must open without an endpoint configured (browsing history works
offline), so loading is lazy: `load_llm_config` returns None when unset and
`require_llm_config` fails fast with an actionable message at run start.
"""

import os
from dataclasses import dataclass

ENV_BASE_URL = "TACHIKOMA_LLM_BASE_URL"
ENV_API_KEY = "TACHIKOMA_LLM_API_KEY"


@dataclass(frozen=True)
class LLMConfig:
    """Connection settings for the LiteLLM OpenAI-compatible proxy.

    Args:
        base_url: Proxy base URL including the /v1 suffix.
        api_key: LiteLLM master key.
    """

    base_url: str
    api_key: str


def load_llm_config() -> LLMConfig | None:
    """Read endpoint settings from the environment.

    Returns:
        The config, or None when either variable is missing/empty.
    """
    base_url = os.environ.get(ENV_BASE_URL, "").strip()
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not base_url or not api_key:
        return None
    return LLMConfig(base_url=base_url, api_key=api_key)


def require_llm_config() -> LLMConfig:
    """Load endpoint settings or fail with a clear message.

    Returns:
        The loaded config.

    Raises:
        RuntimeError: If either environment variable is not set.
    """
    config = load_llm_config()
    if config is None:
        raise RuntimeError(
            f"LLM endpoint not configured: set {ENV_BASE_URL} and {ENV_API_KEY} "
            "before starting a run."
        )
    return config
