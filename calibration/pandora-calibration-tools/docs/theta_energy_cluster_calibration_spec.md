# Theta-Energy Cluster Calibration Spec (Mid-Pandora)

Note: this document was originally drafted in a multi-repo workspace. Some file links point to absolute local paths from that environment; use the referenced filenames/components as canonical targets.

## Objective

Implement **cluster-level** calorimeter calibrations that depend on both cluster polar angle (`theta`) and cluster energy (`E`), applied **after clustering** and **before final PFO energy assignment**.

The system must support **separate calibration tables for ECAL and HCAL**.

This replaces/extends the current 1D non-linearity strategy so calibration can correct geometry/material-driven biases with angular dependence.

## Baseline (Current Workflow)

From the code currently used in your chain:

- `DDPandoraPFANewProcessor` exposes 1D non-linearity points via:
  - `InputEnergyCorrectionPoints`
  - `OutputEnergyCorrectionPoints`
  in [DDPandoraPFANewProcessor.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/src/DDPandoraPFANewProcessor.cc:787)
- Those are registered as a Pandora hadronic correction plugin:
  - `LCContent::RegisterNonLinearityEnergyCorrection(..., m_inputEnergyCorrectionPoints, m_outputEnergyCorrectionPoints)`
  in [DDPandoraPFANewProcessor.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/src/DDPandoraPFANewProcessor.cc:313)
- In your current Pandora XML, enabled hadronic correction plugins are:
  - `SoftwareCompensation` only
  in [PandoraSettingsDefault.xml](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/SteeringMacros/PandoraSettings/PandoraSettingsDefault.xml:10)

So today the framework supports hadronic correction plugin registration, but your desired 2D theta-energy behavior is not available yet.

## Required Changes

## 1) `DDMarlinPandora` (Marlin wrapper layer)

Add new steering parameters to `DDPandoraPFANewProcessor::Settings`:

- `ECalThetaEnergyCorrectionThetaBinEdges` (`FloatVector`)  
- `ECalThetaEnergyCorrectionEnergyBinEdges` (`FloatVector`)  
- `ECalThetaEnergyCorrectionScaleFactors` (`FloatVector`, flattened 2D table)  
- `HCalThetaEnergyCorrectionThetaBinEdges` (`FloatVector`)  
- `HCalThetaEnergyCorrectionEnergyBinEdges` (`FloatVector`)  
- `HCalThetaEnergyCorrectionScaleFactors` (`FloatVector`, flattened 2D table)  
- `ThetaEnergyCorrectionPluginName` (`std::string`, default `"ThetaEnergyBinned"`)  
- `ThetaEnergyCorrectionEnabled` (`bool`, default `false`)  
- `ThetaEnergyCorrectionExtrapolationMode` (`int` or enum as string; clamp vs fail)

Files:
- [DDPandoraPFANewProcessor.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/include/DDPandoraPFANewProcessor.h)
- [DDPandoraPFANewProcessor.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/src/DDPandoraPFANewProcessor.cc)

Implementation details:

1. Register the new processor parameters in `ProcessSteeringFile()`.
2. Validate at init (separately for ECAL and HCAL):
   - `Ntheta >= 2`, `NE >= 2`
   - `scaleFactors.size() == (Ntheta-1) * (NE-1)`
   - strictly increasing bin edges.
3. In `RegisterUserComponents()`, when enabled, register a new correction plugin in LCContent with these bins/scales.

## 2) Pandora `LCContent` plugin (actual correction logic)

Add a new hadronic energy correction plugin in `PandoraPFA/LCContent`.

Concrete existing integration points:

- Existing energy correction plugin classes are in:
  - [LCEnergyCorrectionPlugins.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/include/LCPlugins/LCEnergyCorrectionPlugins.h)
  - [LCEnergyCorrectionPlugins.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/src/LCPlugins/LCEnergyCorrectionPlugins.cc)
- Existing registration entrypoint is in:
  - [LCContent.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/src/LCContent.cc:235)

