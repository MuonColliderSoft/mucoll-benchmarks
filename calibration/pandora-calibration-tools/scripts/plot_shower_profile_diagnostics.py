#!/usr/bin/env python3
"""Plot shower-profile start/discrepancy diagnostics with LCContent cuts."""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass
class ShowerProfileEntry:
    energy: float
    shower_start: float
    shower_discrepancy: float
    theta: Optional[float] = None
    label: str = ""


def _as_float(value: str) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def read_csv_entries(path: str) -> List[ShowerProfileEntry]:
    entries: List[ShowerProfileEntry] = []
    with open(path, newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)
        if reader.fieldnames is None:
            return entries

        lower_to_name = {name.lower(): name for name in reader.fieldnames}
        energy_key = next((lower_to_name[k] for k in ("energy", "eclust", "cluster_energy") if k in lower_to_name), None)
        start_key = next((lower_to_name[k] for k in ("sstart", "shower_start", "profile_start") if k in lower_to_name), None)
        disc_key = next(
            (lower_to_name[k] for k in ("sdisc", "shower_discrepancy", "profile_discrepancy") if k in lower_to_name), None
        )
        theta_key = next((lower_to_name[k] for k in ("theta", "mcp_theta", "cluster_theta") if k in lower_to_name), None)
        label_key = next((lower_to_name[k] for k in ("label", "sample", "pdg", "particle") if k in lower_to_name), None)

        if energy_key is None or start_key is None or disc_key is None:
            raise ValueError(
                f"{path} must contain energy/eclust, sStart/shower_start, and sDisc/shower_discrepancy columns"
            )

        for row in reader:
            energy = _as_float(row.get(energy_key, ""))
            shower_start = _as_float(row.get(start_key, ""))
            shower_discrepancy = _as_float(row.get(disc_key, ""))
            if energy is None or shower_start is None or shower_discrepancy is None:
                continue
            if shower_start < 0.0 or shower_discrepancy < 0.0:
                continue

            theta = _as_float(row.get(theta_key, "")) if theta_key else None
            label = row.get(label_key, "") if label_key else ""
            entries.append(ShowerProfileEntry(energy, shower_start, shower_discrepancy, theta, label))

    return entries


def read_dump_pfos_log_entries(path: str) -> List[ShowerProfileEntry]:
    """Parse neutral PFO rows printed by LCContent DumpPfosMonitoringAlgorithm.

    The neutral rows contain, from the end of the whitespace-tokenized line:
    Eclust tclust fC fP fN inner - outer sStart sDisc
    optionally preceded by PFO id and PFO energy.
    """
    entries: List[ShowerProfileEntry] = []
    numeric_or_dash = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$|^-$")

    with open(path, encoding="utf-8", errors="replace") as fin:
        for line in fin:
            tokens = line.split()
            if len(tokens) < 10 or "-" not in tokens:
                continue
            if not all(numeric_or_dash.match(token) for token in tokens[-10:]):
                continue

            energy = _as_float(tokens[-10])
            shower_start = _as_float(tokens[-2])
            shower_discrepancy = _as_float(tokens[-1])
            if energy is None or shower_start is None or shower_discrepancy is None:
                continue
            if shower_start < 0.0 or shower_discrepancy < 0.0:
                continue

            entries.append(ShowerProfileEntry(energy, shower_start, shower_discrepancy, label="dump_pfos_neutral"))

    return entries


def read_entries(paths: Iterable[str], fmt: str) -> List[ShowerProfileEntry]:
    entries: List[ShowerProfileEntry] = []
    for path in paths:
        if fmt == "csv":
            entries.extend(read_csv_entries(path))
        elif fmt == "dump-pfos-log":
            entries.extend(read_dump_pfos_log_entries(path))
        else:
            if path.lower().endswith(".csv"):
                entries.extend(read_csv_entries(path))
            else:
                entries.extend(read_dump_pfos_log_entries(path))
    return entries


