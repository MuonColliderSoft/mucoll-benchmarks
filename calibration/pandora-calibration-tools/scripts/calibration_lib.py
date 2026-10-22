#!/usr/bin/env python3
"""Shared utilities for ECAL/HCAL theta-energy calibration production."""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import math
import os
from typing import Iterable, List, Sequence, Tuple


def parse_float_list(value: str) -> List[float]:
    if not value.strip():
        return []
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def parse_int_list(value: str) -> List[int]:
    if not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def ensure_strictly_increasing(values: Sequence[float], name: str) -> None:
    if len(values) < 2:
        raise ValueError(f"{name} must contain at least two edges")
    for i in range(1, len(values)):
        if values[i] <= values[i - 1]:
            raise ValueError(f"{name} must be strictly increasing; failed at index {i}")


def find_bin(edges: Sequence[float], value: float) -> int:
    """Find bin index in [0, len(edges)-2], return -1 for under/overflow."""
    if value < edges[0] or value >= edges[-1]:
        return -1
    for i in range(len(edges) - 1):
        if edges[i] <= value < edges[i + 1]:
            return i
    return -1


def flatten_index(i_theta: int, i_energy: int, n_energy_bins: int) -> int:
    return i_theta * n_energy_bins + i_energy


def expand_input_paths(inputs: Sequence[str], file_glob: str, recursive: bool = False) -> List[str]:
    files: List[str] = []

    def add_from_directory(directory: str) -> None:
        pattern = os.path.join(directory, "**", file_glob) if recursive else os.path.join(directory, file_glob)
        files.extend(glob.glob(pattern, recursive=recursive))

    for item in inputs:
        if any(c in item for c in "*?[]"):
            matches = glob.glob(item)
            for m in matches:
                if os.path.isdir(m):
                    add_from_directory(m)
                elif os.path.isfile(m):
                    files.append(m)
            continue
        if os.path.isdir(item):
            add_from_directory(item)
            continue
        if os.path.isfile(item):
            files.append(item)
    files = sorted(set([f for f in files if os.path.isfile(f)]))
    return files


def robust_estimate(values: Sequence[float], estimator: str, trim_fraction: float) -> float:
    if not values:
        return 1.0
    if estimator == "mean":
        return sum(values) / float(len(values))
    sorted_values = sorted(values)
    if estimator == "median":
        n = len(sorted_values)
        mid = n // 2
        if n % 2:
            return sorted_values[mid]
        return 0.5 * (sorted_values[mid - 1] + sorted_values[mid])
    if estimator == "trimmed_mean":
        n = len(sorted_values)
        trim = int(n * trim_fraction)
        lo = min(trim, n - 1)
        hi = max(lo + 1, n - trim)
        trimmed = sorted_values[lo:hi]
        return sum(trimmed) / float(len(trimmed))
    raise ValueError(f"Unknown estimator: {estimator}")


@dataclasses.dataclass
class CalibrationTable:
    domain: str
    theta_edges: List[float]
    energy_edges: List[float]
    scales: List[float]
    counts: List[int]
    metadata: dict

    def validate(self) -> None:
        ensure_strictly_increasing(self.theta_edges, "theta_edges")
        ensure_strictly_increasing(self.energy_edges, "energy_edges")
        n_theta = len(self.theta_edges) - 1
        n_energy = len(self.energy_edges) - 1
        expected = n_theta * n_energy
        if len(self.scales) != expected:
            raise ValueError(f"scales size {len(self.scales)} does not match expected {expected}")
        if len(self.counts) != expected:
            raise ValueError(f"counts size {len(self.counts)} does not match expected {expected}")

    def lookup(self, theta: float, energy: float) -> float:
        i_theta = find_bin(self.theta_edges, theta)
        i_energy = find_bin(self.energy_edges, energy)
        if i_theta < 0 or i_energy < 0:
            return 1.0
        n_energy = len(self.energy_edges) - 1
        return self.scales[flatten_index(i_theta, i_energy, n_energy)]

    def to_json_dict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_json_dict(data: dict) -> "CalibrationTable":
        table = CalibrationTable(
            domain=data["domain"],
            theta_edges=list(data["theta_edges"]),
            energy_edges=list(data["energy_edges"]),
            scales=list(data["scales"]),
            counts=list(data.get("counts", [0] * len(data["scales"]))),
            metadata=dict(data.get("metadata", {})),
        )
        table.validate()
        return table


def save_table_json(table: CalibrationTable, output_path: str) -> None:
    table.validate()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(table.to_json_dict(), f, indent=2, sort_keys=True)


def load_table_json(path: str) -> CalibrationTable:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CalibrationTable.from_json_dict(data)