Proposed new class:
- `LCThetaEnergyBinnedEnergyCorrection` (name flexible)

Expected behavior:

1. For each cluster needing hadronic energy correction:
   - compute `theta` from cluster position,
   - get cluster pre-correction hadronic energy `E`.
2. Determine calibration domain (`ECAL` or `HCAL`) from cluster content.
   - default policy: choose domain by dominant hadronic energy contribution from ECAL-like vs HCAL-like hits in the cluster.
3. Find 2D bin `(theta_bin, energy_bin)` in the selected domain table.
4. Apply scale: `E_corrected = scale_domain(theta_bin, energy_bin) * E`.
5. Honor underflow/overflow policy:
   - default: apply a correction of 1 (no correction) to anything in underflow/overflow
6. Keep plugin deterministic and stateless event-to-event.

Required LCContent edits:

1. Add new nested plugin class declaration in `LCEnergyCorrectionPlugins.h`.
2. Implement constructor, `MakeEnergyCorrections`, `ReadSettings` in `LCEnergyCorrectionPlugins.cc`.
3. Add a public LCContent registration helper, e.g.:
   - `RegisterThetaEnergyBinnedEnergyCorrection(...)`
   in:
   - [LCContent.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/include/LCContent.h)
   - [LCContent.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/src/LCContent.cc)
4. Optionally add default XML-constructible plugin registration macro entry (same pattern as `CleanClusters`, `ScaleHotHadrons`, `MuonCoilCorrection`) in `LCContent.cc`.

## 3) Pandora XML workflow integration

Update `PandoraSettingsDefault.xml` plugin list:

- Current:
  - `<HadronicEnergyCorrectionPlugins>SoftwareCompensation</HadronicEnergyCorrectionPlugins>`
- Proposed:
  - include both plugins with explicit order, e.g.
    - `ThetaEnergyBinned SoftwareCompensation`
  - order decision:
    1. `ThetaEnergyBinned` then `SoftwareCompensation` (recommended first pass), or
    2. reverse order if validation favors it.

File:
- [PandoraSettingsDefault.xml](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/SteeringMacros/PandoraSettings/PandoraSettingsDefault.xml)

## 4) Steering (`steer_reco.py`) parameters

Expose optional arguments that populate new DDMarlinPandora parameters:

- `--ecalThetaEnergyCalibFile` and `--hcalThetaEnergyCalibFile` (preferred high-level interface)
  - each parsed into bin edges + flattened scales before setting `DDMarlinPandora.Parameters`.

or direct low-level vectors:
- `ECalThetaEnergyCorrectionThetaBinEdges`
- `ECalThetaEnergyCorrectionEnergyBinEdges`
- `ECalThetaEnergyCorrectionScaleFactors`
- `HCalThetaEnergyCorrectionThetaBinEdges`
- `HCalThetaEnergyCorrectionEnergyBinEdges`
- `HCalThetaEnergyCorrectionScaleFactors`

## Calibration Data Model

Recommended file format (human-editable and robust):

Use one file per domain (`ECAL` and `HCAL`) with identical schema.

```text
# theta bins (rad)
theta_edges: 0.0,0.4,0.8,1.2,1.6,2.0,2.4,2.8,3.14159
# energy bins (GeV)
energy_edges: 0,10,20,50,100,200,500,1000,5000
# row-major scales: each theta bin row has (NE-1) values
scales:
1.05,1.04,1.03,1.02,1.01,1.00,1.00,1.00
...
```

Flatten convention:
- index = `itheta * (NE-1) + iE`

## Calibration Production Scripts (Adapting Existing Strategy)

Reference scripts you provided:

- [getSimDigiCalibration.py](/Users/tholmes/Downloads/getSimDigiCalibration.py)
- [getHCALSimDigiCalibration.py](/Users/tholmes/Downloads/getHCALSimDigiCalibration.py)

### Current behavior in those scripts

