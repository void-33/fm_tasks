# Trustworthy AI Guardrail System — Evaluation Report

## a. Design and Architecture

### Application Domain
The system implements guardrails for a **Healthcare Q&A Chatbot** that provides educational health information. This domain was chosen because it naturally exposes all required guardrail scenarios: users share PII when describing their conditions; adversarial users attempt to extract medical "diagnoses" via jailbreaks; responses must be grounded in verified health information.

### Component Interaction
```
User Input ──► [PII Detection] ──► [Prompt Injection] ──► [Sensitive Topic]
                                                                │
                                        ┌─────── BLOCK/REFUSE/ESCALATE
                                        │
                              [LLM / Mock Knowledge Base]
                                        │
              [Schema Validation] ◄─────┘
                      │
              [Output PII Detection]
                      │
              [Groundedness Validation]
                      │
              Final response ──► User
```

**Why guardrails are applied at these stages:**
- **Input guardrails first** — prevents malicious or privacy-violating data from ever reaching the LLM or being logged.
- **Output guardrails after LLM** — the LLM is probabilistic; its output cannot be trusted unconditionally even with safe inputs.
- **Schema before groundedness** — pointless to check groundedness if the response is structurally invalid.
- **PII output check before groundedness** — an SSN in the output warrants immediate blocking, regardless of factual correctness.

---

## b. Implementation Choices

### PII Detection
**Technique:** Hand-crafted regular expressions per PII type (EMAIL, PHONE, SSN, CREDIT_CARD, DATE_OF_BIRTH, NID).

**Why chosen:** Zero external dependencies; deterministic; fast; interpretable. Suitable when the set of PII types is known and bounded.

**Limitations:**
- International phone formats may be missed or misclassified.
- Medical record numbers, biometric IDs, and names are not covered.
- The SSN regex can match numeric product codes (false positives).
- No context awareness — a fictional SSN in a story is treated the same as a real one.

---

### Prompt Injection Detection
**Technique:** Weighted rule-based pattern matching. Eight compiled regex rules each carry a risk weight. Rules fire independently; scores accumulate (capped at 1.0). Threshold determines block vs. warn vs. allow.

**Why chosen:** Fast, transparent, no ML infrastructure required. Covers known attack categories (DAN, system-tag smuggling, persona bypass, direct instruction override).

**Limitations:**
- Cannot catch obfuscated injections (Base64, pig-latin, Unicode homoglyphs, multi-step persuasion).
- Indirect phrasing variations not covered by current patterns escape detection (TC-22 failure).
- Static rules require manual updates as new attack vectors emerge.

---

### Sensitive Topic Classification
**Technique:** Keyword dictionary per topic category (5 categories). Priority ordering resolves conflicts when multiple topics are detected.

**Why chosen:** Interpretable, fast, auditable. The keyword lists are domain-specific and can be reviewed and updated by domain experts without ML expertise.

**Limitations:**
- Entirely lexical; misses context (academic discussion vs. personal crisis).
- Non-English, coded, or euphemistic language is not detected.
- No confidence score — detection is binary per keyword match.

---

### Schema Validation
**Technique:** Pydantic v2 `BaseModel` with field-level validators. Checks field presence, types, string lengths, and enumerated allowed values (`category`, `confidence`).

**Why chosen:** Pydantic is the industry standard for Python data validation. It provides rich, structured error messages that distinguish fixable (regenerate) from critical (fallback) failures.

**Limitations:**
- Cannot validate semantic correctness of free-text fields.
- Checks format, not meaning — a structurally valid response can still be medically wrong.

---

### Groundedness Validation
**Technique:** Per-sentence Jaccard similarity between answer sentences and the reference context token set. Sentences below the threshold are flagged as ungrounded; the average score determines the overall action.

**Why chosen:** No external dependencies; works offline; proportional to query complexity. Serves as a lightweight hallucination filter.

**Limitations:**
- Purely lexical — synonyms, paraphrases, and technical abbreviations reduce the score incorrectly.
- Does not detect hallucinated numbers or statistics embedded in otherwise grounded sentences.
- Very short reference documents penalise all responses (low denominator).

---

### Output PII Detection
**Technique:** Same regex patterns applied to AI-generated text. Critical PII types (SSN, CREDIT_CARD) trigger block; others trigger redaction.

**Why chosen:** Symmetrical with input PII guardrail; consistent pattern library.

**Limitations:**
- Same limitations as input PII detection.
- Cannot detect PII that was reworded by the LLM (e.g. "three-two-one hyphen five-four hyphen nine-eight-seven-six").

---

## c. Evaluation Results

### Quantitative Metrics (24 test cases)

| Guardrail | TP | TN | FP | FN | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|---|---|
| PII Detection | 4 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Prompt Injection | 4 | 1 | 0 | 1 | 1.000 | 0.800 | 0.889 | 0.833 |
| Sensitive Topic | 4 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Schema Validation | 3 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Groundedness | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Output PII | 2 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **Overall** | **18** | **5** | **0** | **1** | **1.000** | **0.947** | **0.973** | **0.958** |

### Qualitative Observations

**What performed well:**
- PII detection correctly identified and redacted emails, phones, and SSNs with zero false positives or negatives in the test suite.
- Schema validation reliably caught malformed outputs (wrong category enum, missing fields, too-short answers).
- Sensitive topic classification correctly escalated self-harm and refused violence requests.
- DAN and system-tag jailbreak attempts were blocked at a 1.0 injection score.

**What failed:**
- Indirect prompt injection (TC-22) was missed — the guardrail relies on exact phrase matching.

**What the results do not establish:**
- Performance on non-English inputs.
- Behaviour under adversarial examples specifically crafted to evade each guardrail.
- Reliability at production scale or with a real LLM backend.
- Coverage of PII types beyond the six implemented patterns.

---

## d. Risk Assessment

### Remaining Risks

| Risk | Severity | Likelihood | Notes |
|---|---|---|---|
| Semantically obfuscated prompt injection | High | Medium | Cannot be caught by regex alone |
| Paraphrased / indirect self-harm expressions | High | Medium | Extended keywords partially address this |
| Hallucinated numbers in grounded text | High | Medium | Jaccard cannot detect embedded fabrications |
| International PII formats undetected | Medium | High | Current patterns are US/EN-centric |
| SSN false positives on numeric strings | Medium | Medium | Documented; threshold tunable |
| LLM-reworded PII in output | High | Low | Requires semantic PII detection |

### Deployment Recommendation

> **Suitable only with restrictions.**

The current implementation is appropriate for:
- Educational demonstrations.
- A development/staging environment as a starting guardrail layer.
- A first pass in a multi-layer safety stack.

**Not yet ready for production healthcare deployment** without:
1. Semantic (embedding-based or NLI) groundedness and injection detection.
2. A proper PII service (e.g. Microsoft Presidio) covering international formats and additional entity types.
3. Red-team testing by security and medical domain experts.
4. Regulatory compliance review (HIPAA, GDPR, applicable medical device regulations).
5. Audit logging, rate limiting, and abuse monitoring.
