# SZL Humanitarian Causal Twin — experimental offline proof of concept

**Status: LOCAL / SYNTHETIC / NOT DEPLOYED / NOT SAFETY-CERTIFIED.**

This is an original, independent, small Python reference implementation of a possible
**evidence-bound physical-infrastructure observation layer**. Its first synthetic
use case is a municipal water tank, pump and treatment path. It does **not** copy,
execute or install the referenced third-party P&ID-to-graph skill, consume real
P&IDs, control equipment, train a model, operate as an MCP server, or contact a
provider. It does not use private SZL data.

The differentiator to test is whether **three separate, source-bound evidence
routes**—drawing topology, unit-safe conservation residuals and a spectral
screen—can reduce unjustified claims. The system must admit `UNAVAILABLE` instead
of pretending a graph or one sensor proves physical causation. One potential
humanitarian application is helping small water utilities prioritize *human*
inspections without replacing engineering safety systems.

## Run it with Python 3.11+

No third-party dependencies; all calls are offline.

```sh
cd szl-humanitarian-causal-twin-poc
python -m unittest discover -s tests -v
python -m szl_causal_twin.cli examples/healthy-synthetic-water.json --out examples/receipts/healthy.json
python -m szl_causal_twin.cli examples/imbalance-synthetic-water.json --out examples/receipts/imbalance.json
python -m szl_causal_twin.cli examples/coverage-loss-synthetic-water.json --out examples/receipts/coverage-loss.json
```

Each `--out` must be a new name: append-only create with a temporary file and an
atomic same-filesystem hard-link create. The CLI re-reads and checks the resulting
receipt. Re-running the same destination refuses to overwrite it.

## Optional loopback-only synthetic HTTP evaluator

This process is deliberately **not a field-ready service**. It admits only synthetic inputs and never enables controls or third-party endpoints. No API token is required because it binds to `127.0.0.1` and only accepts loopback Host headers; do not proxy or expose it beyond the local machine.

```sh
python -B -m szl_causal_twin.api --port 18109
# open http://127.0.0.1:18109/ for the local synthetic evidence console
# in a second terminal
curl -s http://127.0.0.1:18109/healthz
# /readyz intentionally returns HTTP 503 (field deployment HOLD)
# POST /api/causal-twin/v1/evaluate with Content-Type: application/json and a synthetic fixture
```

The API is stateless, bounded to 128 KiB, rejects nonfinite or duplicate-key JSON, and has no mutation endpoints. [`docs/RELEASE_GATES.md`](docs/RELEASE_GATES.md) records the integration and qualification holds. Its synthetic-only liveness is separate from real-facility readiness.

## Evidence contract

Input has explicit `synthetic: true`, a synthetic fixture revision, explicit rights,
traceable flow/signal edges, UTC timestamps, **L/s** flow rates, **liters** stored,
**kPa** pressure and seconds sampling. These are the only units admitted.
Outputs contain SHA-256 hashes for the canonical input, topology and source, and
an unsigned receipt digest. Hashes are **not signatures**, independent witnessing
or validation of input truth. Tests use exact synthetic values rather than
claimed real-world performance.

**Three checks**

1. **Topology:** a path from source to water distribution is supported by an
   explicitly attributed graph. No drawing interpretation is attempted.
2. **Mass conservation:** `sum(inflow L/s) - sum(outflow L/s) - delta_storage_liters / seconds`.
   A threshold exceedance is a *screening discrepancy*, not a diagnosis of a leak.
3. **Pressure Fourier screening:** a radix-2 FFT detects the strongest sampled
   non-DC oscillation (amplitude divided by mean pressure) against a declared
   demonstration threshold. Without anti-aliasing and calibration, this cannot
   distinguish mechanical faults, measurement artifacts or under-sampled signals.

**Decision states:** `HUMAN_REVIEW`, `INSUFFICIENT_EVIDENCE`, or
`NO_EXCEPTION_DETECTED_IN_SYNTHETIC_FIXTURE`. There is no `SAFE` or `QUALIFIED`
state and **automated actuation is always DENIED**. Missing input is not zero.

## How it could join SZL later (proposal, not implemented)

| Contract | Intended canonical owner | Promotion gate |
| --- | --- | --- |
| P&ID→graph intake | approved independent parser, separately reviewed | real drawing consent/rights, per-element bounding boxes, DEXPI/ISA mapping, dual human review |
| Claimed graph and evidence handles | `szl-second-brain` | versioned admitted nodes/edges and source lineage, no private leakage |
| Physics or PINN/FNO evaluator | `szl-kernels`, `szl-experiments` under reviewed scope | held-out numerical benchmark, calibrated units and uncertainty, baseline comparison |
| Read-only incident cases | `szl-defensive-control-plane` | tenant authorization; case/evidence parity; zero actuators |
| Governed retrieval tools | `hatun-mcp` | existing tool owner, authentication and Yuyay gate, bounded inputs, no duplicate MCP service |
| Visual evidence overlay | `anatomy` | source-linked scene, `UNAVAILABLE` and stale evidence visible; no control authority |
| Provenance and telemetry | `szl-invariants`, `szl-energy-attest` | verified source bindings, honest UNAVAILABLE for energy; DSSE only with real signer |

**Hard requirements before field pilot:** independent engineering review,
validated drawing provenance and revisions, verified safety boundary,
measurement calibration, uncertainty quantification, timestamp synchronization,
permission to ingest facility data, privacy/security threat model, tested threat
scenarios, and a human-governed incident response. This code is not suitable
for process control, medical advice, emergency response or production use.

See `docs/RESEARCH_AND_TRUST_BOUNDARIES.md` for the research questions,
novelty hypotheses, falsification tests and external primary references.

License of **this new source**: MIT (see `LICENSE`). No incorporation of external
code. Do not interpret the illustrative links as endorsement or evaluated parity.
