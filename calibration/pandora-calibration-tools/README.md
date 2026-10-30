# pandora-calibration-tools

Standalone tools for producing Pandora theta-energy calibration payloads and diagnostic plots for the MAIA reconstruction workflow.

There are two ways to apply these calibrations.

The Marlin/DDMarlinPandora path is documented below and uses `build_theta_energy_steering_payload.py` to convert the calibration tables into steering parameters.

The key4hep path reads the json tables directly. Instead of building a payload, point `ElectromagneticThetaEnergyCorrectionFile` and `HadronicThetaEnergyCorrectionFile` at the tables produced in steps 1 and 2. Everything up to and including step 3 is the same either way.

The key4hep path is still in review across three PRs:

- https://github.com/PandoraPFAOrg/LCContent/pull/41 — the correction plugins
- https://github.com/key4hep/k4GaudiPandora/pull/51 — reads the json tables
- https://github.com/MuonColliderSoft/MAIAConfig/pull/37 — the tables and Pandora settings

This section will be updated once those are merged.


The current workflow targets the `v2.11` MAIA setup and the calibration branches in:

- `trholmes/LCContent`: `codex/photon-em-nonlinearity`
- `trholmes/DDMarlinPandora`: `codex/photon-em-theta-energy`
- `trholmes/SteeringMacros`: `codex/photon-em-steering`
- `trholmes/pandora-calibration-tools`: `codex/photon-em-payload`

The logical workflow is:

1. Use reconstructed single-particle samples to create calibration factors with this repository.
2. Use the matching runtime branches above to apply those calibrations during reconstruction.
3. Use switches in `PandoraSettingsDefault.xml` to control whether corrected energies are used in selected internal decisions, such as ConeBasedMerging track comparisons and `LCElectronId` E/p.
4. Final output cluster energies are calibrated when the corresponding payloads are supplied to `steer_reco.py`.

Default training inputs are cluster-based `PandoraClusters` from reco `.slcio` files. The scripts use `cluster.getSubdetectorEnergies()` with:

- ECAL subdetector index: `0`
- HCAL subdetector index: `1`

Examples below use one consistent EM sample and one consistent hadronic sample:

- EM/photon sample: `photonGun_E_0_50`
- hadronic sample: `neutronGun_E_0_50`

## What This Workflow Covers

This repository provides the scripts and documentation for:

1. Photon/ECAL EM theta-energy calibration.
2. Branch-summed hadronic theta-energy calibration using ECAL+HCAL on the Pandora HAD scale.
3. DDMarlinPandora steering payload generation.
4. Closure and shower-profile diagnostic plots.

The matching runtime code lives in the companion branches listed above. In particular:

- `LCContent` implements the theta-energy nonlinearity plugin and configurable corrected-energy use in selected comparisons.
- `DDMarlinPandora` exposes calibration payload parameters and registers the plugins.
- `SteeringMacros` enables the plugin names in Pandora XML and loads payload JSON files from `steer_reco.py`.

## Repository Contents

- `scripts/make_ecal_theta_energy_calibration.py`: build photon/ECAL EM calibration tables.
- `scripts/make_hcal_theta_energy_calibration.py`: build hadronic calibration tables.
- `scripts/validate_theta_energy_calibration.py`: closure plots and summaries.
- `scripts/build_theta_energy_steering_payload.py`: convert calibration tables to `DDMarlinPandora.Parameters` payloads.
- `scripts/plot_shower_profile_diagnostics.py`: plot `showerProfileStart` and `showerProfileDiscrepancy` diagnostics.
- `scripts/calibration_lib.py`: shared utilities.
- `config/example_ecal_calibration_config.txt`: example ECAL command config.
- `config/example_hcal_calibration_config.txt`: example hadronic command config.
- `docs/theta_energy_cluster_calibration_spec.md`: implementation/spec notes.

## Runtime Requirements