def group_entries(entries: List[ShowerProfileEntry]) -> Dict[str, List[ShowerProfileEntry]]:
    groups: Dict[str, List[ShowerProfileEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.label or "all", []).append(entry)
    return groups


def finite_range(values: List[float], fallback: tuple[float, float]) -> tuple[float, float]:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return fallback
    low, high = min(values), max(values)
    if low == high:
        return low - 0.5, high + 0.5
    return low, high


def plot_diagnostics(entries: List[ShowerProfileEntry], out_dir: str, args: argparse.Namespace) -> None:
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    groups = group_entries(entries)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for label, group in groups.items():
        energies = [entry.energy for entry in group]
        starts = [entry.shower_start for entry in group]
        discrepancies = [entry.shower_discrepancy for entry in group]
        axes[0].scatter(energies, starts, s=args.marker_size, alpha=args.alpha, label=label)
        axes[1].scatter(energies, discrepancies, s=args.marker_size, alpha=args.alpha, label=label)

    axes[0].axhline(args.max_profile_start, color="crimson", linestyle="--", linewidth=2, label="MaxProfileStart")
    axes[1].axhline(args.max_profile_discrepancy, color="crimson", linestyle="--", linewidth=2, label="MaxProfileDiscrepancy")
    axes[1].axhline(
        args.profile_discrepancy_for_auto_id,
        color="darkorange",
        linestyle=":",
        linewidth=2,
        label="ProfileDiscrepancyForAutoId",
    )

    for axis in axes:
        axis.set_xscale("log")
        axis.set_xlabel("cluster energy [GeV]")
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize="small")
    axes[0].set_ylabel("shower profile start [X0]")
    axes[1].set_ylabel("shower profile discrepancy")
    fig.savefig(os.path.join(out_dir, "shower_profile_vs_energy.png"), dpi=args.dpi)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    starts = [entry.shower_start for entry in entries]
    discrepancies = [entry.shower_discrepancy for entry in entries]
    axes[0].hist(starts, bins=args.bins, histtype="stepfilled", alpha=0.65)
    axes[1].hist(discrepancies, bins=args.bins, histtype="stepfilled", alpha=0.65)
    axes[0].axvline(args.max_profile_start, color="crimson", linestyle="--", linewidth=2, label="MaxProfileStart")
    axes[1].axvline(args.max_profile_discrepancy, color="crimson", linestyle="--", linewidth=2, label="MaxProfileDiscrepancy")
    axes[1].axvline(
        args.profile_discrepancy_for_auto_id,
        color="darkorange",
        linestyle=":",
        linewidth=2,
        label="ProfileDiscrepancyForAutoId",
    )
    axes[0].set_xlabel("shower profile start [X0]")
    axes[1].set_xlabel("shower profile discrepancy")
    for axis in axes:
        axis.set_ylabel("entries")
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize="small")
    fig.savefig(os.path.join(out_dir, "shower_profile_distributions.png"), dpi=args.dpi)
    plt.close(fig)

    entries_with_theta = [entry for entry in entries if entry.theta is not None]
    if entries_with_theta:
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
        for label, group in group_entries(entries_with_theta).items():
            theta = [entry.theta for entry in group if entry.theta is not None]
            starts_group = [entry.shower_start for entry in group if entry.theta is not None]
            disc_group = [entry.shower_discrepancy for entry in group if entry.theta is not None]
            axes[0].scatter(theta, starts_group, s=args.marker_size, alpha=args.alpha, label=label)
            axes[1].scatter(theta, disc_group, s=args.marker_size, alpha=args.alpha, label=label)
        axes[0].axhline(args.max_profile_start, color="crimson", linestyle="--", linewidth=2, label="MaxProfileStart")
        axes[1].axhline(args.max_profile_discrepancy, color="crimson", linestyle="--", linewidth=2, label="MaxProfileDiscrepancy")
        axes[1].axhline(
            args.profile_discrepancy_for_auto_id,
            color="darkorange",
            linestyle=":",
            linewidth=2,
            label="ProfileDiscrepancyForAutoId",
        )
        for axis in axes:
            axis.set_xlabel("theta [rad]")
            axis.grid(True, alpha=0.3)
            axis.legend(fontsize="small")
        axes[0].set_ylabel("shower profile start [X0]")
        axes[1].set_ylabel("shower profile discrepancy")
        fig.savefig(os.path.join(out_dir, "shower_profile_vs_theta.png"), dpi=args.dpi)
        plt.close(fig)


def write_summary(entries: List[ShowerProfileEntry], out_dir: str, args: argparse.Namespace) -> None:
    n_total = len(entries)
    n_start_pass = sum(entry.shower_start <= args.max_profile_start for entry in entries)
    n_disc_pass = sum(entry.shower_discrepancy <= args.max_profile_discrepancy for entry in entries)
    n_both_pass = sum(
        entry.shower_start <= args.max_profile_start and entry.shower_discrepancy <= args.max_profile_discrepancy
        for entry in entries
    )
    n_auto = sum(entry.shower_discrepancy < args.profile_discrepancy_for_auto_id for entry in entries)

    with open(os.path.join(out_dir, "shower_profile_summary.txt"), "w", encoding="utf-8") as fout:
        fout.write(f"entries: {n_total}\n")
        fout.write(f"MaxProfileStart: {args.max_profile_start}\n")
        fout.write(f"MaxProfileDiscrepancy: {args.max_profile_discrepancy}\n")
        fout.write(f"ProfileDiscrepancyForAutoId: {args.profile_discrepancy_for_auto_id}\n")
        if n_total:
            fout.write(f"pass_start: {n_start_pass} ({n_start_pass / n_total:.6f})\n")
            fout.write(f"pass_discrepancy: {n_disc_pass} ({n_disc_pass / n_total:.6f})\n")
            fout.write(f"pass_both: {n_both_pass} ({n_both_pass / n_total:.6f})\n")
            fout.write(f"auto_id_discrepancy: {n_auto} ({n_auto / n_total:.6f})\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plot shower profile start/discrepancy diagnostics. Inputs can be Pandora DumpPfosMonitoringAlgorithm "
            "logs or CSV files with energy/eclust, sStart/shower_start, and sDisc/shower_discrepancy columns."
        )
    )
    parser.add_argument("inputs", nargs="+", help="Input log or CSV files.")
    parser.add_argument("--format", choices=("auto", "csv", "dump-pfos-log"), default="auto", help="Input format.")
    parser.add_argument("--output-dir", default="shower_profile_diagnostics", help="Directory for output plots.")
    parser.add_argument("--max-profile-start", type=float, default=4.5, help="LCElectronId MaxProfileStart cut.")
    parser.add_argument("--max-profile-discrepancy", type=float, default=0.6, help="LCElectronId MaxProfileDiscrepancy cut.")
    parser.add_argument(
        "--profile-discrepancy-for-auto-id",
        type=float,
        default=0.5,
        help="LCElectronId ProfileDiscrepancyForAutoId threshold.",
    )
    parser.add_argument("--bins", type=int, default=80, help="Histogram bins.")
    parser.add_argument("--marker-size", type=float, default=4.0, help="Scatter marker size.")
    parser.add_argument("--alpha", type=float, default=0.35, help="Scatter marker opacity.")
    parser.add_argument("--dpi", type=int, default=160, help="Output image DPI.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    entries = read_entries(args.inputs, args.format)
    if not entries:
        raise RuntimeError("No shower-profile entries found in inputs.")

    plot_diagnostics(entries, args.output_dir, args)
    write_summary(entries, args.output_dir, args)
    print(f"Wrote {len(entries)} entries to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
