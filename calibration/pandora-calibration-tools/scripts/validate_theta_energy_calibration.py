#!/usr/bin/env python3
"""Validate ECAL/HCAL theta-energy calibration tables with closure summaries."""

from __future__ import annotations

import argparse
from array import array
import json
import os
import statistics
import time

from calibration_lib import (
    apply_ecal_calibration,
    apply_hadronic_calibration,
    expand_input_paths,
    find_single_primary,
    get_best_cluster,
    get_cluster_energy_split,
    load_table_json,
    mcp_theta,
    parse_int_list,
    setup_reader,
    mcp_energy,
    resolve_file_glob,
    sum_collection_energy,
)


def summarize(values):
    if not values:
        return {"n": 0, "mean": None, "median": None, "stdev": None}
    return {
        "n": len(values),
        "mean": sum(values) / float(len(values)),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values),
    }


def _make_root_hist2(name, title, x_edges, y_edges):
    import ROOT  # type: ignore

    return ROOT.TH2F(
        name,
        title,
        len(x_edges) - 1,
        array("d", x_edges),
        len(y_edges) - 1,
        array("d", y_edges),
    )


def _make_root_hist1(name, title, x_edges):
    import ROOT  # type: ignore

    return ROOT.TH1F(name, title, len(x_edges) - 1, array("d", x_edges))