def get_ecal_table_energy(table: CalibrationTable, raw_ecal_energy: float) -> float:
    basis = str(table.metadata.get("energy_basis", "raw")).lower()
    if basis == "raw":
        return raw_ecal_energy
    if basis == "em":
        return raw_ecal_energy * float(table.metadata.get("ecal_to_em_gev", 1.0))
    raise ValueError(f"Unsupported ECAL calibration energy_basis: {basis}")


def apply_ecal_calibration(table: CalibrationTable, theta: float, raw_ecal_energy: float) -> float:
    table_energy = get_ecal_table_energy(table, raw_ecal_energy)
    return table.lookup(theta, table_energy) * table_energy


def get_hadronic_table_energy(table: CalibrationTable, raw_ecal_energy: float, raw_hcal_energy: float) -> float:
    basis = str(table.metadata.get("energy_basis", "raw")).lower()
    if basis != "hadronic":
        raise ValueError(f"Unsupported hadronic calibration energy_basis: {basis}")
    ecal_to_had = float(table.metadata.get("ecal_to_had_gev", 1.0))
    hcal_to_had = float(table.metadata.get("hcal_to_had_gev", 1.0))
    return raw_ecal_energy * ecal_to_had + raw_hcal_energy * hcal_to_had


def apply_hadronic_calibration(table: CalibrationTable, theta: float, raw_ecal_energy: float, raw_hcal_energy: float) -> float:
    table_energy = get_hadronic_table_energy(table, raw_ecal_energy, raw_hcal_energy)
    return table.lookup(theta, table_energy) * table_energy


def _fmt_float(x: float) -> str:
    return f"{x:.8g}"


def table_to_ddmarlin_params(table: CalibrationTable) -> dict:
    """Return one-domain DDMarlin steering parameters as string vectors."""
    prefix = "ECal" if table.domain.upper() == "ECAL" else "HCal"
    return {
        f"{prefix}ThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in table.theta_edges],
        f"{prefix}ThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in table.energy_edges],
        f"{prefix}ThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in table.scales],
    }


def combine_ddmarlin_params(ecal_table: CalibrationTable, hcal_table: CalibrationTable, plugin_name: str = "ThetaEnergyBinned") -> dict:
    params = {
        "ThetaEnergyCorrectionEnabled": ["true"],
        "ThetaEnergyCorrectionPluginName": [plugin_name],
    }
    params.update(table_to_ddmarlin_params(ecal_table))
    params.update(table_to_ddmarlin_params(hcal_table))
    return params


def build_photon_em_ddmarlin_params(
    em_table: CalibrationTable,
    plugin_name: str = "PhotonEMNonLinearity",
) -> dict:
    if em_table.domain.upper() != "ECAL":
        raise ValueError(f"Photon EM payload expects ECAL-domain table, got {em_table.domain}")
    if str(em_table.metadata.get("energy_basis", "raw")).lower() != "em":
        raise ValueError("Photon EM payload expects an ECAL table built with --energy-basis em")

    return {
        "ElectromagneticThetaEnergyCorrectionEnabled": ["true"],
        "ElectromagneticThetaEnergyCorrectionPluginName": [plugin_name],
        "ElectromagneticThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in em_table.theta_edges],
        "ElectromagneticThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in em_table.energy_edges],
        "ElectromagneticThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in em_table.scales],
    }


def build_hadronic_ddmarlin_params(
    hadronic_table: CalibrationTable,
    plugin_name: str = "HadronicThetaEnergyBinned",
) -> dict:
    if hadronic_table.domain.upper() != "HADRONIC":
        raise ValueError(f"Hadronic payload expects HADRONIC-domain table, got {hadronic_table.domain}")
    if str(hadronic_table.metadata.get("energy_basis", "raw")).lower() != "hadronic":
        raise ValueError("Hadronic payload expects a table built with --energy-basis hadronic")

    return {
        "HadronicThetaEnergyCorrectionEnabled": ["true"],
        "HadronicThetaEnergyCorrectionPluginName": [plugin_name],
        "HadronicThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in hadronic_table.theta_edges],
        "HadronicThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in hadronic_table.energy_edges],
        "HadronicThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in hadronic_table.scales],
    }


def combine_branch_ddmarlin_params(
    ecal_table: CalibrationTable,
    hcal_table: CalibrationTable,
    branch: str,
    plugin_name: str = "ThetaEnergyBinned",
) -> dict:
    branch_key = branch.strip().lower()
    if branch_key == "hadronic":
        prefix = "Hadronic"
    elif branch_key == "electromagnetic":
        prefix = "Electromagnetic"
    else:
        raise ValueError(f"Unsupported branch: {branch}")

    return {
        f"{prefix}ThetaEnergyCorrectionEnabled": ["true"],
        f"{prefix}ThetaEnergyCorrectionPluginName": [plugin_name],
        f"{prefix}ECalThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in ecal_table.theta_edges],
        f"{prefix}ECalThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in ecal_table.energy_edges],
        f"{prefix}ECalThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in ecal_table.scales],
        f"{prefix}HCalThetaEnergyCorrectionThetaBinEdges": [_fmt_float(x) for x in hcal_table.theta_edges],
        f"{prefix}HCalThetaEnergyCorrectionEnergyBinEdges": [_fmt_float(x) for x in hcal_table.energy_edges],
        f"{prefix}HCalThetaEnergyCorrectionScaleFactors": [_fmt_float(x) for x in hcal_table.scales],
    }


