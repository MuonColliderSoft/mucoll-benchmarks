# Reconstruction

This directory contains steering files and documentation related to the reconstruction process for the Muon Collider.

## Overview

The reconstruction process converts raw detector data into meaningful physics objects, such as tracks and clusters, by applying a series of algorithms. This step is essential for transforming digitized signals into higher-level information that can be used for analysis. The steering file in this directory configures the sequence of reconstruction algorithms and their parameters.

## Usage

To run the reconstruction step, use the following command:

```
k4run reco_steer.py
```

Ensure that this command is run in a directory with the input file. Additionally, the `/PandoraSettings/` directory must also be present.


## Contents

- `reco_steer.py`: A complete reconstruction steering file
- `algList.py`: A modifiable list of algorithms used in reconstruction
- `/compontents/`: Directory with all of the algorithms, split up for ease
- `/PandoraSettings/`: Directory with Pandora steering information. Must be present in directory where reconstruction is run

## Contributing

For questions or contributions, please contact the maintainers or open an issue.