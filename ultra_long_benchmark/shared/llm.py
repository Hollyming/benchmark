from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


@dataclass
class OfflineLLMClient:
    prefix: str = "offline"

    def complete(self, prompt: str) -> str:
        first_line = prompt.strip().splitlines()[0] if prompt.strip() else "empty prompt"
        return f"[{self.prefix}] deterministic response for: {first_line[:120]}"


def make_llm_client() -> LLMClient:
    provider = os.getenv("ULB_LLM_PROVIDER", "offline").lower()
    if provider != "offline":
        return OfflineLLMClient(prefix=f"{provider}-placeholder")
    return OfflineLLMClient()