1. ECAL script:
   - uses single-particle photon samples,
   - computes `true_E / ECal_sim_E` versus `theta`,
   - produces a 1D theta profile used as ECAL correction.
2. HCAL script:
   - uses hadron samples (e.g. neutrons/pions),
   - reads ECAL correction profile,
   - estimates HCAL-target energy as:
     - `E_target_hcal = E_true - ECal_sim_E * ECAL_correction(theta)`
   - computes `E_target_hcal / HCal_sim_E` versus `theta`.

### Required adaptations for this spec (2D theta-energy + separate ECAL/HCAL)

1. Convert both pipelines from 1D theta profiles to 2D `(theta, E)` binning.
   - ECAL:
     - ratio per event: `R_ecal = E_true / ECal_cluster_or_sim_energy`
     - fill into ECAL `(theta, E)` bins.
   - HCAL:
     - ratio per event: `R_hcal = E_target_hcal / HCal_cluster_or_sim_energy`
     - fill into HCAL `(theta, E)` bins.
2. Use cluster-level energies consistent with the intended correction target.
   - Since correction is mid-Pandora cluster-level, preferred training input is uncalibrated cluster energy at the same stage (not final PFO energy).
3. Produce separate outputs:
   - ECAL table: theta edges, energy edges, scale matrix.
   - HCAL table: theta edges, energy edges, scale matrix.
4. Standardize outputs to the runtime format consumed by `DDMarlinPandora` parameters:
   - flattened row-major scale vectors with explicit bin-edge arrays.
5. Add robust statistics per bin:
   - median or truncated mean of ratios,
   - minimum effective entries per bin,
   - fallback to `1.0` for empty/low-stat bins.

### Recommended production workflow

1. **Pass A (ECAL calibration production)**
   - sample: photon gun across energy and theta coverage,
   - output: `ecal_theta_energy_calib.(json/csv)`.
2. **Pass B (HCAL calibration production, ECAL-fixed)**
   - sample: neutral hadrons and charged hadrons as needed,
   - compute `E_target_hcal = E_true - ECal_corrected(theta,E)*ECal_measured`,
   - output: `hcal_theta_energy_calib.(json/csv)`.
3. **Pass C (closure and optional iteration)**
   - run both tables together in reconstruction,
   - check residual response maps for ECAL- and HCAL-dominated clusters,
   - optionally regenerate HCAL table (and ECAL if coupling is significant).

### Script deliverables to add under this project

1. `scripts/make_ecal_theta_energy_calibration.py`
   - inputs: reco files, truth matching config, bin definitions,
   - output: ECAL calibration table + QA plots.
2. `scripts/make_hcal_theta_energy_calibration.py`
   - inputs: reco files, ECAL table from pass A, bin definitions,
   - output: HCAL calibration table + QA plots.
3. `scripts/validate_theta_energy_calibration.py`
   - inputs: validation samples + produced ECAL/HCAL tables,
   - output: closure plots and bin occupancy diagnostics.
4. `scripts/build_theta_energy_steering_payload.py`
   - inputs: ECAL + HCAL calibration JSON tables,
   - output: merged DDMarlin parameter payload (JSON + python block) ready for `DDMarlinPandora.Parameters.update(...)`.

Initial implementation status in this repository:

- Implemented:
  - [make_ecal_theta_energy_calibration.py](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/scripts/make_ecal_theta_energy_calibration.py)
  - [make_hcal_theta_energy_calibration.py](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/scripts/make_hcal_theta_energy_calibration.py)
  - [validate_theta_energy_calibration.py](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/scripts/validate_theta_energy_calibration.py)
  - [build_theta_energy_steering_payload.py](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/scripts/build_theta_energy_steering_payload.py)
  - shared helpers:
    - [calibration_lib.py](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/scripts/calibration_lib.py)
- Example configs:
  - [example_ecal_calibration_config.txt](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/config/example_ecal_calibration_config.txt)
  - [example_hcal_calibration_config.txt](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/config/example_hcal_calibration_config.txt)

