#!/usr/bin/env python3
"""Produce HCAL theta-energy calibration table with ECAL correction fixed."""

from __future__ import annotations

import argparse
import time

from calibration_lib import (
    add_common_args,
    apply_ecal_calibration,
    build_table_from_ratios,
    expand_input_paths,
    find_bin,
    find_single_primary,
    flatten_index,
    get_best_cluster,
    get_cluster_energy_split,
    load_table_json,
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
    parser.add_argument("--pdg-ids", default="2112,211,111", help="Comma-separated PDG IDs for HCAL training.")
    parser.add_argument("--mc-collection", default="MCParticle")
    parser.add_argument("--energy-source", choices=["clusters", "hits"], default="clusters")
    parser.add_argument("--cluster-collection", default="PandoraClusters")
    parser.add_argument("--ecal-subdet-index", type=int, default=0)
    parser.add_argument("--hcal-subdet-index", type=int, default=1)
    parser.add_argument("--hcal-fraction-min", type=float, default=0.0)
    parser.add_argument("--skip-missing-subdet-split", action="store_true")
    parser.add_argument("--ecal-barrel-collection", default="ECalBarrelCollection")
    parser.add_argument("--ecal-endcap-collection", default="ECalEndcapCollection")
    parser.add_argument("--hcal-barrel-collection", default="HCalBarrelCollection")
    parser.add_argument("--hcal-endcap-collection", default="HCalEndcapCollection")
    parser.add_argument("--ecal-calibration", help="ECAL calibration JSON from pass A. Required for --energy-basis raw.")
    parser.add_argument(
        "--energy-basis",
        choices=["raw", "hadronic"],
        default="raw",
        help="Use 'hadronic' to train on the branch-summed Pandora hadronic energy basis.",
    )
    parser.add_argument(
        "--ecal-to-had-gev",
        type=float,
        default=1.0,
        help="Raw ECAL energy to Pandora HAD-branch scale factor used when --energy-basis hadronic.",
    )
    parser.add_argument(
        "--hcal-to-had-gev",
        type=float,
        default=1.0,
        help="Raw HCAL energy to Pandora HAD-branch scale factor used when --energy-basis hadronic.",
    )
    parser.add_argument(
        "--ecal-lookup-energy",
        choices=["measured"],
        default="measured",
        help="Energy argument used for ECAL table lookup.",
    )
    parser.add_argument(
        "--hcal-energy-axis",
        choices=["measured"],
        default="measured",
        help="Energy value used for HCAL theta-energy binning.",
    )
    parser.add_argument(
        "--negative-target-policy",
        choices=["skip", "clip0"],
        default="skip",
        help="How to handle E_target_hcal <= 0.",
    )
    parser.add_argument("--output", required=True, help="Output HCAL calibration JSON path.")
    args = parser.parse_args()

    theta_edges = parse_float_list(args.theta_bins)
    energy_edges = parse_float_list(args.energy_bins)
    pdg_ids = parse_int_list(args.pdg_ids)
    files = expand_input_paths(args.inputs, resolve_file_glob(args), recursive=args.recursive)
    if not files:
        raise RuntimeError("No input files found.")

    if args.energy_basis == "raw" and not args.ecal_calibration:
        raise RuntimeError("--ecal-calibration is required when --energy-basis raw.")
    ecal_table = load_table_json(args.ecal_calibration) if args.ecal_calibration else None
    n_theta = len(theta_edges) - 1
    n_energy = len(energy_edges) - 1
    ratios_per_bin = [[] for _ in range(n_theta * n_energy)]

    reader = setup_reader(
        [
            args.mc_collection,
            args.cluster_collection,
            args.ecal_barrel_collection,
            args.ecal_endcap_collection,
            args.hcal_barrel_collection,
            args.hcal_endcap_collection,
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
                total, ecal_e, hcal_e, has_split = get_cluster_energy_split(
                    cluster, ecal_index=args.ecal_subdet_index, hcal_index=args.hcal_subdet_index
                )
                if args.skip_missing_subdet_split and not has_split:
                    events_skipped_split += 1
                    continue
                hcal_fraction = (hcal_e / total) if total > 0.0 else 0.0
                if hcal_fraction < args.hcal_fraction_min:
                    events_skipped_fraction += 1
                    continue
                ecal_measured = ecal_e
                hcal_measured = hcal_e
            else:
                ecal_measured = (
                    sum_collection_energy(event, args.ecal_barrel_collection)
                    + sum_collection_energy(event, args.ecal_endcap_collection)
                )
                hcal_measured = (
                    sum_collection_energy(event, args.hcal_barrel_collection)
                    + sum_collection_energy(event, args.hcal_endcap_collection)
                )
            if hcal_measured <= 0.0:
                continue

            if args.energy_basis == "hadronic":
                measured_energy = ecal_measured * args.ecal_to_had_gev + hcal_measured * args.hcal_to_had_gev
                if measured_energy <= 0.0:
                    continue
                ratio = truth_e / measured_energy
                energy_axis_value = measured_energy
            else:
                ecal_corrected = apply_ecal_calibration(ecal_table, theta, ecal_measured)
                target_hcal = truth_e - ecal_corrected
                if target_hcal <= 0.0:
                    if args.negative_target_policy == "skip":
                        continue
                    target_hcal = 0.0
                if target_hcal <= 0.0:
                    continue

                ratio = target_hcal / hcal_measured
                energy_axis_value = hcal_measured

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
        domain="HADRONIC" if args.energy_basis == "hadronic" else "HCAL",
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
            "hcal_fraction_min": args.hcal_fraction_min,
            "skip_missing_subdet_split": bool(args.skip_missing_subdet_split),
            "ecal_collections": [args.ecal_barrel_collection, args.ecal_endcap_collection],
            "hcal_collections": [args.hcal_barrel_collection, args.hcal_endcap_collection],
            "ecal_calibration": args.ecal_calibration,
            "ecal_lookup_energy": "measured",
            "hcal_energy_axis": "measured",
            "energy_basis": args.energy_basis,
            "ecal_to_had_gev": args.ecal_to_had_gev,
            "hcal_to_had_gev": args.hcal_to_had_gev,
            "negative_target_policy": args.negative_target_policy,
            "runtime_sec": round(time.time() - t0, 3),
        },
    )
    save_table_json(table, args.output)
    print(f"Wrote HCAL calibration table: {args.output}")
    print(f"Events total/used: {events_total}/{events_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
