"""Small shared helpers for benchmark-study JSON sidecars."""

import hashlib
import json
import math
import pathlib


FRAGMENT_SCHEMA_VERSION = 1


def sha256(path):
    """Return the SHA-256 checksum of *path*."""
    path = pathlib.Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fraction(numerator, denominator):
    """Return a JSON-safe fraction, or ``None`` for an empty denominator."""
    return float(numerator) / denominator if denominator else None


def finite(value):
    """Convert a finite numeric value to float, otherwise return ``None``."""
    value = float(value)
    return value if math.isfinite(value) else None


def histogram_summary(histogram):
    """Summarise a TH1 while making its finite range explicit."""
    axis = histogram.GetXaxis()
    bins = histogram.GetNbinsX()
    return {
        "count": int(round(histogram.GetEntries())),
        "mean": finite(histogram.GetMean()),
        "stddev": finite(histogram.GetStdDev()),
        "range": [float(axis.GetXmin()), float(axis.GetXmax())],
        "underflow": finite(histogram.GetBinContent(0)),
        "overflow": finite(histogram.GetBinContent(bins + 1)),
    }


def write_fragment(
    output_path,
    study,
    input_path,
    producer_path,
    total_events,
    selected_events,
    configuration,
    metrics,
):
    """Write one independently consumable study-metrics fragment."""
    if not output_path:
        return
    input_path = pathlib.Path(input_path).expanduser().resolve()
    producer_path = pathlib.Path(producer_path).resolve()
    output_path = pathlib.Path(output_path)
    fragment = {
        "schema_version": FRAGMENT_SCHEMA_VERSION,
        "study": study,
        "input": {
            "path": str(input_path),
            "bytes": input_path.stat().st_size,
        },
        "producer": {
            "name": producer_path.name,
            "sha256": sha256(producer_path),
        },
        "events": {
            "total": int(total_events),
            "selected": int(selected_events),
        },
        "configuration": configuration,
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fragment, allow_nan=False, indent=2, sort_keys=True) + "\n"
    )


def declare_matching_helpers(ROOT):
    """Declare the common momentum delta-R helper used by object studies."""
    ROOT.gInterpreter.Declare(
        r'''
#include <cmath>
#include <limits>

namespace MuCollBenchmarks {

template <typename Momentum>
static double eta(const Momentum& momentum) {
  const double pt = std::hypot(momentum.x, momentum.y);
  if (pt == 0.0) {
    return std::copysign(std::numeric_limits<double>::infinity(), momentum.z);
  }
  return std::asinh(momentum.z / pt);
}

template <typename FirstMomentum, typename SecondMomentum>
static double deltaR(const FirstMomentum& first, const SecondMomentum& second) {
  const double delta_eta = eta(first) - eta(second);
  const double first_phi = std::atan2(first.y, first.x);
  const double second_phi = std::atan2(second.y, second.x);
  const double delta_phi = std::remainder(first_phi - second_phi, 2.0 * M_PI);
  return std::hypot(delta_eta, delta_phi);
}

}  // namespace MuCollBenchmarks
'''
    )
