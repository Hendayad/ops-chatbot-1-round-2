# Week 3 guide: grounded Q&A and in-chat profile collection

This guide explains the two deliverables requested in the Week 3 review: a retrieval-grounded answer pipeline and a safe profile collector. Use it both to implement the work again later and to explain the design during review.

## 1. What changed and why

| Deliverable | Files | Outcome |
| --- | --- | --- |
| Grounded Q&A | `app/qa/graph.py`, `app/qa/prompts.py`, `app/qa/stream.py` | Answers come from approved, cohort-scoped material with validated citations; unsupported questions receive an honest refusal. |
| Profile collector | `app/profile/schema.py`, `app/profile/collector.py` | The assistant asks for one missing field at a time, validates each reply, and writes only valid profile data. |
| Evaluation and tests | `evals/qa_suite.py`, `tests/test_grounding.py`, `tests/test_qa_week3.py`, `tests/test_profile.py` | Regressions such as uncited answers, unsafe streaming, or invalid personal data are detected automatically. |

## 2. Grounded Q&A, step by step

1. A caller gives `answer_question(question, cohort)` a learner question and the learner's cohort.
2. `app/qa/graph.py` delegates to the existing retrieval and citation-validation implementation. Reusing it is intentional: two independent grounding implementations would drift and make safety harder to audit.
3. Retrieval searches only approved material for that cohort.
4. The prompt contract in `app/qa/prompts.py` tells the model to use only supplied evidence, return structured output, and cite every material claim.
5. The application checks that every cited alias exists in the retrieved evidence. Missing, invented, or cross-cohort citations cause a refusal.
6. `app/qa/stream.py` waits until that validation is complete and then emits the safe answer. It does not stream raw model tokens, because a bad claim could otherwise reach the learner before validation.

### Why not let the model answer first and check later?

That design is unsafe: the learner may already have read an unsupported statement. The chosen design fails closed. When evidence is insufficient, the result says so and sets `needs_escalation` instead of guessing.

## 3. Profile collector, step by step

1. Load the learner's current `LearnerProfile`.
2. Find the first missing field in the fixed order: preferred name, timezone, then cohort.
3. Ask exactly one short question. One question avoids a long form inside chat and makes recovery easy.
4. Treat the next learner reply as the answer only to that field.
5. Validate with Pydantic. Text is normalised; timezone must be an IANA value, for example `Africa/Cairo`.
6. Persist only after validation succeeds. If validation fails, keep the prior profile unchanged and repeat the same prompt with a clear correction hint.
7. When no fields are missing, return `completed=True` and let the normal chat flow continue.

### Why deterministic parsing instead of asking an LLM to extract profile data?

An LLM can infer values incorrectly or extract extra personal information. The collector deliberately accepts one explicit answer for one known field, validates it, and stores the smallest useful profile.

## 4. How to test the work

Run the focused suite:

```powershell
$env:APP_ENV='test'; $env:OPENAI_API_KEY='test-key'
python -m pytest tests/test_grounding.py tests/test_qa_week3.py tests/test_profile.py -q
```

The tests prove the main promises: citations are present for grounded answers, streaming occurs only after validation, invalid timezones do not persist, and valid replies complete the profile.

## 5. Questions a reviewer may ask

- **How do we prevent hallucinations?** Retrieval is cohort-scoped, the prompt restricts the model to approved evidence, and code validates citations before returning content.
- **Why are there wrappers in `app/qa`?** The review expects a stable Week 3 capability boundary. Wrappers expose that boundary while reusing the already-tested underlying safety logic.
- **What happens for unknown questions?** The learner receives the standard honest refusal; the result signals escalation rather than fabricating an answer.
- **How is personal data protected?** Only three operational fields are collected, validation happens before persistence, and a bad answer is never saved.
