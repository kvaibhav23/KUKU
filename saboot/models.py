"""Data contracts shared across the pipeline. Rules that must always hold live in validators."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from saboot.config import OFFICIAL_LAW_HOST_SUFFIXES

EvidenceId = Annotated[str, StringConstraints(pattern=r"^E[1-9]\d*(\.m[1-9]\d*)?$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class DisputeType(StrEnum):
    DEPOSIT = "deposit"
    CONSUMER_REFUND = "consumer_refund"
    UNPAID_SALARY = "unpaid_salary"
    NOTICE_EXPLAINER = "notice_explainer"
    OTHER = "other"


class Language(StrEnum):
    HINDI = "hi"
    ENGLISH = "en"
    HINGLISH = "hinglish"
    OTHER = "other"


class EventSource(StrEnum):
    EVIDENCE = "evidence"
    USER_STATEMENT = "user_statement"


class GapSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrustLabel(StrEnum):
    VERIFIED_LAW = "verified_law"
    YOUR_EVIDENCE = "your_evidence"
    GENERAL_GUIDANCE = "general_guidance"


class ProvisionStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NEEDS_MANUAL_PASTE = "NEEDS_MANUAL_PASTE"


class SupportVerdict(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    NOT_SUPPORTED = "not_supported"


class FirewallAction(StrEnum):
    RESOLVED = "resolved"
    BLOCKED_UNKNOWN_ID = "blocked_unknown_id"
    BLOCKED_PATTERN = "blocked_pattern"
    REGENERATED = "regenerated"
    STRIPPED = "stripped"
    DOWNGRADED = "downgraded"


class TripwireOrigin(StrEnum):
    RULE = "rule"
    LLM = "llm"


class Strict(BaseModel):
    """Unknown fields are errors, so an LLM cannot add fields that downstream code would ignore."""

    model_config = ConfigDict(extra="forbid")


def is_official_law_url(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and host.endswith(OFFICIAL_LAW_HOST_SUFFIXES)


class LawProvision(Strict):
    """One provision in the law store. See non-negotiable rule 1 in CLAUDE.md."""

    id: str = Field(min_length=1)
    act_title: str = Field(min_length=1)
    provision_ref: str = Field(min_length=1)
    heading: str | None = None
    text: str | None
    status: ProvisionStatus
    source_url: str
    retrieved_on: date | None = None
    jurisdiction: str = Field(min_length=1)
    # Deliberately has no default: a model law must be recorded as non-binding on purpose.
    binding: bool
    dispute_types: list[DisputeType] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_rule_one(self) -> Self:
        if not is_official_law_url(self.source_url):
            raise ValueError(f"source_url is not an official https source: {self.source_url}")
        if self.status is ProvisionStatus.NEEDS_MANUAL_PASTE:
            if self.text is not None:
                raise ValueError("NEEDS_MANUAL_PASTE records must have text=None")
            return self
        if self.text is None or not self.text.strip():
            raise ValueError("VERIFIED records must carry the verbatim text")
        if self.retrieved_on is None:
            raise ValueError("VERIFIED records must record retrieved_on")
        return self


class EvidenceItem(Strict):
    """One uploaded file, sealed at upload."""

    evidence_id: EvidenceId
    file_name: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    mime_type: str = Field(min_length=1)
    sha256: Sha256Hex
    sealed_at_utc: datetime
    sealed_at_ist: datetime
    description: str | None = None


class CustodyEntry(Strict):
    """One append-only line in the session's custody log."""

    seq: int = Field(ge=1)
    action: str = Field(min_length=1)
    evidence_id: EvidenceId
    sha256: Sha256Hex
    at_utc: datetime
    at_ist: datetime
    note: str | None = None


class Sourced(Strict):
    """A fact in the case file: it either points at evidence or is marked as the user's word."""

    source: EventSource
    evidence_refs: list[EvidenceId] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_source_needs_a_ref(self) -> Self:
        if self.source is EventSource.EVIDENCE and not self.evidence_refs:
            raise ValueError("source='evidence' requires at least one evidence_ref")
        return self


class Party(Strict):
    role: str = Field(min_length=1)
    name: str | None = None


class MoneyAmount(Sourced):
    amount_inr: Decimal = Field(ge=0)
    description: str = Field(min_length=1)


class KeyDate(Sourced):
    label: str = Field(min_length=1)
    on: date


class CaseEvent(Sourced):
    event_date: date | None = None
    date_text: str | None = None
    description: str = Field(min_length=1)


class CaseFile(Strict):
    dispute_type: DisputeType
    language: Language
    state: str | None = None
    parties: list[Party] = Field(default_factory=list)
    amounts: list[MoneyAmount] = Field(default_factory=list)
    key_dates: list[KeyDate] = Field(default_factory=list)
    events: list[CaseEvent] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    desired_outcome: str | None = None


class Gap(Strict):
    key: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: GapSeverity
    other_side_can_confirm: bool
    closed: bool = False


class TripwireHit(Strict):
    key: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    origin: TripwireOrigin


class LadderStep(Strict):
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    due_on: date | None = None
    date_note: str | None = None

    @model_validator(mode="after")
    def undated_step_must_say_why(self) -> Self:
        if self.due_on is None and not (self.date_note and self.date_note.strip()):
            raise ValueError("a step without due_on must explain why in date_note")
        return self


class FirewallDecision(Strict):
    sentence: str
    action: FirewallAction
    label: TrustLabel | None = None
    provision_id: str | None = None
    evidence_id: EvidenceId | None = None
    verdict: SupportVerdict | None = None
    reason: str | None = None