def _plot_table(table, out_dir):
    import ROOT  # type: ignore

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    os.makedirs(out_dir, exist_ok=True)

    n_theta = len(table.theta_edges) - 1
    n_energy = len(table.energy_edges) - 1
    tag = table.domain.lower()

    h_scale = _make_root_hist2(
        f"{tag}_scale_map",
        f"{table.domain} calibration scale;theta [rad];energy [GeV]",
        table.theta_edges,
        table.energy_edges,
    )
    h_count = _make_root_hist2(
        f"{tag}_count_map",
        f"{table.domain} calibration bin counts;theta [rad];energy [GeV]",
        table.theta_edges,
        table.energy_edges,
    )

    h_theta_mean = _make_root_hist1(
        f"{tag}_theta_mean_scale",
        f"{table.domain} mean scale vs theta;theta [rad];scale",
        table.theta_edges,
    )
    h_theta_weighted = _make_root_hist1(
        f"{tag}_theta_weighted_scale",
        f"{table.domain} count-weighted scale vs theta;theta [rad];scale",
        table.theta_edges,
    )

    for i_theta in range(n_theta):
        weighted_sum = 0.0
        count_sum = 0.0
        mean_sum = 0.0
        for i_energy in range(n_energy):
            idx = i_theta * n_energy + i_energy
            scale = table.scales[idx]
            count = table.counts[idx]
            h_scale.SetBinContent(i_theta + 1, i_energy + 1, scale)
            h_count.SetBinContent(i_theta + 1, i_energy + 1, count)
            mean_sum += scale
            weighted_sum += scale * count
            count_sum += count
        h_theta_mean.SetBinContent(i_theta + 1, mean_sum / float(n_energy))
        if count_sum > 0:
            h_theta_weighted.SetBinContent(i_theta + 1, weighted_sum / count_sum)
        else:
            h_theta_weighted.SetBinContent(i_theta + 1, 1.0)

    root_path = os.path.join(out_dir, f"{tag}_calibration_plots.root")
    fout = ROOT.TFile(root_path, "RECREATE")
    for h in (h_scale, h_count, h_theta_mean, h_theta_weighted):
        h.Write()
    fout.Close()

    c1 = ROOT.TCanvas(f"c_{tag}_scale", "", 900, 700)
    c1.SetRightMargin(0.15)
    h_scale.Draw("COLZ")
    c1.SaveAs(os.path.join(out_dir, f"{tag}_scale_map.png"))

    c2 = ROOT.TCanvas(f"c_{tag}_count", "", 900, 700)
    c2.SetRightMargin(0.15)
    c2.SetLogz()
    h_count.Draw("COLZ")
    c2.SaveAs(os.path.join(out_dir, f"{tag}_count_map.png"))

    c3 = ROOT.TCanvas(f"c_{tag}_theta", "", 900, 700)
    h_theta_weighted.SetLineColor(ROOT.kBlue + 1)
    h_theta_weighted.SetLineWidth(3)
    h_theta_weighted.Draw("HIST")
    h_theta_mean.SetLineColor(ROOT.kRed + 1)
    h_theta_mean.SetLineWidth(2)
    h_theta_mean.SetLineStyle(2)
    h_theta_mean.Draw("HIST SAME")
    leg = ROOT.TLegend(0.58, 0.76, 0.89, 0.89)
    leg.AddEntry(h_theta_weighted, "weighted mean", "l")
    leg.AddEntry(h_theta_mean, "simple mean", "l")
    leg.Draw()
    c3.SaveAs(os.path.join(out_dir, f"{tag}_theta_profiles.png"))

    return {
        "root": root_path,
        "scale_map_png": os.path.join(out_dir, f"{tag}_scale_map.png"),
        "count_map_png": os.path.join(out_dir, f"{tag}_count_map.png"),
        "theta_profiles_png": os.path.join(out_dir, f"{tag}_theta_profiles.png"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", default=[], help="Fallback inputs used for both ECAL and HCAL validation.")
    parser.add_argument("--ecal-inputs", nargs="+", default=[], help="Inputs used for ECAL closure validation.")
    parser.add_argument("--hcal-inputs", nargs="+", default=[], help="Inputs used for HCAL and total closure validation.")
    parser.add_argument("--file-glob", default="*.slcio")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-events", type=int, default=-1)
    parser.add_argument("--eta-max", type=float, default=2.436)
    parser.add_argument("--require-single-primary", action="store_true")
    parser.add_argument("--mc-collection", default="MCParticle")
    parser.add_argument("--energy-source", choices=["clusters", "hits"], default="clusters")
    parser.add_argument("--cluster-collection", default="PandoraClusters")
    parser.add_argument("--ecal-subdet-index", type=int, default=0)
    parser.add_argument("--hcal-subdet-index", type=int, default=1)
    parser.add_argument("--skip-missing-subdet-split", action="store_true")
    parser.add_argument("--ecal-barrel-collection", default="ECalBarrelCollection")
    parser.add_argument("--ecal-endcap-collection", default="ECalEndcapCollection")
    parser.add_argument("--hcal-barrel-collection", default="HCalBarrelCollection")
    parser.add_argument("--hcal-endcap-collection", default="HCalEndcapCollection")
    parser.add_argument("--ecal-pdg-ids", default="22")
    parser.add_argument("--hcal-pdg-ids", default="2112,211,111")
    parser.add_argument("--ecal-calibration")
    parser.add_argument("--hcal-calibration")
    parser.add_argument("--hadronic-calibration")
    parser.add_argument("--output", required=True, help="Output JSON summary")
    parser.add_argument(
        "--plot-dir",
        default="",
        help="If set, write ECAL/HCAL calibration plots (.png + .root) to this directory.",
    )
    args = parser.parse_args()

    ecal_inputs = args.ecal_inputs if args.ecal_inputs else args.inputs
    hcal_inputs = args.hcal_inputs if args.hcal_inputs else args.inputs
    if not ecal_inputs and not hcal_inputs:
        raise RuntimeError("No input paths provided. Use --inputs or --ecal-inputs/--hcal-inputs.")

    ecal_files = expand_input_paths(ecal_inputs, resolve_file_glob(args), recursive=args.recursive)
    hcal_files = expand_input_paths(hcal_inputs, resolve_file_glob(args), recursive=args.recursive)
    if not ecal_files and args.ecal_calibration:
        raise RuntimeError("No ECAL input files found.")
    if not hcal_files:
        raise RuntimeError("No HCAL input files found.")

    if args.hadronic_calibration and (args.ecal_calibration or args.hcal_calibration):
        raise RuntimeError("Use either --hadronic-calibration or the ECAL+HCAL calibration pair, not both.")
    if not args.hadronic_calibration and (not args.ecal_calibration or not args.hcal_calibration):
        raise RuntimeError("Provide --hadronic-calibration or both --ecal-calibration and --hcal-calibration.")

    ecal_table = load_table_json(args.ecal_calibration) if args.ecal_calibration else None
    hcal_table = load_table_json(args.hcal_calibration) if args.hcal_calibration else None
    hadronic_table = load_table_json(args.hadronic_calibration) if args.hadronic_calibration else None
    ecal_pdgs = parse_int_list(args.ecal_pdg_ids)
    hcal_pdgs = parse_int_list(args.hcal_pdg_ids)

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

    events_total_ecal = 0
    events_total_hcal = 0
    ecal_closure = []
    hcal_closure = []
    total_closure = []
    hadronic_closure = []
    t0 = time.time()

    ecal_validation_files = ecal_files if ecal_table else []
    for fname in ecal_validation_files:
        reader.open(fname)
        for event in reader:
            if args.max_events > 0 and events_total_ecal >= args.max_events:
                break
            events_total_ecal += 1

            if args.energy_source == "clusters":
                cluster = get_best_cluster(event, args.cluster_collection)
                if cluster is None:
                    continue
                total, ecal_e, _hcal_e, has_split = get_cluster_energy_split(
                    cluster, ecal_index=args.ecal_subdet_index, hcal_index=args.hcal_subdet_index
                )
                if args.skip_missing_subdet_split and not has_split:
                    continue
                ecal_measured = ecal_e
            else:
                ecal_measured = (
                    sum_collection_energy(event, args.ecal_barrel_collection)
                    + sum_collection_energy(event, args.ecal_endcap_collection)
                )

            mcp_ecal = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=ecal_pdgs,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp_ecal is not None and ecal_measured > 0.0:
                truth_e = mcp_energy(mcp_ecal)
                theta = mcp_theta(mcp_ecal)
                ecal_corr = apply_ecal_calibration(ecal_table, theta, ecal_measured)
                if ecal_corr > 0.0:
                    ecal_closure.append(truth_e / ecal_corr)
        reader.close()
        if args.max_events > 0 and events_total_ecal >= args.max_events:
            break

    for fname in hcal_files:
        reader.open(fname)
        for event in reader:
            if args.max_events > 0 and events_total_hcal >= args.max_events:
                break
            events_total_hcal += 1

            if args.energy_source == "clusters":
                cluster = get_best_cluster(event, args.cluster_collection)
                if cluster is None:
                    continue
                _total, ecal_e, hcal_e, has_split = get_cluster_energy_split(
                    cluster, ecal_index=args.ecal_subdet_index, hcal_index=args.hcal_subdet_index
                )
                if args.skip_missing_subdet_split and not has_split:
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
            mcp_hcal = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=hcal_pdgs,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp_hcal is not None and hcal_measured > 0.0:
                truth_e = mcp_energy(mcp_hcal)
                theta = mcp_theta(mcp_hcal)
                if hadronic_table:
                    hadronic_corr = apply_hadronic_calibration(hadronic_table, theta, ecal_measured, hcal_measured)
                    if hadronic_corr > 0.0:
                        hadronic_closure.append(truth_e / hadronic_corr)
                else:
                    ecal_corr = apply_ecal_calibration(ecal_table, theta, ecal_measured)
                    target_hcal = truth_e - ecal_corr
                    if target_hcal > 0.0:
                        hcal_corr = hcal_table.lookup(theta, hcal_measured) * hcal_measured
                        if hcal_corr > 0.0:
                            hcal_closure.append(target_hcal / hcal_corr)
                    total_corr = ecal_corr + hcal_table.lookup(theta, hcal_measured) * hcal_measured
                    if total_corr > 0.0:
                        total_closure.append(truth_e / total_corr)
        reader.close()
        if args.max_events > 0 and events_total_hcal >= args.max_events:
            break

    summary = {
        "created_unix": int(time.time()),
        "runtime_sec": round(time.time() - t0, 3),
        "events_total_ecal": events_total_ecal,
        "events_total_hcal": events_total_hcal,
        "files_ecal": len(ecal_files),
        "files_hcal": len(hcal_files),
        "ecal_closure_truth_over_corrected": summarize(ecal_closure),
        "hcal_closure_target_over_corrected": summarize(hcal_closure),
        "total_closure_truth_over_corrected": summarize(total_closure),
        "hadronic_closure_truth_over_corrected": summarize(hadronic_closure),
        "inputs": {
            "ecal_inputs": ecal_inputs,
            "hcal_inputs": hcal_inputs,
            "ecal_calibration": args.ecal_calibration,
            "hcal_calibration": args.hcal_calibration,
            "hadronic_calibration": args.hadronic_calibration,
            "ecal_pdg_ids": ecal_pdgs,
            "hcal_pdg_ids": hcal_pdgs,
            "energy_source": args.energy_source,
            "cluster_collection": args.cluster_collection,
            "ecal_subdet_index": args.ecal_subdet_index,
            "hcal_subdet_index": args.hcal_subdet_index,
            "skip_missing_subdet_split": bool(args.skip_missing_subdet_split),
        },
    }

    if args.plot_dir and ecal_table and hcal_table:
        summary["plot_outputs"] = {
            "ecal": _plot_table(ecal_table, args.plot_dir),
            "hcal": _plot_table(hcal_table, args.plot_dir),
        }
    elif args.plot_dir and hadronic_table:
        summary["plot_outputs"] = {
            "hadronic": _plot_table(hadronic_table, args.plot_dir),
        }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"Wrote validation summary: {args.output}")
    print(json.dumps(summary["ecal_closure_truth_over_corrected"], indent=2))
    print(json.dumps(summary["hcal_closure_target_over_corrected"], indent=2))
    print(json.dumps(summary["hadronic_closure_truth_over_corrected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
