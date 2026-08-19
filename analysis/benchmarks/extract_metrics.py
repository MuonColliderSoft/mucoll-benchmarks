#!/usr/bin/env python3
"""Extract compact, machine-readable metrics from EDM4hep RECO files."""

import argparse
import collections
import datetime
import hashlib
import json
import math
import pathlib
import sys


METRIC_COLUMNS = (
    "truth_pdg",
    "truth_energy",
    "truth_momentum",
    "truth_pt",
    "truth_theta",
    "pfo_count",
    "selected_track_count",
    "ecal_hit_count",
    "hcal_hit_count",
    "ecal_energy",
    "hcal_energy",
    "total_pfo_energy_ratio",
    "nearest_delta_r",
    "matched",
    "matched_pdg",
    "matched_energy_ratio",
    "matched_momentum_ratio",
)

REQUIRED_COLLECTIONS = ("MCParticles", "PandoraPFOs")
OPTIONAL_COLLECTIONS = (
    "SiTracks_objIdx",
    "EcalBarrelCollectionRec",
    "EcalEndcapCollectionRec",
    "HcalBarrelCollectionRec",
    "HcalEndcapCollectionRec",
)


def parse_sample(value):
    """Parse LABEL=PATH while allowing '=' in the path."""
    try:
        label, path = value.split("=", 1)
    except ValueError:
        raise argparse.ArgumentTypeError("sample must have the form LABEL=PATH")
    if not label or not path:
        raise argparse.ArgumentTypeError("sample label and path must be non-empty")
    return label, pathlib.Path(path).expanduser().resolve()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def production_metadata(input_path):
    """Load the chain submission record when it accompanies the RECO file."""
    path = input_path.parent / "submission.json"
    if not path.is_file():
        return None
    try:
        metadata = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError("could not read production metadata {}: {}".format(path, error))
    return {
        "path": str(path),
        "sha256": sha256(path),
        "metadata": metadata,
    }


def _finite(values):
    return [float(value) for value in values if math.isfinite(float(value))]


def percentile(sorted_values, probability):
    if not sorted_values:
        return None
    position = probability * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def summary(values):
    """Return stable descriptive statistics, excluding non-finite values."""
    finite = sorted(_finite(values))
    if not finite:
        return {
            "count": 0,
            "mean": None,
            "stddev": None,
            "min": None,
            "p16": None,
            "median": None,
            "p84": None,
            "max": None,
        }
    mean = sum(finite) / len(finite)
    variance = sum((value - mean) ** 2 for value in finite) / len(finite)
    return {
        "count": len(finite),
        "mean": mean,
        "stddev": math.sqrt(variance),
        "min": finite[0],
        "p16": percentile(finite, 0.16),
        "median": percentile(finite, 0.50),
        "p84": percentile(finite, 0.84),
        "max": finite[-1],
    }


def count_values(values):
    counts = collections.Counter(int(value) for value in values)
    return {str(key): counts[key] for key in sorted(counts)}


def fraction(count, total):
    return float(count) / total if total else None


