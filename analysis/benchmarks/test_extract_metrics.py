#!/usr/bin/env python3
"""Unit tests for ROOT-independent benchmark metric helpers."""

import argparse
import json
import math
import pathlib
import tempfile
import unittest

import extract_metrics


class MetricHelpersTest(unittest.TestCase):
    def test_parse_sample(self):
        label, path = extract_metrics.parse_sample("muon=sample.root")
        self.assertEqual(label, "muon")
        self.assertEqual(path, pathlib.Path("sample.root").resolve())

    def test_parse_sample_rejects_missing_label(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            extract_metrics.parse_sample("=sample.root")

    def test_summary(self):
        result = extract_metrics.summary([1, 2, 3, float("nan")])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["mean"], 2)
        self.assertAlmostEqual(result["stddev"], math.sqrt(2.0 / 3.0))
        self.assertEqual(result["median"], 2)

    def test_empty_summary_is_valid_json_shape(self):
        result = extract_metrics.summary([float("nan"), float("inf")])
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["mean"])

    def test_counts_are_sorted_and_string_keyed(self):
        self.assertEqual(
            extract_metrics.count_values([22, 11, 22]), {"11": 1, "22": 2}
        )

    def test_production_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            submission = directory / "submission.json"
            submission.write_text(json.dumps({"events": 100}))
            result = extract_metrics.production_metadata(directory / "reco.root")
            self.assertEqual(result["metadata"], {"events": 100})
            self.assertEqual(len(result["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