### Key technical choices to lock before implementation

1. Training observable source:
   - pure `SimCalorimeterHit` sums vs Pandora cluster energies at correction stage.
2. Theta definition:
   - truth-particle theta (training convenience) vs cluster-theta (runtime-consistent).
3. Event selection/matching:
   - single-primary requirement, containment cuts, leakage treatment.
4. HCAL target definition for mixed-shower cases:
   - strict subtraction with ECAL correction and safeguards against negative `E_target_hcal`.

## End-to-End Workflow (Target)

1. `DDSim` + digi/reco setup produces calo hits and tracks as now.
2. Pandora clustering runs (`ClusteringParent`, `PhotonReconstruction`, etc.).
3. **New stage (inside hadronic energy correction plugin stack, mid-Pandora):**
   - for each cluster, select ECAL/HCAL calibration table and apply theta-energy binned correction.
4. Existing downstream steps continue:
   - software compensation (if enabled),
   - `PfoCreation`,
   - final ID and output PFO collections.

This preserves your requirement: correction is **mid-Pandora**, not hit-level preprocessing and not post-PFO patching.

Detailed runtime sequence:

1. `DDPandoraPFANewProcessor` reads steering vectors (ECAL + HCAL) and validates dimensions.
2. `RegisterUserComponents()` registers:
   - existing LC algorithms/plugins,
   - `ThetaEnergyBinned` correction plugin via LCContent API.
3. Pandora runs clustering algorithms (`ClusteringParent`, etc.) from XML.
4. During hadronic energy correction stage, Pandora calls `MakeEnergyCorrections(...)` for each cluster:
   - compute `(theta, E)`,
   - determine ECAL/HCAL domain from cluster content,
   - lookup 2D scale in the selected domain table,
   - update corrected hadronic energy.
5. `PfoCreation` consumes corrected cluster energies.

## Validation Plan

1. Unit tests (plugin level):
   - bin lookup (center, edges, under/overflow),
   - shape mismatch handling,
   - monotonic edge validation.
2. Integration test:
   - fixed sample with known calibration table,
   - confirm cluster energy changes prior to `PfoCreation`.
3. Physics checks:
   - `E_reco/E_true` vs `theta` in energy slices,
   - `E_reco/E_true` vs `E` in theta slices,
   - compare old 1D vs new 2D correction,
   - evaluate ECAL-dominated and HCAL-dominated cluster categories separately.
4. Stability:
   - no pathological tails from sparse bins,
   - enforce scale limits if needed.

## Risks / Design Decisions

1. Plugin order with software compensation can change final response; must be benchmarked.
2. Sparse high-energy forward bins can overfit; include smoothing or fallback policy per domain (ECAL/HCAL).
3. Maintain backward compatibility:
   - if new vectors absent or disabled, behavior should match current production.
4. Domain selection ambiguity for mixed clusters:
   - define deterministic ECAL/HCAL selection policy and document it.

## Deliverables

1. `DDMarlinPandora` parameter/API extension:
   - [DDPandoraPFANewProcessor.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/include/DDPandoraPFANewProcessor.h)
   - [DDPandoraPFANewProcessor.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/DDMarlinPandora/src/DDPandoraPFANewProcessor.cc)
2. New `LCContent` hadronic correction plugin implementing 2D `(theta, E)` scale:
   - [LCEnergyCorrectionPlugins.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/include/LCPlugins/LCEnergyCorrectionPlugins.h)
   - [LCEnergyCorrectionPlugins.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/src/LCPlugins/LCEnergyCorrectionPlugins.cc)
   - [LCContent.h](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/include/LCContent.h)
   - [LCContent.cc](/Users/tholmes/cernbox/Work/MuonCollider/Studies/10TeV/PandoraCalibration/LCContent/src/LCContent.cc)
3. Pandora XML update to include new plugin in correction chain.
4. Steering interface for file/vector input.
5. Validation scripts + reference plots.
