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


class YAMLInput(BaseModel):
    agent_under_test: AgentUnderTest
    world_state: WorldStateInput
    test_config: TestConfig
    llm_config: LLMConfig
