"""Independent deterministic checks of the synthetic pilot's scope and invariants."""
import cmath
import copy
import json
import math
import unittest
import tempfile
import io
from contextlib import redirect_stderr,redirect_stdout
from szl_causal_twin.cli import main as cli_main
from pathlib import Path
from szl_causal_twin.core import evaluate,verify_receipt,InvalidEvidence,_fft

BASE=Path(__file__).resolve().parents[1]/"examples"/"healthy-synthetic-water.json"


def fixture():
    return json.loads(BASE.read_text(encoding="utf-8"))


class PilotTests(unittest.TestCase):
    def test_healthy(self):
        r=evaluate(fixture())
        self.assertEqual(r["decision"]["state"],"NO_EXCEPTION_DETECTED_IN_SYNTHETIC_FIXTURE")
        self.assertTrue(verify_receipt(r))
        self.assertFalse(r["assurance"]["production_qualified"])
        self.assertEqual(r["decision"]["automated_actuation"],"DENIED")

    def test_mass_imbalance(self):
        x=fixture();x["observation"]["flows_lps"]["TANK_TO_PUMP"]=3.1
        r=evaluate(x)
        self.assertEqual(r["assessments"]["mass_balance"]["state"],"FLAG")
        self.assertAlmostEqual(r["assessments"]["mass_balance"]["residual_lps"],0.9)
        self.assertEqual(r["decision"]["state"],"HUMAN_REVIEW")

    def test_storage_rate_cancels_flow(self):
        x=fixture();x["observation"]["flows_lps"]["TANK_TO_PUMP"]=3.1
        x["observation"]["tank_volume_liters_end"] += 54 # 0.9L/s * 60s
        self.assertEqual(evaluate(x)["assessments"]["mass_balance"]["state"],"PASS")

    def test_pressure_peak_flag(self):
        x=fixture()
        x["observation"]["pressure_sensor"]["samples"]=[200+30*math.sin(2*math.pi*2*j/16) for j in range(16)]
        r=evaluate(x)
        self.assertEqual(r["assessments"]["pressure_fft"]["state"],"FLAG")
        self.assertAlmostEqual(r["assessments"]["pressure_fft"]["peak_frequency_hz"],0.125)
        self.assertAlmostEqual(r["assessments"]["pressure_fft"]["peak_amplitude_kpa"],30)

    def test_nyquist_alias_must_abstain_even_below_flag_threshold(self):
        x=fixture()
        x["observation"]["pressure_sensor"]["samples"]=[
            200.0+5.0*((-1)**j) for j in range(16)
        ]
        report=evaluate(x)
        peak=report["assessments"]["pressure_fft"]
        self.assertEqual(peak["state"],"UNAVAILABLE")
        self.assertEqual(peak["reason"],"nyquist_edge_unresolved")
        self.assertEqual(peak["n_samples"],16)
        self.assertEqual(peak["nyquist_hz"],0.5)
        self.assertAlmostEqual(peak["relative_oscillation"],0.025)
        self.assertEqual(report["decision"]["state"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(report["decision"]["automated_actuation"],"DENIED")
        self.assertTrue(verify_receipt(report))

    def test_sub_nyquist_peak_keeps_existing_pass_and_flag(self):
        x=fixture()
        x["observation"]["pressure_sensor"]["samples"]=[
            200.0+5.0*math.sin(2*math.pi*2*j/16) for j in range(16)
        ]
        stable=evaluate(x)
        self.assertEqual(stable["assessments"]["pressure_fft"]["state"],"PASS")
        self.assertEqual(stable["decision"]["state"],
                         "NO_EXCEPTION_DETECTED_IN_SYNTHETIC_FIXTURE")
        x["observation"]["pressure_sensor"]["samples"]=[
            200.0+30.0*math.sin(2*math.pi*2*j/16) for j in range(16)
        ]
        flagged=evaluate(x)
        self.assertEqual(flagged["assessments"]["pressure_fft"]["state"],"FLAG")
        self.assertEqual(flagged["decision"]["state"],"HUMAN_REVIEW")

    def test_extreme_finite_spectral_values_abstain_without_nonfinite_json(self):
        for kind in ("huge_pressure","too_short_interval","too_long_interval"):
            x=fixture()
            pressure=x["observation"]["pressure_sensor"]
            if kind=="huge_pressure":
                pressure["samples"]=[1e308]*16
                expected_reason="spectral_derived_nonfinite"
            elif kind=="too_short_interval":
                pressure["sample_interval_seconds"]=1e-320
                expected_reason="spectral_numeric_resolution_unavailable"
            else:
                pressure["sample_interval_seconds"]=1e308
                expected_reason="spectral_numeric_resolution_unavailable"
            with self.subTest(kind=kind):
                report=evaluate(x)
                self.assertEqual(report["assessments"]["pressure_fft"]["state"],"UNAVAILABLE")
                self.assertEqual(report["assessments"]["pressure_fft"]["reason"],expected_reason)
                self.assertEqual(report["decision"]["state"],"INSUFFICIENT_EVIDENCE")
                self.assertEqual(report["decision"]["automated_actuation"],"DENIED")
                self.assertTrue(verify_receipt(report))
                self.assertNotIn("Infinity",json.dumps(report,allow_nan=False))

    def test_fft_matches_direct_dft(self):
        x=[3*math.sin(2*math.pi*3*n/16)+10 for n in range(16)]
        fft=_fft(x)
        brute=[sum(x[n]*cmath.exp(-2j*math.pi*k*n/16) for n in range(16)) for k in range(16)]
        for a,b in zip(fft,brute):self.assertAlmostEqual(abs(a-b),0,places=9)

    def test_missing_flow_abstains_not_normal(self):
        x=fixture();del x["observation"]["flows_lps"]["TANK_TO_PUMP"]
        r=evaluate(x)
        self.assertEqual(r["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_missing_source_lineage_abstains(self):
        x=fixture();del x["observation"]["flow_evidence_refs"]
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_unbound_pressure_sensor_abstains(self):
        x=fixture();x["observation"]["pressure_sensor"]["id"]="not-in-graph"
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_missing_pressure_abstains(self):
        x=fixture();del x["observation"]["pressure_sensor"]
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_real_data_denied(self):
        x=fixture();x["synthetic"]=False
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_wrong_units_denied(self):
        x=fixture();x["observation"]["flow_unit"]="gal/min"
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_wrong_pressure_unit_unavailable(self):
        x=fixture();x["observation"]["pressure_sensor"]["unit"]="psi"
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_dangling_graph_ref_denied(self):
        x=fixture();x["graph"]["edges"][0]["to"]="NONEXISTENT"
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_missing_graph_path_is_unavailable(self):
        x=fixture();x["graph"]["edges"]=[e for e in x["graph"]["edges"] if e["id"]!="TO_COMMUNITY"]
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_bad_clock_denied(self):
        x=fixture();x["observation"]["observed_utc"]="2026-11-16"
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_duplicate_nodes_denied(self):
        x=fixture();x["graph"]["nodes"].append(copy.deepcopy(x["graph"]["nodes"][0]))
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_nonfinite_denied(self):
        x=fixture();x["observation"]["tank_volume_liters_end"]=float("nan")
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_integrity_detects_tamper(self):
        r=evaluate(fixture())
        r["decision"]["state"]="QUALIFIED"
        self.assertFalse(verify_receipt(r))

    def test_identical_input_identical_hash(self):
        a=evaluate(fixture());b=evaluate(fixture())
        self.assertEqual(a,b)

    def test_source_rights_denied(self):
        x=fixture();x["source"]["rights"]="UNKNOWN"
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_negative_flow_denied(self):
        x=fixture();x["observation"]["flows_lps"]["TANK_TO_PUMP"]=-3
        with self.assertRaises(InvalidEvidence):evaluate(x)

    def test_stale_flow_is_unavailable(self):
        x=fixture();x["observation"]["flow_sampled_utc"]["TANK_TO_PUMP"]="2026-11-16T21:00:00Z"
        self.assertEqual(evaluate(x)["assessments"]["mass_balance"]["state"],"UNAVAILABLE")
        self.assertEqual(evaluate(x)["decision"]["state"],"INSUFFICIENT_EVIDENCE")

    def test_future_pressure_clock_is_unavailable(self):
        x=fixture();x["observation"]["pressure_sensor"]["sampled_utc"]="2026-11-16T22:10:00Z"
        self.assertEqual(evaluate(x)["assessments"]["pressure_fft"]["state"],"UNAVAILABLE")

    def test_cli_refuses_overwrite_and_does_not_corrupt_record(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"receipt.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli_main([str(BASE),"--out",str(out)]),0)
            first=out.read_bytes()
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli_main([str(BASE),"--out",str(out)]),2)
            self.assertEqual(out.read_bytes(),first)
            self.assertTrue(verify_receipt(json.loads(first)))

    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as td:
            malformed=Path(td)/"dup.json"
            malformed.write_text('{"schema_version":"test","schema_version":"evil"}',encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli_main([str(malformed),"--out",str(Path(td)/"receipt.json")]),2)
            self.assertFalse((Path(td)/"receipt.json").exists())

    def test_no_actuation_on_flag(self):
        x=fixture();x["observation"]["flows_lps"]["TANK_TO_PUMP"]=0
        r=evaluate(x)
        self.assertEqual(r["decision"]["automated_actuation"],"DENIED")
        self.assertEqual(r["assurance"]["signature"],"UNSIGNED")

if __name__=="__main__":unittest.main()