def _vec_xyz(vec):
    """
    Return (x, y, z) from a momentum/position accessor.

    LCIO hands back an indexable array; EDM4hep hands back a Vector3d/Vector3f
    with .x/.y/.z attributes. Accept either so the physics code below does not
    have to care which file format it is reading.
    """
    try:
        return float(vec[0]), float(vec[1]), float(vec[2])
    except (TypeError, IndexError, KeyError):
        return float(vec.x), float(vec.y), float(vec.z)


def _coll_size(collection) -> int:
    """Number of elements, for either an LCIO collection or an EDM4hep one."""
    getter = getattr(collection, "getNumberOfElements", None)
    if getter is not None:
        return int(getter())
    return len(collection)


def mcp_energy(mcp) -> float:
    """
    Truth particle energy.

    LCIO MCParticle carries getEnergy() directly. EDM4hep MCParticle may or may
    not, depending on the version, so fall back to sqrt(p^2 + m^2).
    """
    getter = getattr(mcp, "getEnergy", None)
    if getter is not None:
        try:
            return float(getter())
        except Exception:
            pass
    px, py, pz = _vec_xyz(mcp.getMomentum())
    mass = float(mcp.getMass())
    return math.sqrt(px * px + py * py + pz * pz + mass * mass)


class _EDM4hepEvent:
    """Wraps a podio Frame so it answers getCollection() like an LCEvent."""

    def __init__(self, frame):
        self._frame = frame

    def getCollection(self, name: str):
        collection = self._frame.get(name)
        if collection is None:
            raise KeyError(f"collection '{name}' not in frame")
        return collection


class EDM4hepReader:
    """
    Minimal stand-in for the pyLCIO reader, backed by podio.

    Supports the same four operations the calibration scripts use:
    setReadCollectionNames(), open(), iteration, close(). Collection names are
    accepted and ignored - podio reads lazily, so there is nothing to preselect.
    """

    def __init__(self, collection_names: Sequence[str] = ()):
        self._collection_names = list(collection_names)
        self._frames = None

    def setReadCollectionNames(self, collection_names: Sequence[str]) -> None:
        self._collection_names = list(collection_names)

    def open(self, path: str) -> None:
        try:
            from podio.root_io import Reader  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "podio is required to read EDM4hep files but is not available; "
                "source the MAIA software environment first"
            ) from exc
        self._frames = Reader(path).get("events")

    def __iter__(self):
        if self._frames is None:
            return
        for frame in self._frames:
            yield _EDM4hepEvent(frame)

    def close(self) -> None:
        self._frames = None


def setup_reader(collection_names: Sequence[str], input_format: str = "lcio"):
    """Build the reader for the requested input format."""
    fmt = (input_format or "lcio").strip().lower()
    if fmt == "edm4hep":
        return EDM4hepReader(collection_names)
    if fmt == "lcio":
        return setup_lcio_reader(collection_names)
    raise ValueError(f"Unknown input format: {input_format}")


def resolve_file_glob(args) -> str:
    """
    Glob used when an input is a directory. Defaults to the right extension for
    the chosen format, so --file-glob only has to be given for unusual layouts.
    """
    explicit = getattr(args, "file_glob", None)
    if explicit:
        return explicit
    if getattr(args, "input_format", "lcio") == "edm4hep":
        return "*.edm4hep.root"
    return "*.slcio"


def setup_lcio_reader(collection_names: Sequence[str]):
    try:
        import pyLCIO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyLCIO is required but not available in this environment") from exc
    reader = pyLCIO.IOIMPL.LCFactory.getInstance().createLCReader()
    reader.setReadCollectionNames(list(collection_names))
    return reader


def mcp_eta(mcp) -> float:
    px, py, pz = _vec_xyz(mcp.getMomentum())
    p = math.sqrt(px * px + py * py + pz * pz)
    if p <= 0.0:
        return 999.0
    cos_theta = max(-1.0, min(1.0, pz / p))
    theta = math.acos(cos_theta)
    tan_half = math.tan(0.5 * theta)
    if tan_half <= 0:
        return 999.0
    return -math.log(tan_half)


def mcp_theta(mcp) -> float:
    px, py, pz = _vec_xyz(mcp.getMomentum())
    p = math.sqrt(px * px + py * py + pz * pz)
    if p <= 0.0:
        return 0.0
    cos_theta = max(-1.0, min(1.0, pz / p))
    return math.acos(cos_theta)


