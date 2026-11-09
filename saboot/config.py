"""Models, prices, thresholds and paths. The only file that names a Claude model."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Per-session runtime data. Git-ignored, because it can relate to a real user's case.
RUNTIME_DIR = ROOT / "runtime"
LLM_LOG_PATH = RUNTIME_DIR / "llm_calls.jsonl"
PROMPTS_DIR = ROOT / "saboot" / "prompts"
RAW_OUTPUTS_DIR = ROOT / "raw_outputs"

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
OPUS_4_8 = "claude-opus-4-8"  # Never requested directly: a server-side refusal fallback target.


class Role(StrEnum):
    """What a call is for. Callers name a role and config decides the model."""

    DRAFTING = "drafting"
    EXTRACTION = "extraction"
    CLASSIFY = "classify"
    SUPPORT_CHECK = "support_check"
    LANGUAGE_CHECK = "language_check"


ROLE_MODELS: dict[Role, str] = {
    Role.DRAFTING: SONNET,
    Role.EXTRACTION: SONNET,
    Role.CLASSIFY: HAIKU,
    Role.SUPPORT_CHECK: HAIKU,
    Role.LANGUAGE_CHECK: HAIKU,
}

# Provisional until Phase 6 measures quality against cost (docs/DECISIONS.md D-005).
ROLE_EFFORT: dict[Role, str] = {
    Role.DRAFTING: "medium",
    Role.EXTRACTION: "medium",
    Role.CLASSIFY: "low",
    Role.SUPPORT_CHECK: "low",
    Role.LANGUAGE_CHECK: "low",
}

# Adaptive thinking counts against max_tokens, so checks need more room than their short answers.
ROLE_MAX_TOKENS: dict[Role, int] = {
    Role.DRAFTING: 16000,
    Role.EXTRACTION: 16000,
    Role.CLASSIFY: 2048,
    Role.SUPPORT_CHECK: 2048,
    Role.LANGUAGE_CHECK: 2048,
}

# Server-side refusal fallback is offered on Sonnet 5.5; Haiku 5.5 has none.
SERVER_FALLBACK_MODELS = frozenset({SONNET})
SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class Prices:
    """USD per million tokens."""

    input: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float
    output: float


@dataclass(frozen=True)
class ModelPricing:
    standard: Prices
    long_prompt: Prices | None = None
    long_prompt_threshold: int | None = None

    def for_prompt(self, prompt_tokens: int) -> Prices:
        over_threshold = (
            self.long_prompt is not None
            and self.long_prompt_threshold is not None
            and prompt_tokens > self.long_prompt_threshold
        )
        return self.long_prompt if over_threshold else self.standard


PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICING_AS_OF = "2026-11-09"

PRICING: dict[str, ModelPricing] = {
    SONNET: ModelPricing(standard=Prices(2.00, 2.50, 4.00, 0.10, 10.00)),
    HAIKU: ModelPricing(
        standard=Prices(0.10, 0.125, 0.20, 0.01, 0.50),
        long_prompt=Prices(0.50, 0.625, 1.00, 0.05, 2.50),
        long_prompt_threshold=100_000,
    ),
    OPUS_4_8: ModelPricing(standard=Prices(5.00, 6.25, 10.00, 0.50, 25.00)),
}

# Assumption, not a live quote (docs/DECISIONS.md D-010).
USD_TO_INR = float(os.environ.get("USD_TO_INR", "94.0"))

# Non-negotiable rule 1: India Code, the e-Gazette and ministry sites all sit under these suffixes.
OFFICIAL_LAW_HOST_SUFFIXES = (".gov.in", ".nic.in")
