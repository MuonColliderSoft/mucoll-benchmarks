# Digitization

This directory contains steering files and documentation related to the digitization process for the Muon Collider.

## Overview

The digitization process transforms simulated detector hits into electronic signals by applying models of detector response and noise. This step bridges the gap between idealized simulation and realistic data, ensuring that subsequent reconstruction and analysis reflect actual detector performance. The steering files in this directory define the sequence of digitization algorithms and their configuration parameters.

## Usage

Example usage:

```
k4run digi_steer.py --DD4hepXMLFile /path/to/geometry/compact/file/MAIA_v0.xml --OverlayFullPathToMuPlus /path/to/BIB/MUPLUS/ --OverlayFullPathToMuMinus /path/to/BIB/MUMINUS/ --OverlayFullNumberBackground 60 --doOverlayFull
```

Ensure that this command is run in a directory with the input file.

## Contents

- `digi_steer.py`: A complete digitization steering file
- `algList.py`: A modifiable list of algorithms used in digitization
- `/compontents/`: Directory with all of the algorithms, split up for ease

## Contributing

For questions or contributions, please contact the maintainers or open an issue.