def declare_helpers(ROOT):
    ROOT.gInterpreter.Declare(
        r'''
#include "ROOT/RVec.hxx"
#include "edm4hep/CalorimeterHitData.h"
#include "edm4hep/MCParticleData.h"
#include "edm4hep/ReconstructedParticleData.h"
#include "podio/ObjectID.h"
#include <algorithm>
#include <cmath>
#include <limits>

using ROOT::VecOps::RVec;

struct BenchmarkMetricsEvent {
  int truth_pdg = 0;
  double truth_energy = std::numeric_limits<double>::quiet_NaN();
  double truth_momentum = std::numeric_limits<double>::quiet_NaN();
  double truth_pt = std::numeric_limits<double>::quiet_NaN();
  double truth_theta = std::numeric_limits<double>::quiet_NaN();
  int pfo_count = 0;
  int selected_track_count = 0;
  int ecal_hit_count = 0;
  int hcal_hit_count = 0;
  double ecal_energy = 0;
  double hcal_energy = 0;
  double total_pfo_energy_ratio = std::numeric_limits<double>::quiet_NaN();
  double nearest_delta_r = std::numeric_limits<double>::quiet_NaN();
  int matched = 0;
  int matched_pdg = 0;
  double matched_energy_ratio = std::numeric_limits<double>::quiet_NaN();
  double matched_momentum_ratio = std::numeric_limits<double>::quiet_NaN();
};

static double benchmarkDeltaPhi(double first, double second) {
  return std::remainder(first - second, 2.0 * M_PI);
}

static double benchmarkEta(double px, double py, double pz) {
  const double pt = std::hypot(px, py);
  if (pt == 0.0) {
    return std::copysign(std::numeric_limits<double>::infinity(), pz);
  }
  return std::asinh(pz / pt);
}

template <typename Momentum>
static double benchmarkMomentum(const Momentum& momentum) {
  return std::sqrt(momentum.x * momentum.x + momentum.y * momentum.y +
                   momentum.z * momentum.z);
}

BenchmarkMetricsEvent benchmarkMetrics(
    const RVec<edm4hep::MCParticleData>& mc_particles,
    const RVec<edm4hep::ReconstructedParticleData>& pfos,
    const RVec<podio::ObjectID>& selected_tracks,
    const RVec<edm4hep::CalorimeterHitData>& ecal_barrel,
    const RVec<edm4hep::CalorimeterHitData>& ecal_endcap,
    const RVec<edm4hep::CalorimeterHitData>& hcal_barrel,
    const RVec<edm4hep::CalorimeterHitData>& hcal_endcap,
    double match_delta_r_max) {
  BenchmarkMetricsEvent result;
  result.pfo_count = static_cast<int>(pfos.size());
  result.selected_track_count = static_cast<int>(selected_tracks.size());
  result.ecal_hit_count = static_cast<int>(ecal_barrel.size() + ecal_endcap.size());
  result.hcal_hit_count = static_cast<int>(hcal_barrel.size() + hcal_endcap.size());
  for (const auto& hit : ecal_barrel) result.ecal_energy += hit.energy;
  for (const auto& hit : ecal_endcap) result.ecal_energy += hit.energy;
  for (const auto& hit : hcal_barrel) result.hcal_energy += hit.energy;
  for (const auto& hit : hcal_endcap) result.hcal_energy += hit.energy;

  if (mc_particles.empty()) return result;
  const auto& truth = mc_particles.front();
  result.truth_pdg = truth.PDG;
  result.truth_momentum = benchmarkMomentum(truth.momentum);
  result.truth_pt = std::hypot(truth.momentum.x, truth.momentum.y);
  result.truth_theta = std::atan2(result.truth_pt, truth.momentum.z);
  result.truth_energy = std::hypot(result.truth_momentum, truth.mass);
  if (result.truth_energy <= 0.0) return result;

  double total_pfo_energy = 0.0;
  int nearest = -1;
  double nearest_delta_r = std::numeric_limits<double>::infinity();
  const double truth_eta = benchmarkEta(
      truth.momentum.x, truth.momentum.y, truth.momentum.z);
  const double truth_phi = std::atan2(truth.momentum.y, truth.momentum.x);
  for (std::size_t index = 0; index < pfos.size(); ++index) {
    const auto& pfo = pfos[index];
    total_pfo_energy += pfo.energy;
    const double pfo_eta = benchmarkEta(
        pfo.momentum.x, pfo.momentum.y, pfo.momentum.z);
    const double pfo_phi = std::atan2(pfo.momentum.y, pfo.momentum.x);
    const double delta_eta = pfo_eta - truth_eta;
    const double delta_phi = benchmarkDeltaPhi(pfo_phi, truth_phi);
    const double delta_r = std::hypot(delta_eta, delta_phi);
    if (delta_r < nearest_delta_r) {
      nearest = static_cast<int>(index);
      nearest_delta_r = delta_r;
    }
  }
  result.total_pfo_energy_ratio = total_pfo_energy / result.truth_energy;
  if (nearest < 0) return result;

  result.nearest_delta_r = nearest_delta_r;
  if (nearest_delta_r >= match_delta_r_max) return result;
  const auto& matched = pfos[nearest];
  result.matched = 1;
  result.matched_pdg = matched.PDG;
  result.matched_energy_ratio = matched.energy / result.truth_energy;
  if (result.truth_momentum > 0.0) {
    result.matched_momentum_ratio =
        benchmarkMomentum(matched.momentum) / result.truth_momentum;
  }
  return result;
}
'''
    )


def collection_expression(columns, name, cpp_type):
    if name in columns:
        return name
    return "ROOT::VecOps::RVec<{}>{{}}".format(cpp_type)


