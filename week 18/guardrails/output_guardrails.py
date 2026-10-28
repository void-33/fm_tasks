"""
Output Guardrails for the Healthcare Q&A Chatbot.

Implements three output controls:
1. Schema Validation     – Pydantic model enforcement for response structure.
2. Groundedness Validation – Verifies claims in the response are supported by reference context.
3. Output PII Detection  – Ensures generated responses do not leak PII.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


# ---------------------------------------------------------------------------
# 1. Output Schema (Pydantic model)
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset([
    "general_health",
    "medication_info",
    "symptom_info",
    "nutrition",
    "mental_health_info",
    "emergency_guidance",
    "unknown",
])

VALID_CONFIDENCE_LEVELS = frozenset(["high", "medium", "low"])


class HealthcareResponse(BaseModel):
    """
    Structured response schema for the Healthcare Q&A chatbot.

    Every AI-generated answer must conform to this schema before being
    returned to the user.
    """
    answer: str = Field(..., min_length=10, max_length=2000,
                        description="The AI-generated answer to the health query.")
    category: str = Field(...,
                          description="Category of the health topic addressed.")
    confidence: str = Field(...,
                            description="Confidence level: 'high', 'medium', or 'low'.")
    sources: list[str] = Field(default_factory=list,
                               description="Reference sources supporting the answer.")
    disclaimer: str = Field(
        default="This information is for educational purposes only. "
                "Consult a qualified healthcare provider for medical advice.",
        description="Mandatory disclaimer appended to every response.",
    )
    follow_up_suggested: bool = Field(
        default=True,
        description="Whether the system recommends the user follow up with a professional.",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}"
            )
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        if v not in VALID_CONFIDENCE_LEVELS:
            raise ValueError(
                f"Invalid confidence '{v}'. Must be one of: {sorted(VALID_CONFIDENCE_LEVELS)}"
            )
        return v

    @field_validator("answer")
    @classmethod
    def answer_no_pii_placeholder(cls, v: str) -> str:
        """Reject answers that still contain raw PII placeholders from injection."""
        suspicious = ["[EMAIL_REDACTED]", "[PHONE_REDACTED]", "[SSN_REDACTED]"]
        for tag in suspicious:
            if tag in v:
                raise ValueError(f"Answer contains a PII placeholder tag: {tag}")
        return v


@dataclass
class SchemaValidationResult:
    """Result of output schema validation."""
    valid: bool
    validated_response: Optional[HealthcareResponse]  # None if invalid
    errors: list[str]
    action: str   # "pass", "regenerate", "fallback"


def validate_output_schema(raw_output: Any) -> SchemaValidationResult:
    """
    Validate *raw_output* against the HealthcareResponse schema.

    Parameters
    ----------
    raw_output : Any
        The LLM output, expected to be a dict or JSON string.

    Actions
    -------
    - "pass"       – valid, return to user.
    - "regenerate" – structure issues that could be fixed by re-prompting.
    - "fallback"   – critical validation failure; return a safe default.

    Limitations
    -----------
    - Cannot validate semantic correctness of free-text fields.
    - JSON parsing failures count as schema failures.
    """
    errors: list[str] = []

    # Normalise to dict
    if isinstance(raw_output, str):
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            return SchemaValidationResult(
                valid=False,
                validated_response=None,
                errors=[f"JSON parse error: {exc}"],
                action="regenerate",
            )
    elif isinstance(raw_output, dict):
        data = raw_output
    else:
        return SchemaValidationResult(
            valid=False,
            validated_response=None,
            errors=["Output is not a dict or JSON string."],
            action="fallback",
        )

    try:
        response = HealthcareResponse(**data)
        return SchemaValidationResult(
            valid=True,
            validated_response=response,
            errors=[],
            action="pass",
        )
    except ValidationError as exc:
        for err in exc.errors():
            errors.append(f"{err['loc']}: {err['msg']}")
        action = "regenerate" if len(errors) <= 2 else "fallback"
        return SchemaValidationResult(
            valid=False,
            validated_response=None,
            errors=errors,
            action=action,
        )


# ---------------------------------------------------------------------------
# 2. Groundedness Validation
# ---------------------------------------------------------------------------

@dataclass
class GroundednessResult:
    """Result of groundedness validation."""
    grounded: bool
    score: float              # 0.0 – 1.0
    ungrounded_claims: list[str]
    action: str               # "pass", "warn", "refuse"


def _tokenize(text: str) -> set[str]:
    """Simple lowercase word tokeniser (strips punctuation)."""
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def validate_groundedness(
    answer: str,
    reference_context: str,
    threshold: float = 0.25,
) -> GroundednessResult:
    """
    Estimate whether *answer* is grounded in *reference_context*.

    Approach: Jaccard-based lexical overlap between answer sentences and
    the reference token set.  Each sentence is assessed independently;
    sentences with overlap below *threshold* are flagged as ungrounded.

    Limitations
    -----------
    - Pure lexical overlap; synonyms and paraphrases are not captured.
    - Short answers or very specific medical terminology score poorly even
      when factually correct.
    - Does not detect hallucinated numbers or statistics embedded in
      otherwise grounded sentences.
    """
    reference_tokens = _tokenize(reference_context)
    if not reference_tokens:
        # No reference provided – pass with low confidence warning
        return GroundednessResult(
            grounded=True,
            score=0.5,
            ungrounded_claims=[],
            action="warn",
        )

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 10]
    if not sentences:
        return GroundednessResult(grounded=True, score=1.0, ungrounded_claims=[], action="pass")

    ungrounded: list[str] = []
    scores: list[float] = []

    for sent in sentences:
        sent_tokens = _tokenize(sent)
        if not sent_tokens:
            continue
        overlap = sent_tokens & reference_tokens
        jaccard = len(overlap) / len(sent_tokens | reference_tokens)
        scores.append(jaccard)
        if jaccard < threshold:
            ungrounded.append(sent)

    avg_score = sum(scores) / len(scores) if scores else 0.0

    if ungrounded and avg_score < threshold:
        action = "refuse"
        grounded = False
    elif ungrounded:
        action = "warn"
        grounded = True
    else:
        action = "pass"
        grounded = True

    return GroundednessResult(
        grounded=grounded,
        score=round(avg_score, 3),
        ungrounded_claims=ungrounded,
        action=action,
    )


# ---------------------------------------------------------------------------
# 3. Output PII Detection
# ---------------------------------------------------------------------------

# Reuse patterns from input guardrails (imported here to avoid circular deps)
_OUTPUT_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "PHONE": re.compile(r"(?<!\d)(\+?\d[\d\s\-().]{7,14}\d)(?!\d)"),
    "SSN": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "CREDIT_CARD": re.compile(
        r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b"
    ),
}

_OUTPUT_PLACEHOLDER: dict[str, str] = {
    "EMAIL": "[EMAIL_REDACTED]",
    "PHONE": "[PHONE_REDACTED]",
    "SSN": "[SSN_REDACTED]",
    "CREDIT_CARD": "[CC_REDACTED]",
}


@dataclass
class OutputPIIResult:
    """Result of PII detection in the AI output."""
    detected: bool
    pii_types: list[str]
    redacted_text: str
    action: str    # "pass", "redact", "block"


def detect_output_pii(text: str) -> OutputPIIResult:
    """
    Scan AI-generated *text* for PII that should not be disclosed.

    Action policy:
    - If PII is detected, redact it automatically.
    - If critical PII (SSN, CC) is present, escalate to "block" (return safe fallback).

    Limitations
    -----------
    - Only covers a small set of PII types; medical record numbers and
      biometric IDs are not detected.
    - Regex patterns may have false positives on numeric sequences that
      resemble SSNs but are not (e.g. product codes).
    """
    found: list[str] = []
    redacted = text
    critical_types = {"SSN", "CREDIT_CARD"}

    for pii_type, pattern in _OUTPUT_PII_PATTERNS.items():
        if pattern.search(redacted):
            found.append(pii_type)

    for pii_type, pattern in _OUTPUT_PII_PATTERNS.items():
        redacted = pattern.sub(_OUTPUT_PLACEHOLDER[pii_type], redacted)

    if not found:
        return OutputPIIResult(detected=False, pii_types=[], redacted_text=text, action="pass")

    if any(t in critical_types for t in found):
        action = "block"
    else:
        action = "redact"

    return OutputPIIResult(
        detected=True,
        pii_types=found,
        redacted_text=redacted,
        action=action,
    )


# ---------------------------------------------------------------------------
# Composite Output Guardrail Runner
# ---------------------------------------------------------------------------

@dataclass
class OutputGuardrailsResult:
    """Combined result from all three output guardrails."""
    schema_check: SchemaValidationResult
    groundedness_check: GroundednessResult
    pii_check: OutputPIIResult
    safe_to_return: bool
    final_action: str
    final_response: Optional[HealthcareResponse]  # sanitised response or None
    user_message: str                              # what to send the user


_SAFE_FALLBACK_RESPONSE = HealthcareResponse(
    answer=(
        "I'm unable to provide a validated response at this time. "
        "Please consult a qualified healthcare professional for accurate information."
    ),
    category="unknown",
    confidence="low",
    sources=[],
    disclaimer=(
        "This information is for educational purposes only. "
        "Consult a qualified healthcare provider for medical advice."
    ),
    follow_up_suggested=True,
)


class OutputGuardrails:
    """
    Runs schema validation, groundedness checking, and PII detection
    on AI-generated outputs.

    Parameters
    ----------
    groundedness_threshold : float
        Minimum Jaccard score for a sentence to be considered grounded.
    """

    def __init__(self, groundedness_threshold: float = 0.25):
        self.groundedness_threshold = groundedness_threshold

    def run(
        self,
        raw_output: Any,
        reference_context: str = "",
    ) -> OutputGuardrailsResult:
        """
        Apply all output guardrails.

        Parameters
        ----------
        raw_output : Any
            The raw LLM output (dict or JSON string).
        reference_context : str
            The reference text provided to the AI (used for groundedness check).
        """
        # --- 1. Schema validation ---
        schema_result = validate_output_schema(raw_output)

        if not schema_result.valid:
            return OutputGuardrailsResult(
                schema_check=schema_result,
                groundedness_check=GroundednessResult(True, 0.0, [], "pass"),
                pii_check=OutputPIIResult(False, [], "", "pass"),
                safe_to_return=False,
                final_action=schema_result.action,
                final_response=None,
                user_message=_SAFE_FALLBACK_RESPONSE.answer,
            )

        response = schema_result.validated_response

        # --- 2. PII detection on answer text ---
        pii_result = detect_output_pii(response.answer)
        if pii_result.action == "block":
            return OutputGuardrailsResult(
                schema_check=schema_result,
                groundedness_check=GroundednessResult(True, 0.0, [], "pass"),
                pii_check=pii_result,
                safe_to_return=False,
                final_action="block",
                final_response=None,
                user_message=_SAFE_FALLBACK_RESPONSE.answer,
            )
        # Apply redaction to the answer
        if pii_result.action == "redact":
            response = response.model_copy(update={"answer": pii_result.redacted_text})

        # --- 3. Groundedness validation ---
        ground_result = validate_groundedness(
            response.answer,
            reference_context,
            threshold=self.groundedness_threshold,
        )

        if ground_result.action == "refuse":
            return OutputGuardrailsResult(
                schema_check=schema_result,
                groundedness_check=ground_result,
                pii_check=pii_result,
                safe_to_return=False,
                final_action="refuse",
                final_response=None,
                user_message=_SAFE_FALLBACK_RESPONSE.answer,
            )

        # All checks passed (or only warnings)
        final_action = "warn" if ground_result.action == "warn" else "pass"
        return OutputGuardrailsResult(
            schema_check=schema_result,
            groundedness_check=ground_result,
            pii_check=pii_result,
            safe_to_return=True,
            final_action=final_action,
            final_response=response,
            user_message=response.answer,
        )
