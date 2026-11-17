# SZL Humanitarian Causal Twin: staged release gates

This proof of concept is a **synthetic-only, read-only research reference**. Its local HTTP interface is not public ingress. It cannot accept real facility records, access infrastructure, run training, send messages, control equipment, or create signed attestations.

| Gate | State | Required evidence to promote |
| --- | --- | --- |
| Source identity | LOCAL implementation | Reviewed GitHub source commit and code-owner decision |
| Deterministic synthetic CLI | TESTED (replay per release) | Matrix test pass, source-bound fixtures, independently checked output hashes |
| Local synthetic HTTP API + browser console | TESTED (replay per release) | Loopback-only binding, CSP, frontend readback, HTTP refusal tests, traceable read-only output |
| Attested source/graph ingestion | HOLD | Drawing rights, revision provenance, node/edge source coordinates, independent dual QA |
| Authorized real facility data | HARD DENY | Partner agreement, privacy threat model, cyber review, engineering safety sign-off |
| Live telemetry | NOT CONNECTED | Units, calibration, freshness, clock alignment, sensor fault bounds, signed access authorization |
| Human-quality evaluation | NOT MEASURED | Pre-registered blinded faults, false-negative/false-positive denominators, baselines, reviewer adjudication |
| Scientific physical qualification | NOT QUALIFIED | Independent engineering validation, OOD tests, safety case and monitoring |
| Hatun MCP bridge | NOT CONNECTED | Canonical owner review, authenticated bounded tool, no competing MCP service, no actuation |
| Second Brain graph projection | NOT ADMITTED | Rights-filtered source handles, immutable revision bindings, no private graph leakage |
| Living Anatomy display | NOT CONNECTED | Read-only visual feed, measured/derived/unavailable clearly distinguished |
| Public HF model/Space or product | HOLD | Publishing approval, render/readback, truthful cards, independently verified release evidence |

## Contracts (planned, not active)

* The core read-only evaluation is owned by this research package; future integration occurs as a **versioned, reviewed import/adapter** under the actual canonical service owner.
* Existing Hatun MCP remains the only gateway, and its policy/receipt semantics cannot be bypassed by calling this API directly over a public network.
* The Second Brain may admit **reviewed graph handles**, not raw plant drawings or sensitive source documents.
* Living Anatomy is an evidence visualization only; rendering does not confer authority to command devices.
* Source hash ≠ signer identity. A source merge ≠ installed runtime. A local passing test ≠ field qualification.

No production upgrade, secret rotation, database write, model training, paid compute, physical control, or public ingress is authorized by this stage.
