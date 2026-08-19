# Reconstruction benchmark metrics

`extract_metrics.py` reduces one or more EDM4hep reconstruction outputs to a
small JSON document suitable for release comparisons and CI artifacts. It does
not apply pass/fail tolerances. Reference values and tolerances should be added
only after the metric definitions and their statistical stability have been
reviewed.

The current metrics cover:

- truth-particle kinematics and PDG counts;
- Pandora PFO multiplicity, nearest-PFO matching, and energy/momentum response;
- selected-track multiplicity and the fraction of events with a selected track;
- reconstructed ECAL and HCAL hit multiplicities and energies; and
- input checksums and the availability of required and optional collections.

Matching uses the nearest Pandora PFO in eta-phi distance and accepts it when
`deltaR < 0.1` by default. The first `MCParticles` entry is treated as the gun
particle, matching the particle-gun samples used by the validation chain.

Run the extractor in a Muon Collider software environment. For example:

```bash
source /opt/setup_mucoll.sh
python analysis/benchmarks/extract_metrics.py \
  --expected-events 100 \
  --sample muon=/path/to/muon/reco.edm4hep.root \
  --sample electron=/path/to/electron/reco.edm4hep.root \
  --sample pion=/path/to/pion/reco.edm4hep.root \
  --sample photon=/path/to/photon/reco.edm4hep.root \
  --output metrics.json
```

The lightweight helper tests do not require ROOT:

```bash
python -m unittest discover -s analysis/benchmarks -p 'test_*.py'
```

The initial 100-event samples are intended to validate the extraction and
metric choices. They are not yet statistically sufficient to define physics
regression tolerances.
