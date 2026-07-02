# MuColl Benchmarks Playground

Welcome to the **k4MuCPlayground**! This guide will help you set up your environment and run the full simulation chain.

---

## Environment Setup

With the new image, everything works out-of-the-box. The path to the setup script may change in different versions, so use tab-complete to fill in the ellipses:

```bash
apptainer shell --cleanenv docker://ghcr.io/muoncollidersoft/mucoll-sim-alma9:full_gaudi_test 
source /opt/spack/opt/spack/.../linux-almalinux9-x86_64/mucoll-stack-.../setup.sh
cd /path/to/k4MuCPlayground
source ../setup_config.sh ../ DETECTOR_GEOMETRY_NAME
```

> **Note:**  
> If you are somewhere other than `k4MuCPlayground` when sourcing the setup script, simply point the argument to wherever the `mucoll-benchmarks` directory exists.  
> For `DETECTOR_GEOMETRY_NAME`, use the style `MAIA_v0`.

---

## Generation

```bash
python ../generation/pgun/pgun_edm4hep.py \
    -p 1 -e 1 --pdg 11 --pt 100 --theta 10 170 -- gen_output.edm4hep.root
```

---

## Simulation

```bash
ddsim --steeringFile ../simulation/steer_baseline.py --numberOfEvents 1
```

---

## Digitization

```bash
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/digi_steer.py"
```

---

## Reconstruction

```bash
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/reco_steer.py"
```

---

## Input/Output

- **Simulation:**
    ```bash
    --inputFiles INPUT_FILE_NAME.edm4hep.root --outputFile OUTPUT_FILE_NAME.edm4hep.root
    ```
- **Digitization/Reconstruction:**
    ```bash
    --IOSvc.Input INPUT_FILE_NAME.edm4hep.root --IOSvc.Output OUTPUT_FILE_NAME.edm4hep.root
    ```

---

## Setting Environment Variables

The Simulation, Digitization, and Reconstruction steps all use environment variables for the geometry:

- `MUCOLL_GEO` (Sim, Digi, Reco)
- `MUCOLL_GEOM_NAME`, `MUCOLL_MATMAP`, `MUCOLL_TGEO`, `MUCOLL_TGEO_DESC` (Reco)

These are set by the setup script. Point them elsewhere if you wish.

- All Geometry Files (MuColl_v1, MuSIC, MAIA) live in the `k4geo` directory (`.../share/k4geo/MuColl/`).
- All Tracking geometries live in the `k4actstracking` directory (`.../share/k4ActsTracking/data/`).

---

## Adding Beam-Induced Background (BIB)

BIB is included during the digitization stage. For this, you will need BIB samples. If you don't have any,
reach out to your favorite Muon Colliderer and they can probably point you to a set.

BIB can be included by using some key arguments at the digitzation stage:
```bash
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/digi_steer.py" \
    --doOverlayFull \ # Turns on BIB Overlay
    --OverlayFullNumberBackground 100 \ # The amount of BIB. 812 is Full BIB
    --OverlayFullPathToMuPlus  /Path/to/MuPlus/Files  \ # The directory containing the MuPlus  Files
    --OverlayFullPathToMuMinus /Path/to/MuMinus/Files \ # The directory containing the MuMinus Files
```

---

> For more details, refer to the documentation or reach out to the maintainers.
