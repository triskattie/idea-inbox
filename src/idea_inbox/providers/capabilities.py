"""Capability declarations for optional provider adapters."""

from idea_inbox.core.capabilities import Capability, CapabilityKind, ConfigRequirement

CHAT_PROVIDER_ENV = "IDEA_INBOX_CHAT_PROVIDER"
EMBEDDING_PROVIDER_ENV = "IDEA_INBOX_EMBEDDING_PROVIDER"
OPENAI_BASE_URL_ENV = "IDEA_INBOX_OPENAI_BASE_URL"
OPENAI_API_KEY_ENV = "IDEA_INBOX_OPENAI_API_KEY"
OPENAI_CHAT_MODEL_ENV = "IDEA_INBOX_OPENAI_CHAT_MODEL"
OPENAI_EMBEDDING_MODEL_ENV = "IDEA_INBOX_OPENAI_EMBEDDING_MODEL"
OLLAMA_BASE_URL_ENV = "IDEA_INBOX_OLLAMA_BASE_URL"
OLLAMA_CHAT_MODEL_ENV = "IDEA_INBOX_OLLAMA_CHAT_MODEL"

PROVIDER_SELECTION_CAPABILITIES = {
    "mock": "mock-model-provider",
    "openai-compatible": "openai-compatible-model-provider",
    "ollama": "ollama-model-provider",
}


def provider_capabilities() -> tuple[Capability, ...]:
    """Return SDK-free metadata for installed provider adapter capabilities."""
    return (
        Capability(
            name="model-provider",
            kind=CapabilityKind.PROVIDER,
            dependencies=("core",),
            default_enabled=False,
            description="Generic selected chat/model provider boundary for cited query.",
            owner="idea-inbox.providers",
        ),
        Capability(
            name="none-credentials",
            kind=CapabilityKind.PROVIDER,
            dependencies=("core",),
            default_enabled=False,
            description="No-secret credential provider for local providers and tests.",
            owner="idea-inbox.providers",
        ),
        Capability(
            name="env-api-key-credentials",
            kind=CapabilityKind.PROVIDER,
            dependencies=("core",),
            default_enabled=False,
            description=(
                "Credential provider that resolves API keys from configured environment keys."
            ),
            owner="idea-inbox.providers",
        ),
        Capability(
            name="static-config-credentials",
            kind=CapabilityKind.PROVIDER,
            dependencies=("core",),
            default_enabled=False,
            description=(
                "Credential provider for explicitly supplied in-process static credentials."
            ),
            owner="idea-inbox.providers",
        ),
        Capability(
            name="mock-model-provider",
            kind=CapabilityKind.PROVIDER,
            dependencies=("model-provider", "none-credentials"),
            default_enabled=False,
            description="Deterministic offline model provider for tests and local harnesses.",
            owner="idea-inbox.providers",
        ),
        Capability(
            name="openai-compatible-model-provider",
            kind=CapabilityKind.PROVIDER,
            dependencies=("model-provider", "env-api-key-credentials"),
            default_enabled=False,
            configuration=(
                ConfigRequirement(
                    key=OPENAI_BASE_URL_ENV,
                    required_when_enabled=True,
                    secret=False,
                    description="OpenAI-compatible API base URL.",
                ),
                ConfigRequirement(
                    key=OPENAI_API_KEY_ENV,
                    required_when_enabled=True,
                    secret=True,
                    description="OpenAI-compatible API key credential handle.",
                ),
                ConfigRequirement(
                    key=OPENAI_CHAT_MODEL_ENV,
                    required_when_enabled=True,
                    secret=False,
                    description="OpenAI-compatible chat model name.",
                ),
            ),
            description="OpenAI-compatible chat/completions adapter boundary.",
            owner="idea-inbox.providers",
        ),
        Capability(
            name="ollama-model-provider",
            kind=CapabilityKind.PROVIDER,
            dependencies=("model-provider", "none-credentials"),
            default_enabled=False,
            configuration=(
                ConfigRequirement(
                    key=OLLAMA_BASE_URL_ENV,
                    required_when_enabled=True,
                    secret=False,
                    description="Local Ollama API base URL.",
                ),
                ConfigRequirement(
                    key=OLLAMA_CHAT_MODEL_ENV,
                    required_when_enabled=True,
                    secret=False,
                    description="Ollama chat model name.",
                ),
            ),
            description="Local Ollama generate adapter boundary.",
            owner="idea-inbox.providers",
        ),
        Capability(
            name="embedding-provider",
            kind=CapabilityKind.PROVIDER,
            dependencies=("core",),
            default_enabled=False,
            configuration=(
                ConfigRequirement(
                    key=EMBEDDING_PROVIDER_ENV,
                    required_when_enabled=True,
                    secret=False,
                    description="Selected embedding provider capability.",
                ),
                ConfigRequirement(
                    key=OPENAI_EMBEDDING_MODEL_ENV,
                    required_when_enabled=False,
                    secret=False,
                    description="OpenAI-compatible embedding model name for future adapters.",
                ),
            ),
            description="Placeholder embedding provider contract; vector search remains disabled.",
            owner="idea-inbox.providers",
        ),
    )
