# Research brief — a bounded, falsifiable humanitarian causal twin

Prepared 2026-11-16 (research/prototype, not a model or infrastructure deployment).

## Observed source ideas and engineering gaps

1. The screenshot's security list groups unrelated functions (SAST, SCA, secrets,
   application penetration testing, malware scanning, agent-skill risk and AI red
   teaming). These are not interchangeable. BLA is artifact obfuscation rather
   than a vulnerability detector. For SZL, require owner-scoped security lanes
   with reproducible regression tests and coverage receipts. Scan untrusted skills
   BEFORE installation; do not run them or transmit sensitive code to a remote
   analyzer without permission. A scan cannot prove an artifact safe.
2. Ciroos illustrates cross-domain incident reconstruction with telemetry,
   repository/config changes and a topology graph. Claimed vendor results are
   not independent benchmark evidence. An incident graph should preserve event
   time, change provenance and cause/association uncertainty; refuse automatic
   remediations absent signed operator authorization.
3. Physics-informed neural networks constrain a learned function with PDE
   residuals, but these soft constraints can fail under loss imbalance, stiffness,
   multiscale dynamics and invalid boundary data. A low training loss is NOT a
   correctness or safety certificate. Start from deterministic conservation
   checks before attempting PhysicsNeMo/PINNs/FNOs. Compare to classical
   numerical solvers and held-out measurements, not only a neural baseline.
4. FFT is a fast transform, not a recovery of frequencies lost to sampling.
   The pilot performs a discrete, finite-window spectral screening with
   explicitly stated Nyquist and no claims about missing high-frequency detail.
5. MCP sits above existing API contracts as a tool discovery/invocation layer.
   `hatun-mcp` is SZL's existing canonical governed gateway. Do not add a new
   unauthenticated or bypassing MCP gateway to integrate these capabilities.
6. Scott Duncan's PID-to-Knowledge-Graph demonstrates LLM-assisted P&ID
   extraction into graph.json/DuckDB with element source references. The source
   also describes QA flags for doubtful tags. It does not turn a drawing into
   a validated live sensor twin or a licensed operator of real equipment.

## Falsifiable novelty hypothesis (not a priority claim)

**H1:** At fixed false-negative rate on a blinded set of synthetic and
engineering-reviewed municipal-water faults, fusing (i) document-attested
connectivity, (ii) calibrated mass/energy residuals and (iii) temporal/spectral
anomalies *with explicit abstention* yields a lower false-positive incident rate
than any individual detector. Require the primary comparison to be adjudicated
blindly by independent engineering reviewers. Pre-register thresholds and
include induced evidence corruption and absent/mismatched revision tests.

**H2:** Source-linked graph-path explanations improve a water operator's ability
 to reject a spurious cause, compared with model-generated prose, without
 increasing time-to-resolution or unsafe action. Randomize operators/cases and
 measure justified decisions and harmful omissions; avoid claims without a trial.

**H3:** A receipt-closed tool workflow can preserve source/operation identity
 across a 2-hour SRE incident without claiming that internal hashes are
 signatures. Require independently checked readback of input and output bytes,
 distinct signer verification when available and interruption/replay tests.

## High-impact, bounded first deployments

A. **Small water utilities** — detect inconsistent flow, pump cavitation
 indications or data gaps and offer a verified inspection path, not automated
 valve actions. Metrics: calibrated sensitivity/specificity, operator workload,
 lead time to confirmed leak, false-alarm burden, protected customer privacy.

B. **Research laboratories** — turn annotated instrument diagrams and
 temperature/flow records into read-only reproducible equipment status and
 measurement lineage. Do not infer biological findings from instrument QC.

C. **Disaster resilience / microgrids** — integrate outage topology and
 conservative energy checks only with operator agreements and simulation
 calibration. Never send actuation commands to grids or evacuation systems.

## Proposed interfaces — not implemented

- `POST /api/causal-twin/v1/evaluate` (internal; read-only; controller-owned),
  with input schema and source-rights admission, returns bounded findings and
  source revision/digest. No public endpoint until authorization and threat review.
- `szl_causal_twin_inspect` via existing canonical Hatun tool catalog after
  source registration and signed contract checks, no arbitrary file path arguments.
- Second Brain link projection: only public/permissioned handles, not raw plant
  records; every graph edge has a reviewer-addressable source-id.
- Living Anatomy: node color `MEASURED`, `DERIVED`, `UNAVAILABLE`, `CONFLICTED`
  must not be collapsed into a single green badge.

## Failure injections before meaningful pilot

- Wrong diagram revision, ambiguous instrument tag, reversed flow direction.
- Unknown unit, calibration drift, sensor clock skew, unseen bypass line.
- Aliased periodic signal, high noise, partial sensor outage, stale samples.
- Contradictory graph + telemetry, malicious annotation inside source PDF,
  unauthorized tool call, case approval spoofing.
- Duplicate receipts, forged parent hash, signed but untrusted key,
  source changed after evaluation, time-travel and replayed evidence.

The test harness should demand refusal/`INSUFFICIENT_EVIDENCE` rather than
patching holes with generated evidence or automatic action.

## Primary resources reviewed

- P&ID source: https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph
- NVIDIA PhysicsNeMo PINNs: https://docs.nvidia.com/physicsnemo/26.05/user-guide/pinns-tutorials/index.html
- NVIDIA PhysicsNeMo architectures: https://docs.nvidia.com/physicsnemo/26.05/user-guide/model_architectures.html
- PINN failure modes: https://papers.nips.cc/paper_files/paper/2021/hash/df438e5206f31600e6ae4af72f2725f1-Abstract.html
- NVIDIA verified skills: https://developer.nvidia.com/blog/nvidia-verified-agent-skills-provide-capability-governance-for-ai-agents/
- NVIDIA SkillSpector: https://github.com/NVIDIA/skillspector
- NVIDIA AI Enterprise: https://www.nvidia.com/en-us/data-center/products/ai-enterprise/
- SZL Second Brain: https://github.com/szl-holdings/szl-second-brain
- SZL Defensive Control Plane: https://github.com/szl-holdings/szl-defensive-control-plane
- SZL Hatun: https://github.com/szl-holdings/hatun-mcp

## Truth boundary

This pilot's conservation residual and spectrum are **deterministic calculations
on invented input**. No training step, real facility, external provider,
independent backup, hosted deployment, third-party evaluation, peer review,
formal physical theorem, or production qualification was performed. The hashes
prove only self-consistency of the report bytes under this implementation.
