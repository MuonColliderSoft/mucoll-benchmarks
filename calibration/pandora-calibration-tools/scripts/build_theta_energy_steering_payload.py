#!/usr/bin/env python3
"""Build DDMarlinPandora steering payload from ECAL/HCAL calibration JSON tables."""

from __future__ import annotations

import argparse
import json

from calibration_lib import (
    build_hadronic_ddmarlin_params,
    build_photon_em_ddmarlin_params,
    combine_branch_ddmarlin_params,
    combine_ddmarlin_params,
    load_table_json,
)


def render_python_update_block(params: dict) -> str:
    lines = []
    lines.append("theta_energy_calibration_params = {")
    for key in sorted(params.keys()):
        values = ", ".join([f"\"{v}\"" for v in params[key]])
        lines.append(f"    \"{key}\": [{values}],")
    lines.append("}")
    lines.append("DDMarlinPandora.Parameters.update(theta_energy_calibration_params)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecal-calibration", help="ECAL calibration JSON.")
    parser.add_argument("--hcal-calibration", help="HCAL calibration JSON.")
    parser.add_argument("--photon-em-calibration", help="Photon EM calibration JSON.")
    parser.add_argument("--hadronic-calibration", help="Hadronic branch calibration JSON.")
    parser.add_argument("--plugin-name", default=None)
    parser.add_argument(
        "--branch",
        choices=["legacy", "hadronic", "electromagnetic"],
        default="legacy",
        help="Payload namespace to generate. 'legacy' preserves the historical hadronic-only key set.",
    )
    parser.add_argument("--output-json", help="Write merged DDMarlin parameter payload JSON.")
    parser.add_argument("--output-python", help="Write ready-to-paste python block for steer_reco.py.")
    args = parser.parse_args()

    if args.photon_em_calibration:
        if args.ecal_calibration or args.hcal_calibration or args.hadronic_calibration:
            raise RuntimeError("Use only one payload mode at a time.")
        plugin_name = args.plugin_name or "PhotonEMNonLinearity"
        params = build_photon_em_ddmarlin_params(load_table_json(args.photon_em_calibration), plugin_name=plugin_name)
    elif args.hadronic_calibration:
        if args.ecal_calibration or args.hcal_calibration:
            raise RuntimeError("Use only one payload mode at a time.")
        plugin_name = args.plugin_name or "HadronicThetaEnergyBinned"
        params = build_hadronic_ddmarlin_params(load_table_json(args.hadronic_calibration), plugin_name=plugin_name)
    else:
        if not args.ecal_calibration or not args.hcal_calibration:
            raise RuntimeError("ECAL+HCAL mode requires both --ecal-calibration and --hcal-calibration.")

        ecal = load_table_json(args.ecal_calibration)
        hcal = load_table_json(args.hcal_calibration)
        plugin_name = args.plugin_name or "ThetaEnergyBinned"
        if ecal.domain.upper() != "ECAL":
            raise RuntimeError(f"Expected ECAL domain table, got {ecal.domain}")
        if hcal.domain.upper() != "HCAL":
            raise RuntimeError(f"Expected HCAL domain table, got {hcal.domain}")

        if args.branch == "legacy":
            params = combine_ddmarlin_params(ecal, hcal, plugin_name=plugin_name)
        else:
            params = combine_branch_ddmarlin_params(ecal, hcal, branch=args.branch, plugin_name=plugin_name)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, sort_keys=True)
        print(f"Wrote JSON payload: {args.output_json}")

    py_block = render_python_update_block(params)
    if args.output_python:
        with open(args.output_python, "w", encoding="utf-8") as f:
            f.write(py_block)
        print(f"Wrote python payload block: {args.output_python}")
    else:
        print(py_block)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
