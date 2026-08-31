import os

PROVIDER_NAMES = ["openai", "anthropic", "ollama"]


def _is_configured(name):
    if name == "openai":
        return bool(os.environ.get("OPENAI_KEY"))
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if name == "ollama":
        return bool(os.environ.get("OLLAMA_HOST"))
    return False  # pragma: no cover


def list_available_providers():
    """Providers with the env vars needed to construct them actually set."""
    return [name for name in PROVIDER_NAMES if _is_configured(name)]


def get_provider(name):
    """Instantiate the requested provider adapter by name."""
    if name == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider()
    raise ValueError(f"Unknown or unconfigured provider: {name}")
