# P4 mock-only evidence

STATUS: partial - mock-only slice verified; live SGLang smoke is blocked.
CONTRACT: `reports/contracts/P4-inference.md` v1
COMMIT: `a88e484489bbae989c59d28a4ac31baa079188ff` (no commit made by this slice)
CAPTURED: 2026-10-24T21:57:25+05:30
HOST: Windows, Python 3.11.9, Pydantic 2.14.1, pytest 8.4.2, ruff 0.16.0
GPU/LIVE SGLANG: not available / not attempted

## Acceptance

```powershell
uv run pytest tests/unit tests/security -q -k "prompt or inference or orchestration"
```

Result: exit 0; `37 passed, 153 deselected`.
Log: `logs/acceptance-pytest.log`

```powershell
uv run ruff check src/hallx/prompting src/hallx/inference src/hallx/orchestration tests/unit/test_prompt*.py tests/unit/test_inference*.py tests/unit/test_orchestration*.py
```

Result: exit 0; `All checks passed!`.
Log: `logs/acceptance-ruff.log`

Advisory full current suite:

```powershell
uv run pytest -q
```

Result: exit 0; `190 passed in 28.71s`.
Log: `logs/full-pytest.log`

The exact collected acceptance test IDs are in `logs/test-ids.log`.

## Invariant evidence

| Invariant | Test |
|---|---|
| Non-loopback URLs rejected before socket construction | `tests/unit/test_inference.py::test_inference_rejects_non_loopback` |
| Transport/timeout/model/HTTP/schema failures are typed; no fallback | `test_inference_failures_are_typed`, `test_inference_timeout_is_typed`, `test_inference_transport_failure_is_typed` |
| Health is diagnostic and unhealthy does not generate | `test_inference_health_is_diagnostic_and_model_aware`, `test_inference_health_unhealthy_does_not_generate` |
| Prompt is byte-stable and ordered by `chunk_id` | `tests/unit/test_prompt.py::test_prompt_prefix_stable` |
| Exact untrusted delimiters and escaped attributes | `test_prompt_uses_exact_untrusted_delimiters`, `test_prompt_escapes_delimiter_material_in_attributes` |
| Injection remains data; no tools/offsets | `tests/security/test_prompt_injection.py::test_prompt_injection_is_untrusted_data`, `test_prompt_has_no_tools_or_model_offsets` |
| Stale candidates are excluded from the prompt | `test_prompt_excludes_stale_candidates` |
| Exactly one repair | `tests/unit/test_orchestration.py::test_orchestration_repairs_at_most_once` |
| ACL, identity, freshness, stale failures are not repaired | `test_orchestration_security_failures_not_repaired` |
| Blocking bundle rejection makes zero generation calls | `test_orchestration_security_failures_not_repaired` (ACL case) |
| Second invalid candidate abstains | `test_orchestration_second_invalid_abstains` |
| Rejected output never exposes an envelope | `test_orchestration_rejected_has_no_envelope` |
| Malformed output is rejected without repair | `test_orchestration_rejects_malformed_json_without_repair` |
| Repair cap and disabled repair | `test_orchestration_caps_max_repairs` |
| Generator failure propagates without fallback | `test_orchestration_generator_failure_propagates_without_fallback` |
| Server state overrides model state; evidence text is not logged at INFO | `test_orchestration_accepts_server_state_not_model_state`, `test_inference_success_sends_one_schema_constrained_request` |

## Blocked / not proven

- Live SGLang generation and real runtime timings: blocked by no GPU/live server. No alternate engine was used.
- Browser/UI: out of scope for this slice.
- Health route is not named by the contract; implementation uses `GET /v1/models`.
- Adapter ID source is not named by the contract; implementation accepts top-level `adapter_id` or `metadata.adapter_id` only.
