from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentUnderTest(BaseModel):
    name: str
    url: str | None = None
    protocol: str = Field(pattern=r"^(http|websocket|callable)$")
    description: str
    capabilities: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_url_for_network_protocols(self):
        if self.protocol in ("http", "websocket") and not self.url:
            raise ValueError(f"url is required for protocol '{self.protocol}'")
        return self


class WorldStateInput(BaseModel):
    entities: list[dict[str, Any]] = Field(default_factory=list)
    catalog: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class TestConfig(BaseModel):
    total: int = Field(ge=1)
    positive: int = Field(ge=0)
    negative: int = Field(ge=0)


class LLMConfig(BaseModel):
    provider: str = Field(pattern=r"^(anthropic|openai|google|openrouter|ollama)$")
    model: str


class AssetSpec(BaseModel):
    """An external data source ATA samples from to build test material.

    ``format`` is inferred from the path extension when omitted. ``role`` decides
    what the sample becomes: ``entities`` / ``data_sample`` are ingested into
    world_state; ``knowledge_base`` is reserved for RAG. ``target`` is an optional
    JSON pointer overriding where the ingested data is placed in world_state.
    """

    id: str
    path: str
    format: str | None = Field(default=None, pattern=r"^(csv|jsonl)$")
    role: str = Field(default="entities", pattern=r"^(entities|data_sample|knowledge_base)$")
    sample_size: int = Field(default=50, ge=1)
    seed: int = 0
    description: str | None = None
    target: str | None = None


class YAMLInput(BaseModel):
    agent_under_test: AgentUnderTest
    world_state: WorldStateInput
    test_config: TestConfig
    llm_config: LLMConfig
    assets: list[AssetSpec] = Field(default_factory=list)
