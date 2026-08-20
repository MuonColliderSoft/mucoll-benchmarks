# Reconstruction benchmark metrics

The EDM4hep studies under [`analysis/python/edm4hep`](../python/edm4hep/)
optionally write compact JSON sidecars with the same quantities and selections
used for their plots. `aggregate_metrics.py` validates and combines whichever
study sidecars were produced; it does not recalculate physics quantities.

This keeps one authoritative definition of each metric:

- `study_tracks.py` reports tracking efficiency, fake rate, track quality, and
  track resolutions;
- `study_seeds.py` reports seed matching, multiplicity, and resolutions;
- `study_hits.py` reports tracker-hit occupancy;
- `study_photons.py` reports photon matching, PFO multiplicity, response, and
  resolution; and
- `study_notracks.py` can report the optional empty-track diagnostic.

PFO matching uses the shared delta-R implementation in
`benchmark_metrics.py`. Study sidecars record their collection names, cuts,
binning or finite histogram range, event counts, and producer checksum.

## Produce and aggregate sidecars

Pass `--metrics` to any study. For example:

```bash
source /opt/setup_mucoll.sh
python analysis/python/edm4hep/study_tracks.py \
  -i reco.edm4hep.root \
  -o histos_tracks.root \
  -d plots \
  --metrics metrics_tracks.json

python analysis/benchmarks/aggregate_metrics.py \
  --sample-label pion \
  --input reco.edm4hep.root \
  --expected-events 100 \
  --fragment metrics_tracks.json \
  --fragment metrics_seeds.json \
  --fragment metrics_hits.json \
  --output metrics.json
```

The aggregator records the RECO input size and SHA-256, the installed
`mucoll-stack` version from `MUCOLL_RELEASE_VERSION`, the benchmark Git revision
and dirty state, aggregator and fragment checksums, and stable GitHub Actions
identifiers when present. If `submission.json` accompanies the RECO input, its
container, geometry, generated-input, and source-revision provenance is
included with its checksum.

The report intentionally excludes hostnames and full environment/package dumps.
The container digest and stack version identify the runtime without adding
machine-specific noise.

No pass/fail physics tolerances are applied yet. Initial small samples are for
reviewing the definitions and statistical stability before reference values are
fixed.

The lightweight contract tests do not require ROOT:

```bash
python3 -m unittest discover -s analysis/benchmarks -p 'test_*.py'
```
