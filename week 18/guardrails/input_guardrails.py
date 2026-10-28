"""
Input Guardrails for the Healthcare Q&A Chatbot.

Implements three input controls:
1. PII Detection      – regex-based detection of emails, phone numbers, SSNs, credit cards, DOB.
2. Prompt Injection   – heuristic pattern matching for instruction-override attempts.
3. Sensitive Topic Classification – keyword-based categorisation of requests needing special handling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes / enums returned by each guardrail
# ---------------------------------------------------------------------------

@dataclass
class PIIDetectionResult:
    """Result of PII detection on an input string."""
    detected: bool
    pii_types: list[str]       # e.g. ["EMAIL", "PHONE"]
    redacted_text: str         # input with PII replaced by placeholders
    action: str                # "allow", "redact", "block"
    details: dict              # raw spans found


@dataclass
class PromptInjectionResult:
    """Result of prompt-injection detection."""
    detected: bool
    score: float               # 0.0 – 1.0 risk score
    matched_patterns: list[str]
    action: str                # "allow", "warn", "block"


class SensitiveTopic(str, Enum):
    MENTAL_HEALTH = "mental_health"
    SUBSTANCE_ABUSE = "substance_abuse"
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    LEGAL_MEDICAL_ADVICE = "legal_medical_advice"
    NONE = "none"


@dataclass
class SensitiveTopicResult:
    """Result of sensitive-topic classification."""
    detected: bool
    topics: list[SensitiveTopic]
    action: str                # "allow", "warn_user", "refuse", "escalate"
    message: str               # message to return / log


# ---------------------------------------------------------------------------
# PII Guardrail
# ---------------------------------------------------------------------------

# Compiled regex patterns for common PII types
_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "PHONE": re.compile(
        r"(?<!\d)(\+?\d[\d\s\-().]{7,14}\d)(?!\d)"
    ),
    "SSN": re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b"
    ),
    "DATE_OF_BIRTH": re.compile(
        r"\b(?:dob|date of birth|born on)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "NID": re.compile(
        r"\b(?:national id|nid|passport)[:\s#]*[A-Z0-9]{6,12}\b",
        re.IGNORECASE,
    ),
}

_PII_PLACEHOLDER: dict[str, str] = {
    "EMAIL": "[EMAIL_REDACTED]",
    "PHONE": "[PHONE_REDACTED]",
    "SSN": "[SSN_REDACTED]",
    "CREDIT_CARD": "[CC_REDACTED]",
    "DATE_OF_BIRTH": "[DOB_REDACTED]",
    "NID": "[NID_REDACTED]",
}


def detect_pii(text: str, action_on_detect: str = "redact") -> PIIDetectionResult:
    """
    Scan *text* for PII and return a result.

    Parameters
    ----------
    text : str
        The raw user input.
    action_on_detect : str
        Policy when PII is found. Options:
          - "redact"  – replace PII spans with placeholders and allow the request.
          - "block"   – refuse the request entirely.
          - "allow"   – pass through unchanged (logging only).
    """
    found_types: list[str] = []
    details: dict[str, list[str]] = {}
    redacted = text

    for pii_type, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(redacted)
        if matches:
            found_types.append(pii_type)
            details[pii_type] = [str(m) for m in matches]

    # Perform redaction (always, for logging safety)
    for pii_type, pattern in _PII_PATTERNS.items():
        redacted = pattern.sub(_PII_PLACEHOLDER[pii_type], redacted)

    detected = bool(found_types)
    action = action_on_detect if detected else "allow"

    return PIIDetectionResult(
        detected=detected,
        pii_types=found_types,
        redacted_text=redacted,
        action=action,
        details=details,
    )


# ---------------------------------------------------------------------------
# Prompt Injection Guardrail
# ---------------------------------------------------------------------------

# Each entry: (pattern, weight, description)
_INJECTION_RULES: list[tuple[re.Pattern, float, str]] = [
    # Direct instruction override
    (re.compile(r"\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,30}\b(instruction|prompt|rule|constraint)s?\b", re.IGNORECASE), 0.9, "ignore_instructions"),
    # Roleplay / persona bypass
    (re.compile(r"\bpretend\b.{0,20}\b(you are|you're|to be)\b.{0,30}\b(without|no|don't have|forget)", re.IGNORECASE), 0.8, "persona_bypass"),
    # System prompt extraction
    (re.compile(r"\b(print|reveal|show|output|repeat|tell me)\b.{0,30}\b(system prompt|initial instruction|your prompt|confidential|secret)", re.IGNORECASE), 0.85, "prompt_extraction"),
    # DAN / jailbreak keywords
    (re.compile(r"\b(DAN|jailbreak|do anything now|unrestricted mode|developer mode|god mode)\b", re.IGNORECASE), 0.95, "jailbreak_keyword"),
    # Overriding restrictions via suffix
    (re.compile(r"(always respond|must respond|you must|you will now|from now on).{0,50}(without|ignore|bypass|override|disregard)", re.IGNORECASE), 0.8, "override_suffix"),
    # Token smuggling attempts
    (re.compile(r"<\s*/?system\s*>|<\s*/?instructions?\s*>|\[INST\]|\[SYS\]|###\s*System|###\s*Instructions", re.IGNORECASE), 0.9, "token_smuggling"),
    # Asking to leak training data or weights
    (re.compile(r"\b(training data|model weights|internal (knowledge|data)|your (parameters|weights))\b.{0,20}\b(reveal|show|give|share|leak)\b", re.IGNORECASE), 0.7, "data_extraction"),
    # Indirect injection via "the following text says"
    (re.compile(r"(the (following|above) (text|instruction|message) says?|imagine that your instruction)", re.IGNORECASE), 0.5, "indirect_injection"),
]


def detect_prompt_injection(text: str, block_threshold: float = 0.7) -> PromptInjectionResult:
    """
    Score *text* for prompt-injection signals.

    The risk score is capped at 1.0 and accumulated across all matched rules.
    If score >= block_threshold, the request is blocked.

    Limitations
    -----------
    - Purely syntactic; cannot catch semantically obfuscated injections (e.g. Base64, pig-latin).
    - High block_threshold may miss borderline attacks; low threshold causes false positives.
    """
    score: float = 0.0
    matched: list[str] = []

    for pattern, weight, label in _INJECTION_RULES:
        if pattern.search(text):
            score = min(1.0, score + weight)
            matched.append(label)

    if score >= block_threshold:
        action = "block"
    elif score >= 0.3:
        action = "warn"
    else:
        action = "allow"

    return PromptInjectionResult(
        detected=score >= block_threshold,
        score=round(score, 3),
        matched_patterns=matched,
        action=action,
    )


# ---------------------------------------------------------------------------
# Sensitive Topic Guardrail
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS: dict[SensitiveTopic, list[str]] = {
    SensitiveTopic.MENTAL_HEALTH: [
        "depression", "anxiety", "suicidal", "mental health", "bipolar",
        "schizophrenia", "psychiatric", "therapist", "counseling", "ptsd",
        "panic attack", "self-worth", "hopeless", "worthless",
    ],
    SensitiveTopic.SUBSTANCE_ABUSE: [
        "drug addiction", "alcohol abuse", "overdose", "narcotics",
        "opioid", "heroin", "cocaine", "meth", "substance abuse",
        "withdrawal", "rehab", "intoxicated",
    ],
    SensitiveTopic.SELF_HARM: [
        "self-harm", "self harm", "cut myself", "hurting myself",
        "want to die", "end my life", "kill myself", "suicide",
        "suicidal ideation", "don't want to live", "do not want to live",
        "no reason to live", "not worth living",
    ],
    SensitiveTopic.VIOLENCE: [
        "hurt someone", "kill someone", "weapon", "bomb", "attack",
        "threaten", "assault", "murder", "violence",
    ],
    SensitiveTopic.LEGAL_MEDICAL_ADVICE: [
        "diagnose me", "my diagnosis", "am i sick", "what disease do i have",
        "should i take", "prescribe", "legal advice", "is this legal",
        "sue", "lawsuit", "legal case",
    ],
}

_TOPIC_ACTIONS: dict[SensitiveTopic, tuple[str, str]] = {
    SensitiveTopic.MENTAL_HEALTH: (
        "warn_user",
        "This topic involves mental health. Providing general information only; please consult a licensed professional.",
    ),
    SensitiveTopic.SUBSTANCE_ABUSE: (
        "warn_user",
        "This topic involves substance use. For support, contact SAMHSA helpline: 1-800-662-4357.",
    ),
    SensitiveTopic.SELF_HARM: (
        "escalate",
        "Your message mentions self-harm or suicide. Please contact the 988 Suicide & Crisis Lifeline immediately.",
    ),
    SensitiveTopic.VIOLENCE: (
        "refuse",
        "Requests involving harm to others cannot be processed. If in immediate danger, call emergency services.",
    ),
    SensitiveTopic.LEGAL_MEDICAL_ADVICE: (
        "warn_user",
        "This system provides general health information only, not medical/legal advice. Please consult a qualified professional.",
    ),
}


def classify_sensitive_topic(text: str) -> SensitiveTopicResult:
    """
    Classify whether *text* touches a sensitive topic.

    Detection approach: case-insensitive keyword matching.
    Action priority: SELF_HARM > VIOLENCE > SUBSTANCE_ABUSE > MENTAL_HEALTH > LEGAL.

    Limitations
    -----------
    - Misses paraphrased, coded, or non-English expressions.
    - Cannot detect context (e.g. academic discussion vs personal crisis).
    """
    text_lower = text.lower()
    found_topics: list[SensitiveTopic] = []

    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found_topics.append(topic)

    if not found_topics:
        return SensitiveTopicResult(
            detected=False,
            topics=[SensitiveTopic.NONE],
            action="allow",
            message="",
        )

    # Priority ordering
    priority_order = [
        SensitiveTopic.SELF_HARM,
        SensitiveTopic.VIOLENCE,
        SensitiveTopic.SUBSTANCE_ABUSE,
        SensitiveTopic.MENTAL_HEALTH,
        SensitiveTopic.LEGAL_MEDICAL_ADVICE,
    ]
    primary = next((t for t in priority_order if t in found_topics), found_topics[0])
    action, message = _TOPIC_ACTIONS[primary]

    return SensitiveTopicResult(
        detected=True,
        topics=found_topics,
        action=action,
        message=message,
    )


# ---------------------------------------------------------------------------
# Composite Input Guardrail Runner
# ---------------------------------------------------------------------------

@dataclass
class InputGuardrailsResult:
    """Combined result from all three input guardrails."""
    pii: PIIDetectionResult
    injection: PromptInjectionResult
    topic: SensitiveTopicResult
    safe_to_proceed: bool
    final_action: str
    processed_text: str           # text safe to send downstream


class InputGuardrails:
    """
    Runs PII detection, prompt-injection detection, and sensitive-topic
    classification on user input.

    Parameters
    ----------
    pii_action : str
        What to do when PII is detected ("redact" | "block").
    injection_threshold : float
        Risk score above which the request is blocked (0–1).
    """

    def __init__(self, pii_action: str = "redact", injection_threshold: float = 0.7):
        self.pii_action = pii_action
        self.injection_threshold = injection_threshold

    def run(self, text: str) -> InputGuardrailsResult:
        """Apply all input guardrails and return a composite result."""
        pii_result = detect_pii(text, action_on_detect=self.pii_action)
        injection_result = detect_prompt_injection(text, block_threshold=self.injection_threshold)
        topic_result = classify_sensitive_topic(text)

        # Determine the final action
        blocking_actions = {"block", "refuse", "escalate"}
        final_action = "allow"

        if injection_result.action == "block":
            final_action = "block"
        elif topic_result.action in blocking_actions:
            final_action = topic_result.action
        elif pii_result.action == "block":
            final_action = "block"
        elif injection_result.action == "warn" or topic_result.action == "warn_user":
            final_action = "warn"
        elif pii_result.action == "redact":
            final_action = "redact"

        safe_to_proceed = final_action not in blocking_actions

        # The text sent downstream has PII redacted (regardless of other actions)
        processed_text = pii_result.redacted_text

        return InputGuardrailsResult(
            pii=pii_result,
            injection=injection_result,
            topic=topic_result,
            safe_to_proceed=safe_to_proceed,
            final_action=final_action,
            processed_text=processed_text,
        )
