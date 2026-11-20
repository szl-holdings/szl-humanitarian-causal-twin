"""Offline proof-of-concept. No device control, network calls or ML execution."""
from __future__ import annotations

import cmath
import hashlib
import json
import math
from collections import deque
from datetime import datetime, timezone

SCHEMA_VERSION = "szl.synthetic-causal-twin.v0.1"
LIMIT_NODES = 100
LIMIT_EDGES = 250
LIMIT_PRESSURE_SAMPLES = 64
# Numerical roundoff sentinel only; NOT a calibrated pressure noise floor.
NYQUIST_NUMERIC_EPSILON = 1e-9


class InvalidEvidence(ValueError):
    """Input failed deterministic evidence schema/contract validation."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(v: object, label: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InvalidEvidence(f"{label} must be a finite number")
    return float(v)


def _time(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise InvalidEvidence("observed_utc must be an explicit UTC Z timestamp")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.utcoffset().total_seconds() != 0:
            raise ValueError("non-UTC")
    except (ValueError, AttributeError) as e:
        raise InvalidEvidence("invalid observed_utc") from e
    return value


def _sample_age(sampled_utc: object, observed_utc: str, max_age_seconds: float) -> float | None:
    if sampled_utc is None:
        return None
    sample = _time(sampled_utc)
    observed = datetime.fromisoformat(observed_utc.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(sample.replace("Z", "+00:00"))
    age = (observed-parsed).total_seconds()
    if age < -2 or age > max_age_seconds:
        return None
    return round(age, 6)


def _fft(samples: list[float]) -> list[complex]:
    """Iterative radix-2 DFT (only power-of-two lengths). Not a signal reconstruction."""
    n = len(samples)
    if n < 8 or n > LIMIT_PRESSURE_SAMPLES or (n & (n-1)):
        raise InvalidEvidence("pressure samples must have 8, 16, 32 or 64 points")
    data = [complex(x) for x in samples]
    j = 0
    for i in range(1, n):
        b = n >> 1
        while j & b:
            j ^= b
            b >>= 1
        j ^= b
        if i < j:
            data[i], data[j] = data[j], data[i]
    step = 2
    while step <= n:
        w_step = cmath.exp(-2j * math.pi / step)
        for i in range(0, n, step):
            w = 1.0+0.0j
            for k in range(step//2):
                a = data[i+k]
                b = w * data[i+k+step//2]
                data[i+k], data[i+k+step//2] = a+b, a-b
                w *= w_step
        step *= 2
    return data


def _validate_graph(graph: object) -> tuple[dict, list, list]:
    if not isinstance(graph, dict):
        raise InvalidEvidence("graph must be an object")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise InvalidEvidence("nodes and edges must be arrays")
    if not (1 <= len(nodes) <= LIMIT_NODES) or len(edges) > LIMIT_EDGES:
        raise InvalidEvidence("graph size exceeds bounded limits")
    node_ids = []
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n.get("evidence_ref"):
            raise InvalidEvidence("every node needs id and source evidence")
        node_ids.append(n["id"])
    if len(node_ids) != len(set(node_ids)):
        raise InvalidEvidence("duplicate node id")
    ids = set(node_ids)
    edge_ids = []
    for e in edges:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            raise InvalidEvidence("invalid edge id")
        if e.get("from") not in ids or e.get("to") not in ids or e.get("kind") not in ("flow", "signal"):
            raise InvalidEvidence("invalid graph edge endpoint/type")
        if not isinstance(e.get("evidence_ref"), str) or not e["evidence_ref"]:
            raise InvalidEvidence("missing edge evidence")
        edge_ids.append(e["id"])
    if len(edge_ids) != len(set(edge_ids)):
        raise InvalidEvidence("duplicate edge id")
    return {n["id"]: n for n in nodes}, edges, edge_ids


def _path(edges: list[dict], start: str, finish: str) -> list[str]:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        if e["kind"] == "flow":
            adjacency.setdefault(e["from"], []).append((e["to"], e["id"]))
    q = deque([(start, [])])
    seen = {start}
    while q:
        at, route = q.popleft()
        if at == finish:
            return route
        for nxt, edge_id in sorted(adjacency.get(at, [])):
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, route+[edge_id]))
    return []


def _mass_balance(nodes: dict, edges: list[dict], observations: dict, rule: dict) -> dict:
    tank = rule.get("tank_id")
    if tank not in nodes or nodes[tank].get("kind") != "tank":
        raise InvalidEvidence("tank_id must refer to a tank node")
    incoming = sorted(e["id"] for e in edges if e["kind"] == "flow" and e["to"] == tank)
    outgoing = sorted(e["id"] for e in edges if e["kind"] == "flow" and e["from"] == tank)
    if not incoming or not outgoing:
        return {"state":"UNAVAILABLE","reason":"topology_missing_flow_side","evidence_edges":incoming+outgoing}
    flows = observations.get("flows_lps")
    sources = observations.get("flow_evidence_refs", {})
    storage_source = observations.get("storage_evidence_ref")
    if not isinstance(flows, dict):
        return {"state":"UNAVAILABLE","reason":"flow_observations_missing"}
    needed = incoming + outgoing
    if not isinstance(sources,dict) or not storage_source or any(not isinstance(sources.get(k),str) or not sources.get(k) for k in needed):
        return {"state":"UNAVAILABLE","reason":"measurement_lineage_missing","required_edges":needed}
    anchor = observations["observed_utc"]
    times = observations.get("flow_sampled_utc", {})
    max_age = _number(rule.get("max_sensor_age_seconds"),"max_sensor_age_seconds")
    if max_age <= 0:
        raise InvalidEvidence("max_sensor_age_seconds must be positive")
    if not isinstance(times,dict) or any(_sample_age(times.get(k),anchor,max_age) is None for k in needed) or _sample_age(observations.get("storage_sampled_utc"), anchor, max_age) is None:
        return {"state":"UNAVAILABLE","reason":"missing_or_stale_flow_storage_clock_evidence","required_edges":needed}
    if any(k not in flows or flows[k] is None for k in needed):
        return {"state":"UNAVAILABLE","reason":"required_flow_missing","missing_edges":[k for k in needed if k not in flows or flows[k] is None]}
    try:
        values = {k:_number(flows[k], f"flows_lps.{k}") for k in needed}
    except InvalidEvidence:
        raise
    if any(v < 0 for v in values.values()):
        raise InvalidEvidence("flow measurements must be nonnegative; direction is in graph")
    start = observations.get("tank_volume_liters_start")
    end = observations.get("tank_volume_liters_end")
    seconds = observations.get("interval_seconds")
    if None in (start, end, seconds):
        return {"state":"UNAVAILABLE","reason":"storage_evidence_missing"}
    start = _number(start, "tank_volume_liters_start")
    end = _number(end, "tank_volume_liters_end")
    seconds = _number(seconds, "interval_seconds")
    if seconds <= 0:
        raise InvalidEvidence("interval_seconds must be positive")
    tolerance = _number(rule.get("max_abs_residual_lps"),"max_abs_residual_lps")
    if tolerance <= 0:
        raise InvalidEvidence("mass-balance threshold must be positive")
    sum_in, sum_out = sum(values[k] for k in incoming), sum(values[k] for k in outgoing)
    storage_rate = (end-start)/seconds
    residual = sum_in - sum_out - storage_rate
    return {
        "state":"FLAG" if abs(residual) > tolerance else "PASS",
        "equation":"sum_in_lps - sum_out_lps - delta_storage_liters / interval_seconds",
        "in_lps":round(sum_in,8),"out_lps":round(sum_out,8),
        "delta_storage_liters":round(end-start,8),"interval_seconds":seconds,
        "residual_lps":round(residual,8),"absolute_threshold_lps":tolerance,
        "evidence_edges":needed,"measurement_evidence_refs":[sources[k] for k in needed]+[storage_source],
        "sample_age_seconds": {k:_sample_age(times[k],anchor,max_age) for k in needed},
        "interpretation":"screening only; an imbalance may indicate missing telemetry, meter error, or unmodeled flow—not necessarily a leak",
    }


def _spectrum(observations: dict, rule: dict, nodes: dict, edges: list[dict]) -> dict:
    pressure = observations.get("pressure_sensor")
    if not isinstance(pressure, dict):
        return {"state":"UNAVAILABLE","reason":"pressure_sensor_missing"}
    sensor_id = pressure.get("id")
    sensor_node = nodes.get(sensor_id)
    if not isinstance(sensor_node,dict) or sensor_node.get("kind") != "pressure_transmitter":
        return {"state":"UNAVAILABLE","reason":"pressure_sensor_not_in_graph"}
    observed_edge = sensor_node.get("observes_edge_id")
    if not observed_edge or observed_edge not in {e["id"] for e in edges if e["kind"] == "flow"}:
        return {"state":"UNAVAILABLE","reason":"pressure_sensor_location_unbound"}
    if not isinstance(pressure.get("evidence_ref"),str) or not pressure.get("evidence_ref"):
        return {"state":"UNAVAILABLE","reason":"pressure_sample_lineage_missing"}
    max_age = _number(rule.get("max_sensor_age_seconds"),"max_sensor_age_seconds")
    if _sample_age(pressure.get("sampled_utc"),observations["observed_utc"],max_age) is None:
        return {"state":"UNAVAILABLE","reason":"missing_or_stale_pressure_clock_evidence"}
    if pressure.get("unit") != "kPa":
        return {"state":"UNAVAILABLE","reason":"pressure_unit_unqualified"}
    if "samples" not in pressure or pressure["samples"] is None:
        return {"state":"UNAVAILABLE","reason":"pressure_samples_missing"}
    raw = pressure["samples"]
    if not isinstance(raw, list):
        raise InvalidEvidence("pressure samples must be an array")
    samples = [_number(x,"pressure_sample") for x in raw]
    dt = _number(pressure.get("sample_interval_seconds"),"sample_interval_seconds")
    threshold = _number(rule.get("max_relative_oscillation"),"max_relative_oscillation")
    if dt <= 0 or threshold <= 0:
        raise InvalidEvidence("spectral interval/threshold must be positive")
    n = len(samples)
    # Individually finite measurements can overflow the FFT or sample-rate
    # arithmetic. Withhold evidence before any nonfinite JSON serialization.
    try:
        spectrum = _fft(samples)
    except OverflowError:
        return {"state":"UNAVAILABLE","reason":"spectral_derived_nonfinite"}
    mean = sum(samples)/n
    if not math.isfinite(mean) or any(
        not math.isfinite(x.real) or not math.isfinite(x.imag) for x in spectrum
    ):
        return {"state":"UNAVAILABLE","reason":"spectral_derived_nonfinite"}
    nyquist = 0.5/dt
    duration = n*dt
    if (
        not math.isfinite(nyquist) or not math.isfinite(duration)
        or nyquist <= 0 or duration <= 0 or round(nyquist, 8) <= 0
    ):
        return {"state":"UNAVAILABLE","reason":"spectral_numeric_resolution_unavailable"}
    if abs(mean) < 1e-9:
        return {"state":"UNAVAILABLE","reason":"zero_mean_pressure"}
    # A complex component may be finite while its magnitude overflows.
    magnitudes = [abs(spectrum[i]) for i in range(1,n//2+1)]
    if any(not math.isfinite(a) for a in magnitudes):
        return {"state":"UNAVAILABLE","reason":"spectral_derived_nonfinite"}
    bin_id = max(range(1,n//2+1), key=lambda i: magnitudes[i-1])
    scale = 1 if bin_id == n//2 else 2
    amplitude = scale*magnitudes[bin_id-1]/n
    relative = amplitude / abs(mean)
    peak_frequency = bin_id/duration
    if any(not math.isfinite(v) for v in (amplitude, relative, peak_frequency)):
        return {"state":"UNAVAILABLE","reason":"spectral_derived_nonfinite"}
    if round(peak_frequency, 8) <= 0:
        return {"state":"UNAVAILABLE","reason":"spectral_numeric_resolution_unavailable"}
    # Above-Nyquist signals can produce exactly the same alternating samples.
    # A floating-point epsilon is NOT measured sensor noise or band-limiting.
    if bin_id == n//2 and relative > NYQUIST_NUMERIC_EPSILON:
        return {
            "state":"UNAVAILABLE","reason":"nyquist_edge_unresolved",
            "sensor_id":sensor_id,"observed_flow_edge_id":observed_edge,
            "sensor_evidence_ref":sensor_node["evidence_ref"],
            "measurement_evidence_ref":pressure["evidence_ref"],
            "n_samples":n,"nyquist_hz":round(nyquist,8),
            "relative_oscillation":round(relative,8),
            "interpretation":"Nyquist-boundary peak cannot establish anti-aliasing or safe frequency attribution",
        }
    return {
        "state":"FLAG" if relative > threshold else "PASS",
        "sensor_id":sensor_id,"observed_flow_edge_id":observed_edge,
        "sensor_evidence_ref":sensor_node["evidence_ref"],
        "measurement_evidence_ref":pressure["evidence_ref"],
        "sample_age_seconds":_sample_age(pressure["sampled_utc"],observations["observed_utc"],max_age),
        "n_samples":n,"sample_interval_seconds":dt,
        "nyquist_hz":round(nyquist,8),
        "peak_frequency_hz":round(peak_frequency,8),
        "peak_amplitude_kpa":round(amplitude,8),
        "mean_pressure_kpa":round(mean,8),
        "relative_oscillation":round(relative,8),
        "relative_threshold":threshold,
        "interpretation":"FFT screening only; spectral peaks do not prove cause or permit reconstruction of aliased signals"
    }


def evaluate(evidence: dict) -> dict:
    """Pure, deterministic, synthetic-only read-only assessment; no external effects."""
    if not isinstance(evidence, dict) or evidence.get("schema_version") != SCHEMA_VERSION:
        raise InvalidEvidence("unsupported schema_version")
    if evidence.get("synthetic") is not True:
        raise InvalidEvidence("real facility data is not admitted into this prototype")
    source = evidence.get("source")
    if not isinstance(source, dict) or source.get("kind") != "synthetic_fixture" or not source.get("revision") or source.get("rights") != "CC0-synthetic":
        raise InvalidEvidence("explicit synthetic source, revision and rights required")
    observation = evidence.get("observation")
    rules = evidence.get("rules")
    if not isinstance(observation, dict) or not isinstance(rules, dict):
        raise InvalidEvidence("observation and rules are required objects")
    _time(observation.get("observed_utc"))
    if observation.get("flow_unit") != "L/s":
        raise InvalidEvidence("only L/s flow units supported")
    nodes, edges, edge_ids = _validate_graph(evidence.get("graph"))
    source_id, target_id = rules.get("path_start_id"), rules.get("path_end_id")
    if source_id not in nodes or target_id not in nodes:
        raise InvalidEvidence("path endpoints must exist")
    route = _path(edges, source_id, target_id)
    topology = {"state":"PASS" if route else "UNAVAILABLE",
                "path_found":bool(route),"flow_edge_ids":route,
                "source_evidence_refs":[e["evidence_ref"] for e in edges if e["id"] in route],
                "node_count":len(nodes),"edge_count":len(edges)}
    mass = _mass_balance(nodes, edges, observation, rules)
    spectral = _spectrum(observation, rules, nodes, edges)
    vals = (topology["state"],mass["state"],spectral["state"])
    if "UNAVAILABLE" in vals:
        state="INSUFFICIENT_EVIDENCE"
    elif "FLAG" in vals:
        state="HUMAN_REVIEW"
    else:
        state="NO_EXCEPTION_DETECTED_IN_SYNTHETIC_FIXTURE"
    report = {
        "schema_version":"szl.synthetic-causal-twin-receipt.v0.1",
        "source_class":"SYNTHETIC_ONLY",
        "observed_utc":observation["observed_utc"],
        "graph_source_revision":source["revision"],
        "source_sha256":_sha(source),"graph_sha256":_sha(evidence["graph"]),
        "input_sha256":_sha(evidence),
        "assessments":{"topology":topology,"mass_balance":mass,"pressure_fft":spectral},
        "decision":{"state":state,"automated_actuation":"DENIED",
                    "recommended_next_gate":"independently validate drawing, calibration, sensor timestamps and on-site safety review"},
        "assurance":{"receipt":"SHA256_INTEGRITY_ONLY","signature":"UNSIGNED","independent_witness":"NONE",
                     "model_trained":False,"model_quality_evaluated":False,"live_facility_observed":False,
                     "physics_model_validated":False,"production_qualified":False}
    }
    report["receipt_sha256"]=_sha(report)
    return report


def verify_receipt(report: dict) -> bool:
    if not isinstance(report, dict):
        return False
    digest = report.get("receipt_sha256")
    if not isinstance(digest,str) or len(digest)!=64:
        return False
    payload = {k:v for k,v in report.items() if k!="receipt_sha256"}
    try:
        return hashlib.sha256(_canonical(payload)).hexdigest()==digest
    except (TypeError,ValueError):
        return False
