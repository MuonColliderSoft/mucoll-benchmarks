# Tools for producing the Muon Collider benchmark plots

Collection of configuration files and scripts for obtaining the basic overview of the Muon Collider detector performance, also used for software-release validation.

## Repository structure

All the code is split into separate stages of the performance-evaluation process:

* `generation` - production of a sample of input objects, typically `MCParticles`;
* `simulation` - simulation of particles' interaction with the detector in GEANT4, typically producing `SimHits`;
* `configs` - geometry-specific digi/reco configuration packages, checked out as submodules where the upstream repository exists;
* `analysis` - production of files with standardised objects types compatible with generic plotting scripts, typically `ROOT.TTree`, `ROOT.TH1`, etc.
* `plotting` - generic scripts for producing plots from the `analysis` output.

Specific workflow scripts and corresponding plotting configurations for individual use cases are stored under `workflows/` directory.
Each workflow can use any subset of the `generation` to `plotting` stages, depending on its purpose.

Select the active geometry config with:

```bash
source setup_config.sh /path/to/mucoll-benchmarks MAIA_v0
```

After setup, run geometry-specific digitisation and reconstruction steering from
`$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/`.