def read_sample(ROOT, label, path, match_delta_r):
    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError("could not open {}".format(path))
    tree = root_file.Get("events")
    if not tree:
        raise RuntimeError("events tree not found in {}".format(path))
    event_count = int(tree.GetEntries())
    branch_names = {branch.GetName() for branch in tree.GetListOfBranches()}
    root_file.Close()

    missing = sorted(set(REQUIRED_COLLECTIONS) - branch_names)
    if missing:
        raise RuntimeError(
            "{} is missing required collections: {}".format(path, ", ".join(missing))
        )

    df = ROOT.RDataFrame("events", str(path))
    expressions = {
        "selected_tracks": collection_expression(
            branch_names, "SiTracks_objIdx", "podio::ObjectID"
        ),
        "ecal_barrel": collection_expression(
            branch_names, "EcalBarrelCollectionRec", "edm4hep::CalorimeterHitData"
        ),
        "ecal_endcap": collection_expression(
            branch_names, "EcalEndcapCollectionRec", "edm4hep::CalorimeterHitData"
        ),
        "hcal_barrel": collection_expression(
            branch_names, "HcalBarrelCollectionRec", "edm4hep::CalorimeterHitData"
        ),
        "hcal_endcap": collection_expression(
            branch_names, "HcalEndcapCollectionRec", "edm4hep::CalorimeterHitData"
        ),
    }
    for name, expression in expressions.items():
        df = df.Define(name, expression)
    df = df.Define(
        "benchmark",
        "benchmarkMetrics(MCParticles, PandoraPFOs, selected_tracks, "
        "ecal_barrel, ecal_endcap, hcal_barrel, hcal_endcap, {:.17g})".format(
            match_delta_r
        ),
    )
    for name in METRIC_COLUMNS:
        df = df.Define(name, "benchmark.{}".format(name))
    arrays = df.AsNumpy(list(METRIC_COLUMNS))

    matched_mask = [bool(value) for value in arrays["matched"]]
    matched_values = lambda name: [
        value for value, matched in zip(arrays[name], matched_mask) if matched
    ]
    track_event_count = int(
        sum(bool(value > 0) for value in arrays["selected_track_count"])
    )
    matched_event_count = int(sum(matched_mask))

    return {
        "label": label,
        "input": {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        },
        "production": production_metadata(path),
        "event_count": event_count,
        "collections": {
            name: name in branch_names
            for name in REQUIRED_COLLECTIONS + OPTIONAL_COLLECTIONS
        },
        "truth": {
            "pdg_counts": count_values(arrays["truth_pdg"]),
            "energy_gev": summary(arrays["truth_energy"]),
            "momentum_gev": summary(arrays["truth_momentum"]),
            "pt_gev": summary(arrays["truth_pt"]),
            "theta_rad": summary(arrays["truth_theta"]),
        },
        "reconstruction": {
            "pfo_multiplicity": summary(arrays["pfo_count"]),
            "selected_track_multiplicity": summary(arrays["selected_track_count"]),
            "events_with_selected_track": track_event_count,
            "events_with_selected_track_fraction": fraction(
                track_event_count, event_count
            ),
            "ecal_hit_multiplicity": summary(arrays["ecal_hit_count"]),
            "hcal_hit_multiplicity": summary(arrays["hcal_hit_count"]),
            "ecal_energy_gev": summary(arrays["ecal_energy"]),
            "hcal_energy_gev": summary(arrays["hcal_energy"]),
            "total_pfo_energy_over_truth_energy": summary(
                arrays["total_pfo_energy_ratio"]
            ),
            "nearest_pfo_delta_r": summary(arrays["nearest_delta_r"]),
            "matched_events": matched_event_count,
            "matched_fraction": fraction(matched_event_count, event_count),
            "matched_pdg_counts": count_values(matched_values("matched_pdg")),
            "matched_energy_over_truth_energy": summary(
                matched_values("matched_energy_ratio")
            ),
            "matched_momentum_over_truth_momentum": summary(
                matched_values("matched_momentum_ratio")
            ),
        },
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        action="append",
        type=parse_sample,
        required=True,
        metavar="LABEL=PATH",
        help="label and RECO input path; repeat for multiple samples",
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--match-delta-r", type=float, default=0.1)
    parser.add_argument(
        "--expected-events",
        type=int,
        help="fail unless every sample contains this many events",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not 0.0 < args.match_delta_r:
        raise SystemExit("--match-delta-r must be positive")
    labels = [label for label, _ in args.sample]
    if len(labels) != len(set(labels)):
        raise SystemExit("sample labels must be unique")
    for _, path in args.sample:
        if not path.is_file():
            raise SystemExit("RECO input not found: {}".format(path))

    try:
        import ROOT
    except ImportError:
        raise SystemExit(
            "PyROOT is required; run inside the mucoll-sim container after "
            "sourcing /opt/setup_mucoll.sh"
        )

    ROOT.gROOT.SetBatch(True)
    declare_helpers(ROOT)
    samples = {}
    for label, path in args.sample:
        print("Extracting {} from {}".format(label, path), file=sys.stderr)
        sample = read_sample(ROOT, label, path, args.match_delta_r)
        if args.expected_events is not None and sample["event_count"] != args.expected_events:
            raise SystemExit(
                "{}: expected {} events, found {}".format(
                    label, args.expected_events, sample["event_count"]
                )
            )
        samples[label] = sample

    output = {
        "schema_version": 1,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "configuration": {"match_delta_r_max": args.match_delta_r},
        "extractor": {
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": sha256(pathlib.Path(__file__).resolve()),
        },
        "software": {"root_version": str(ROOT.gROOT.GetVersion())},
        "samples": samples,
    }
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Wrote {}".format(output_path))


if __name__ == "__main__":
    main()