def find_single_primary(
    mcp_collection,
    pdg_ids: Sequence[int],
    eta_max: float,
    require_single: bool,
):
    matches = []
    for mcp in mcp_collection:
        if mcp.getGeneratorStatus() != 1:
            continue
        if abs(mcp.getPDG()) not in pdg_ids:
            continue
        eta = mcp_eta(mcp)
        if abs(eta) > eta_max:
            continue
        matches.append(mcp)
    if not matches:
        return None
    if require_single and len(matches) != 1:
        return None
    return max(matches, key=mcp_energy)


def sum_collection_energy(event, name: str) -> float:
    try:
        collection = event.getCollection(name)
    except Exception:
        return 0.0
    return sum(hit.getEnergy() for hit in collection)


def get_best_cluster(event, cluster_collection: str):
    try:
        collection = event.getCollection(cluster_collection)
    except Exception:
        return None
    if _coll_size(collection) <= 0:
        return None
    best = None
    best_energy = -1.0
    for cluster in collection:
        energy = float(cluster.getEnergy())
        if energy > best_energy:
            best_energy = energy
            best = cluster
    return best


def get_cluster_energy_split(cluster, ecal_index: int = 0, hcal_index: int = 1):
    """Return (total, ecal, hcal, has_split)."""
    total = float(cluster.getEnergy())
    values: List[float] = []
    if hasattr(cluster, "getSubdetectorEnergies"):
        sub = cluster.getSubdetectorEnergies()
        try:
            n = len(sub)
            values = [float(sub[i]) for i in range(n)]
        except Exception:
            try:
                values = [float(x) for x in sub]
            except Exception:
                values = []
    max_idx = max(ecal_index, hcal_index)
    has_split = len(values) > max_idx
    ecal = float(values[ecal_index]) if len(values) > ecal_index else 0.0
    hcal = float(values[hcal_index]) if len(values) > hcal_index else 0.0
    return total, ecal, hcal, has_split


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input files/directories/globs. Directories are expanded with --file-glob.",
    )
    parser.add_argument(
        "--input-format",
        choices=["lcio", "edm4hep"],
        default="lcio",
        help="Input file format. 'lcio' reads .slcio via pyLCIO; 'edm4hep' reads "
             ".edm4hep.root via podio, which is what the v3 reconstruction writes.",
    )
    parser.add_argument(
        "--file-glob",
        default=None,
        help="Glob used when an input is a directory. Defaults to *.slcio for "
             "--input-format lcio and *.edm4hep.root for --input-format edm4hep.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directory inputs using **/<file-glob>.",
    )
    parser.add_argument("--max-events", type=int, default=-1, help="Maximum events to process (-1 = all).")
    parser.add_argument("--eta-max", type=float, default=2.436, help="Truth particle acceptance cut.")
    parser.add_argument(
        "--require-single-primary",
        action="store_true",
        help="Require exactly one matching primary truth particle per event.",
    )
    parser.add_argument(
        "--theta-bins",
        required=True,
        help="Comma-separated theta bin edges in radians (e.g. 0,0.4,0.8,3.14159).",
    )
    parser.add_argument(
        "--energy-bins",
        required=True,
        help="Comma-separated energy bin edges in GeV.",
    )
    parser.add_argument("--min-bin-count", type=int, default=20, help="Minimum entries to calibrate a bin.")
    parser.add_argument(
        "--estimator",
        choices=["median", "mean", "trimmed_mean"],
        default="median",
        help="Per-bin estimator for correction factor.",
    )
    parser.add_argument(
        "--trim-fraction",
        type=float,
        default=0.1,
        help="Trim fraction on each side when estimator=trimmed_mean.",
    )


def build_table_from_ratios(
    domain: str,
    theta_edges: List[float],
    energy_edges: List[float],
    ratios_per_bin: List[List[float]],
    min_bin_count: int,
    estimator: str,
    trim_fraction: float,
    metadata: dict,
) -> CalibrationTable:
    n_theta = len(theta_edges) - 1
    n_energy = len(energy_edges) - 1
    expected = n_theta * n_energy
    if len(ratios_per_bin) != expected:
        raise ValueError("Internal error: ratio buffer size mismatch")

    scales: List[float] = []
    counts: List[int] = []
    for values in ratios_per_bin:
        counts.append(len(values))
        if len(values) < min_bin_count:
            scales.append(1.0)
        else:
            scales.append(robust_estimate(values, estimator, trim_fraction))

    table = CalibrationTable(
        domain=domain,
        theta_edges=theta_edges,
        energy_edges=energy_edges,
        scales=scales,
        counts=counts,
        metadata=metadata,
    )
    table.validate()
    return table
