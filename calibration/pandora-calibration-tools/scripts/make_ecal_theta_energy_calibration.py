#!/usr/bin/env python3
"""Produce ECAL theta-energy calibration table from single-particle samples."""

from __future__ import annotations

import argparse
import time

from calibration_lib import (
    add_common_args,
    build_table_from_ratios,
    expand_input_paths,
    find_bin,
    find_single_primary,
    flatten_index,
    get_best_cluster,
    get_cluster_energy_split,
    mcp_theta,
    parse_float_list,
    parse_int_list,
    save_table_json,
    setup_reader,
    mcp_energy,
    resolve_file_glob,
    sum_collection_energy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--pdg-ids", default="22", help="Comma-separated PDG IDs to use as truth primary (default: 22).")
    parser.add_argument("--mc-collection", default="MCParticle")
    parser.add_argument("--energy-source", choices=["clusters", "hits"], default="clusters")
    parser.add_argument("--cluster-collection", default="PandoraClusters")
    parser.add_argument("--ecal-subdet-index", type=int, default=0)
    parser.add_argument("--hcal-subdet-index", type=int, default=1)
    parser.add_argument("--ecal-fraction-min", type=float, default=0.0)
    parser.add_argument("--skip-missing-subdet-split", action="store_true")
    parser.add_argument("--ecal-barrel-collection", default="ECalBarrelCollection")
    parser.add_argument("--ecal-endcap-collection", default="ECalEndcapCollection")
    parser.add_argument(
        "--energy-basis",
        choices=["raw", "em"],
        default="raw",
        help="Energy basis used for ratios and energy-axis binning. Use 'em' for Pandora EM-branch calibration.",
    )
    parser.add_argument(
        "--ecal-to-em-gev",
        type=float,
        default=1.0,
        help="Raw ECAL energy to Pandora EM-branch scale factor used when --energy-basis em.",
    )
    parser.add_argument(
        "--energy-axis",
        choices=["measured"],
        default="measured",
        help="Choose binning energy axis value.",
    )
    parser.add_argument("--output", required=True, help="Output calibration JSON path.")
    args = parser.parse_args()

    theta_edges = parse_float_list(args.theta_bins)
    energy_edges = parse_float_list(args.energy_bins)
    pdg_ids = parse_int_list(args.pdg_ids)
    files = expand_input_paths(args.inputs, resolve_file_glob(args), recursive=args.recursive)
    if not files:
        raise RuntimeError("No input files found.")

    n_theta = len(theta_edges) - 1
    n_energy = len(energy_edges) - 1
    ratios_per_bin = [[] for _ in range(n_theta * n_energy)]

    reader = setup_reader(
        [
            args.mc_collection,
            args.cluster_collection,
            args.ecal_barrel_collection,
            args.ecal_endcap_collection,
        ],
        input_format=args.input_format
    )
    events_total = 0
    events_used = 0
    events_skipped_split = 0
    events_skipped_fraction = 0
    t0 = time.time()

    for fname in files:
        reader.open(fname)
        for event in reader:
            if args.max_events > 0 and events_total >= args.max_events:
                break
            events_total += 1

            mcp = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=pdg_ids,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp is None:
                continue

            truth_e = mcp_energy(mcp)
            theta = mcp_theta(mcp)
            if args.energy_source == "clusters":
                cluster = get_best_cluster(event, args.cluster_collection)
                if cluster is None:
                    continue
                total, raw_ecal_energy, hcal_e, has_split = get_cluster_energy_split(
                    cluster, ecal_index=args.ecal_subdet_index, hcal_index=args.hcal_subdet_index
                )
                if args.skip_missing_subdet_split and not has_split:
                    events_skipped_split += 1
                    continue
                ecal_fraction = (raw_ecal_energy / total) if total > 0.0 else 0.0
                if ecal_fraction < args.ecal_fraction_min:
                    events_skipped_fraction += 1
                    continue
            else:
                raw_ecal_energy = (
                    sum_collection_energy(event, args.ecal_barrel_collection)
                    + sum_collection_energy(event, args.ecal_endcap_collection)
                )

            if raw_ecal_energy <= 0.0:
                continue

            ecal_measured = raw_ecal_energy
            if args.energy_basis == "em":
                ecal_measured *= args.ecal_to_em_gev

            if ecal_measured <= 0.0:
                continue

            ratio = truth_e / ecal_measured
            energy_axis_value = ecal_measured
            i_theta = find_bin(theta_edges, theta)
            i_energy = find_bin(energy_edges, energy_axis_value)
            if i_theta < 0 or i_energy < 0:
                continue
            ratios_per_bin[flatten_index(i_theta, i_energy, n_energy)].append(ratio)
            events_used += 1
        reader.close()
        if args.max_events > 0 and events_total >= args.max_events:
            break

    table = build_table_from_ratios(
        domain="ECAL",
        theta_edges=theta_edges,
        energy_edges=energy_edges,
        ratios_per_bin=ratios_per_bin,
        min_bin_count=args.min_bin_count,
        estimator=args.estimator,
        trim_fraction=args.trim_fraction,
        metadata={
            "created_unix": int(time.time()),
            "files": len(files),
            "events_total": events_total,
            "events_used": events_used,
            "events_skipped_split": events_skipped_split,
            "events_skipped_fraction": events_skipped_fraction,
            "pdg_ids": pdg_ids,
            "mc_collection": args.mc_collection,
            "energy_source": args.energy_source,
            "cluster_collection": args.cluster_collection,
            "ecal_subdet_index": args.ecal_subdet_index,
            "hcal_subdet_index": args.hcal_subdet_index,
            "ecal_fraction_min": args.ecal_fraction_min,
            "skip_missing_subdet_split": bool(args.skip_missing_subdet_split),
            "ecal_collections": [args.ecal_barrel_collection, args.ecal_endcap_collection],
            "energy_axis": "measured",
            "energy_basis": args.energy_basis,
            "ecal_to_em_gev": args.ecal_to_em_gev,
            "runtime_sec": round(time.time() - t0, 3),
        },
    )
    save_table_json(table, args.output)
    print(f"Wrote ECAL calibration table: {args.output}")
    print(f"Events total/used: {events_total}/{events_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