- MAIA `v2.11` software environment.
- Python 3.8+.
- `pyLCIO` for calibration-table production.
- `matplotlib` for `plot_shower_profile_diagnostics.py`.
- `.slcio` reco inputs for `photonGun_E_0_50` and `neutronGun_E_0_50`.
- Writable output directory, normally `calib/`.

## Set Up From Scratch

Use this for a clean checkout in a new `v2.11` area.

```bash
export MUCOL_BASE=/scratch/trholmes/mucol/v2.11
mkdir -p "${MUCOL_BASE}"
cd "${MUCOL_BASE}"
```

Clone the repositories:

```bash
git clone git@github.com:PandoraPFA/LCContent.git
git clone git@github.com:MuonColliderSoft/DDMarlinPandora.git
git clone https://github.com/madbaron/SteeringMacros.git
git clone git@github.com:trholmes/pandora-calibration-tools.git
```

Add the fork remotes and check out the working branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git remote add trholmes git@github.com:trholmes/LCContent.git
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git remote add trholmes git@github.com:trholmes/DDMarlinPandora.git
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git remote add trholmes git@github.com:trholmes/SteeringMacros.git
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering

cd "${MUCOL_BASE}/pandora-calibration-tools"
git fetch origin codex/photon-em-payload
git checkout codex/photon-em-payload
```

Build and install local `LCContent`:

```bash
cd "${MUCOL_BASE}/LCContent"
rm -rf build install
mkdir -p build install
cd build
cmake .. -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/LCContent/install"
cmake --build . -j"$(nproc)"
cmake --install .
```

Build and install local `DDMarlinPandora` against that `LCContent`:

```bash
cd "${MUCOL_BASE}/DDMarlinPandora"
rm -rf build install
mkdir -p build install
cd build
cmake .. \
  -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/DDMarlinPandora/install" \
  -DLCContent_DIR="${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent"
cmake --build . -j"$(nproc)"
cmake --install .
```

Point runtime to the local builds before running `k4run`:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

Check that the local runtime is active:

```bash
echo "${LD_LIBRARY_PATH}" | tr ':' '\n' | head -n 5
echo "${MARLIN_DLL}" | tr ':' '\n' | head -n 10
```

## Set Up Upon Return

Use this when coming back to an existing `v2.11` checkout.

```bash
export MUCOL_BASE=/scratch/trholmes/mucol/v2.11
```

Update the branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity
git pull --ff-only trholmes codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy
git pull --ff-only trholmes codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering
git pull --ff-only trholmes codex/photon-em-steering

cd "${MUCOL_BASE}/pandora-calibration-tools"
git fetch origin codex/photon-em-payload
git checkout codex/photon-em-payload
git pull --ff-only origin codex/photon-em-payload
```

Rebuild after `LCContent` or `DDMarlinPandora` changes:

```bash
cd "${MUCOL_BASE}/LCContent/build"
cmake --build . -j"$(nproc)"
cmake --install .

cd "${MUCOL_BASE}/DDMarlinPandora/build"
cmake --build . -j"$(nproc)"
cmake --install .
```

Re-export the local runtime libraries in each new shell:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

## Calibration Inputs And Conventions

The calibration scripts train on reconstructed clusters and compare to the matched generated particle energy.

The EM/photon table is trained in the Pandora EM energy basis:

```text
E_em_basis = raw_ecal_subdetector_energy * ECalToEMGeVCalibration
```

The first-pass hadronic table is trained in a branch-summed Pandora HAD energy basis:

```text
E_had_basis = raw_ecal_subdetector_energy * ECalToHadGeVCalibration
            + raw_hcal_subdetector_energy * HCalToHadGeVCalibration
```

This is why the examples below explicitly pass the flat ECAL/HCAL calibration constants. They make the table training basis match the basis where the Pandora runtime correction is applied.

The values passed to the calibration scripts must match the values used by `SteeringMacros/k4Reco/steer_reco.py` for the reconstruction that produced the input clusters and for the reconstruction where the payload will be applied. For the current `v2.11` steering, the relevant values are:

| Steering parameter | Current value | Calibration-script argument |
| --- | --- | --- |
| `ECalToEMGeVCalibration` | `1.02373335516` | `--ecal-to-em-gev 1.02373335516` |
| `ECalToHadGeVCalibrationBarrel` | `1.38` | `--ecal-to-had-gev 1.38` |
| `ECalToHadGeVCalibrationEndCap` | `1.38` | `--ecal-to-had-gev 1.38` |
| `HCalToHadGeVCalibration` | `1.25` | `--hcal-to-had-gev 1.25` |

Do not treat these as universal detector constants. If `steer_reco.py` changes, update the calibration commands and regenerate the payloads. A mismatch double-counts or under-counts a flat scale factor: the table is trained in one energy basis, while Pandora applies it in another.

The current hadronic script uses one ECAL-to-HAD value for both barrel and endcap, so the barrel and endcap values in steering should be identical for this workflow. If they are changed independently later, the calibration script or sample splitting should be updated before producing new hadronic payloads.

## End-To-End Calibration Workflow

Prepare output directories:

```bash
cd "${MUCOL_BASE}/pandora-calibration-tools"
mkdir -p calib calib/plots
```

### 1. Build The Photon/ECAL EM Table

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-fraction-min 0.7 \
  --energy-basis em \
  --ecal-to-em-gev 1.02373335516 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

### 2. Build The Hadronic Branch Table

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hcal-fraction-min 0.1 \
  --energy-basis hadronic \
  --ecal-to-had-gev 1.38 \
  --hcal-to-had-gev 1.25 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 2112,211,111 \
  --output calib/hadronic_theta_energy_calib.json
```

### 3. Validate Closure

Validate the photon/ECAL table:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --ecal-inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/ecal_closure_summary.json
```

Validate the first-pass hadronic branch table:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --hcal-inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/hadronic_closure_summary.json
```

The validation scripts write quick-look maps and theta profiles to `calib/plots`.

### 4. Build Steering Payloads

Build the photon EM runtime payload:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --photon-em-calibration calib/ecal_theta_energy_calib.json \
  --output-json calib/photon_em_calib_payload.json
```

Build the hadronic runtime payload:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --output-json calib/hadronic_calib_payload.json
```

## Run Reconstruction With Payloads

Photon EM test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --photonEMCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/photon_em_calib_payload.json"
```

Hadronic branch test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent neutronGun_E_0_50 \
  --InFileName 0 \
  --hadronicCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_calib_payload.json"
```

Combined photon/hadronic payload test:

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --photonEMCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/photon_em_calib_payload.json" \
  --hadronicCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_calib_payload.json"
```

## Payloads And Runtime Switches

There are two separate runtime controls:

1. Payload arguments to `steer_reco.py` load calibration tables into the Pandora correction plugins.
2. XML switches in `SteeringMacros/PandoraSettings/PandoraSettingsDefault.xml` decide whether selected internal comparisons use corrected energies instead of the nominal cluster energies.

Loading a payload changes the corrected-energy value returned by Pandora. It does not automatically make every internal algorithm use that corrected energy. The XML switches below opt specific decisions into using corrected energies.

If a switch is turned on without the matching payload, the correction plugin is still registered but has an empty correction table. In that case `GetCorrectedElectromagneticEnergy(...)` and `GetCorrectedHadronicEnergy(...)` fall back to the nominal calibrated cluster energy. This should be safe and effectively identity-like. If the runtime branches are not built or the plugin names in XML are missing from the loaded `LCContent`, Pandora can still fail at initialization.

### Payload Arguments

```bash
--photonEMCalibPayload calib/photon_em_calib_payload.json
```

Loads the EM theta-energy table and enables the `PhotonEMNonLinearity` electromagnetic correction plugin. This affects corrected EM energies and final photon/EM energy assignment, and it is used by internal comparisons only where an EM corrected-energy switch is enabled.

```bash
--hadronicCalibPayload calib/hadronic_calib_payload.json
```

Loads the hadronic theta-energy table and enables the `HadronicThetaEnergyBinned` hadronic correction plugin. This affects corrected HAD energies and final hadronic energy assignment, and it is used by internal comparisons only where a HAD corrected-energy switch is enabled.

### XML Switches

All switches default to `false` in the steering. Set only the specific comparisons you want to test to `true`.

| XML location | Switch | Effect when `true` |
| --- | --- | --- |
| `ProximityBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The proximity-merging track-cluster chi checks use corrected parent and merged-candidate hadronic energies. |
| `ConeBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The cone-merging track-cluster chi checks use corrected parent and merged-candidate hadronic energies. |
| nested `TrackClusterAssociation` inside `ProximityBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| nested `TrackClusterAssociation` inside `ConeBasedMerging` | `UseCorrectedHadronicEnergyForTrackComparison` | The association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| `TrackPreparation/trackClusterAssociationAlgorithms/TrackClusterAssociation` | `UseCorrectedHadronicEnergyForTrackComparison` | The final track-cluster association energy tie-break uses corrected hadronic energy. Distance remains the primary comparison. |
| `LCElectronId` | `UseCorrectedElectromagneticEnergyForEOverP` | The electron-ID E/p comparison uses corrected electromagnetic energy. Fast profile and preselection cuts remain unchanged. |

The hadronic switch name is reused in different XML scopes. For example, this turns on the `TrackClusterAssociation` tie-break inside `ConeBasedMerging`, not the `ConeBasedMerging` chi checks:

```xml
<algorithm type = "ConeBasedMerging">
    <algorithm type = "TrackClusterAssociation">
        <UseCorrectedHadronicEnergyForTrackComparison>true</UseCorrectedHadronicEnergyForTrackComparison>
    </algorithm>
    <UseCorrectedHadronicEnergyForTrackComparison>false</UseCorrectedHadronicEnergyForTrackComparison>
</algorithm>
```

This turns on the `ConeBasedMerging` chi checks, not the nested association tie-break:

```xml
<algorithm type = "ConeBasedMerging">
    <algorithm type = "TrackClusterAssociation">
        <UseCorrectedHadronicEnergyForTrackComparison>false</UseCorrectedHadronicEnergyForTrackComparison>
    </algorithm>
    <UseCorrectedHadronicEnergyForTrackComparison>true</UseCorrectedHadronicEnergyForTrackComparison>
</algorithm>
```

## Shower-Profile Diagnostics

`scripts/plot_shower_profile_diagnostics.py` plots `showerProfileStart` and `showerProfileDiscrepancy` with the current `LCElectronId` cuts overlaid:

```bash
python3 scripts/plot_shower_profile_diagnostics.py reco.log \
  --format dump-pfos-log \
  --output-dir calib/shower_profile_diagnostics
```

This log-parsing mode reads neutral PFO rows printed by `DumpPfosMonitoringAlgorithm`, where the columns are labelled `sStart` and `sDisc`. Charged PFO rows do not currently print these quantities. For electron-specific studies, either add those columns to the monitoring output or provide a CSV with columns:

```text
energy,sStart,sDisc,theta,label
```

`theta` and `label` are optional. The script writes:

- `shower_profile_vs_energy.png`
- `shower_profile_distributions.png`
- `shower_profile_vs_theta.png` when `theta` is present
- `shower_profile_summary.txt`

## Troubleshooting

1. `ImportError: pyLCIO`
   Source the MAIA software environment before running the calibration scripts.

2. `No input files found`
   Check the sample path and add `--recursive` if files are in nested directories.

3. `LCContent_DIR` not found
   Check that `${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent` exists after installing `LCContent`.

4. Local changes do not appear in the `k4run` log
   Re-export `LD_LIBRARY_PATH` and `MARLIN_DLL`, then check that `MARLIN_DLL` points at `${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so`.

5. Too many calibration bins have scale `1.0`
   Increase statistics, reduce bin granularity, or lower the minimum-bin threshold.

6. Cluster subdetector split is unavailable
   Remove `--skip-missing-subdet-split` to make the script fail loudly, or temporarily switch to hit-based energy inputs for debugging.
