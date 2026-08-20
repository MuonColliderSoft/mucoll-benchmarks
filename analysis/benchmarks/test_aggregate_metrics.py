#!/usr/bin/env python3
"""ROOT-independent tests for study fragments and report aggregation."""

import json
import pathlib
import sys
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
EDM4HEP = HERE.parent / "python" / "edm4hep"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EDM4HEP))

import aggregate_metrics
import benchmark_metrics


class FakeAxis:
    def GetXmin(self):
        return -1.0

    def GetXmax(self):
        return 1.0


class FakeHistogram:
    def GetXaxis(self):
        return FakeAxis()

    def GetNbinsX(self):
        return 2

    def GetEntries(self):
        return 4

    def GetMean(self):
        return 0.25

    def GetStdDev(self):
        return 0.5

    def GetBinContent(self, index):
        return {0: 1.0, 3: 2.0}.get(index, 0.0)


class MetricsTest(unittest.TestCase):
    def make_fragment(self, directory, study="tracks", total=10):
        input_path = directory / "reco.edm4hep.root"
        if not input_path.exists():
            input_path.write_bytes(b"edm4hep test input")
        fragment = directory / ("metrics_{}.json".format(study))
        benchmark_metrics.write_fragment(
            fragment,
            study=study,
            input_path=input_path,
            producer_path=__file__,
            total_events=total,
            selected_events=total - 1,
            configuration={"cut": 0.5},
            metrics={"efficiency": 0.9},
        )
        return input_path, fragment

    def test_histogram_summary_records_range_and_flow(self):
        result = benchmark_metrics.histogram_summary(FakeHistogram())
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["range"], [-1.0, 1.0])
        self.assertEqual(result["underflow"], 1.0)
        self.assertEqual(result["overflow"], 2.0)

    def test_fragment_contains_producer_and_input_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, fragment_path = self.make_fragment(directory)
            fragment = json.loads(fragment_path.read_text())
            self.assertEqual(fragment["study"], "tracks")
            self.assertEqual(fragment["input"]["bytes"], input_path.stat().st_size)
            self.assertEqual(len(fragment["producer"]["sha256"]), 64)

    def test_aggregate_report_records_stack_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, fragment_path = self.make_fragment(directory)
            submission = directory / "submission.json"
            submission.write_text(json.dumps({"geometry": "MAIA_v0"}))
            report = aggregate_metrics.build_report(
                "pion",
                input_path,
                [fragment_path],
                expected_events=10,
                environment={
                    "MUCOLL_RELEASE_VERSION": "3.1",
                    "GITHUB_RUN_ID": "123",
                },
            )
            self.assertEqual(report["software"]["mucoll_stack_version"], "3.1")
            self.assertEqual(
                report["provenance"]["production"]["metadata"]["geometry"],
                "MAIA_v0",
            )
            self.assertEqual(
                report["provenance"]["github_actions"]["run_id"], "123"
            )
            self.assertIn("tracks", report["samples"]["pion"]["studies"])
            self.assertEqual(len(report["samples"]["pion"]["input"]["sha256"]), 64)

    def test_rejects_duplicate_study(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, fragment_path = self.make_fragment(directory)
            with self.assertRaisesRegex(RuntimeError, "duplicate"):
                aggregate_metrics.load_fragments(
                    [fragment_path, fragment_path], input_path
                )

    def test_rejects_event_count_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, first = self.make_fragment(directory, "tracks", 10)
            _, second = self.make_fragment(directory, "hits", 9)
            with self.assertRaisesRegex(RuntimeError, "event count"):
                aggregate_metrics.load_fragments([first, second], input_path)

    def test_expected_event_count_is_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, fragment_path = self.make_fragment(directory)
            with self.assertRaisesRegex(RuntimeError, "expected 11 events"):
                aggregate_metrics.load_fragments(
                    [fragment_path], input_path, expected_events=11
                )

    def test_stack_version_is_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            input_path, fragment_path = self.make_fragment(directory)
            with self.assertRaisesRegex(RuntimeError, "mucoll-stack version"):
                aggregate_metrics.build_report(
                    "pion", input_path, [fragment_path], environment={}
                )


if __name__ == "__main__":
    unittest.main()
