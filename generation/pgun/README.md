# Particle-gun generation scripts

Scripts for producing samples of particles to be used as input for detector simulation.
Typically used for detector-response validation or efficiency studies.

## Sampling pT flat in log(pT)

`pgun_edm4hep.py` samples `--pt min max` flat in pT by default. Add `--log-pt` to sample the same range flat in log(pT), which populates log-spaced pT bins evenly:

```bash
python pgun_edm4hep.py -e 10000 -p 1 --pdg 211 --pt 1 100 --log-pt --theta 10 170 --phi 0 360 -s 20211 -- gen-pion.edm4hep.root
```

## Dijet gun (`dijetgun_hepmc3.py`)

Flavour-labelled jet pairs for jet flavour-tagging studies. Each event is a colour-singlet
scalar at rest in a μ⁺μ⁻ collision at √s = M = 2E. It decays to a single parton flavour:
`b`, `c`, `s`, `u`, `d` or `g` (gluons).
- The parton energy E and the polar angle are sampled from user-chosen ranges, so every
  flavour covers the same (E, θ) plane, including the forward region.
- The two partons are back to back, at θ and π − θ.
- Pythia8 showers them and hadronises them.
- Output is HepMC3 ASCII, which `ddsim` reads directly.

**Requirements**: the `pythia8` and `pyHepMC3` Python modules, which come with a MuColl
stack built with `+gen` (e.g. the `mucoll-sim` images). Stacks without
MuonColliderSoft/mucoll-spack#119 do not put `pythia8` on the Python path; there, run
first:

```bash
export PYTHONPATH=$PYTHIA8/lib:$PYTHONPATH
```

**Usage**: one sample per flavour, e.g.

```bash
python dijetgun_hepmc3.py --flavour b --events 10000 --seed 1 --output dijet_b.hepmc3
```

| Option | Default | Meaning |
|---|---|---|
| `--flavour` | (required) | `b`, `c`, `s`, `u`, `d` or `g` |
| `--energy EMIN EMAX` | 20 5000 | parton energy range [GeV] |
| `--energy-sampling` | log | `flat` or `log` (flat in log E) |
| `--angle-sampling` | eta | `eta` (flat in η) or `costheta` |
| `--theta-min` | 10 | partons in [θ_min, 180° − θ_min] |
| `--tau0max` | 10 | cτ₀ [mm] above which Geant4, not Pythia, decays the particle |
| `--cmnd FILE` | – | extra Pythia settings (e.g. a tune), read before init |
| `--print N` | 0 | list the first N Pythia events |

`--help` lists all options. Use a different `--seed` for every flavour and job.

**Event record**

| Index | Particle | HepMC status |
|---|---|---|
| 1, 2 | μ⁻, μ⁺ beams (E = M/2 each) | 4 |
| 3 | scalar (PDG 25 by default, mass M = 2E), at rest | 22 |
| 4, 5 | hard partons | 23 |

- Final-state particles have status 1, and particles decayed by Pythia have status 2.
  The full history is kept, with each vertex at its production point.
- Per-event attributes: `flavour`, `parton_energy`, `parton_theta`, `parton_phi`.
- Run attributes: `generator`, `pythia_version`, `flavour`, `configuration`.
- Label jets from the partons or the `flavour` attribute, not from the scalar.
  Light-quark and gluon samples also contain heavy flavour from gluon splitting in the shower.

**Decays**: particles with cτ₀ > 10 mm (K⁰_S, Λ, Σ, Ξ, Ω, and the usual stable ones) are
left to Geant4. Heavy-flavour hadrons and τ are decayed by Pythia, with displaced decay
vertices in the HepMC record.

**Beam spot**: not applied. Use `ddsim --vertexSigma ...`.

**Simulation**:

```bash
ddsim --steeringFile simulation/steer_baseline.py \
      --compactFile ${k4geo_DIR}/MuColl/MAIA/compact/MAIA_v0/MAIA_v0.xml \
      --inputFiles dijet_b.hepmc3 --outputFile dijet_b_sim.edm4hep.root
```

Geant4 prints `G4PrimaryParticle::Set4Momentum` warnings for short-lived resonances (e.g. ρ)
whose Breit–Wigner mass differs from the nominal one. They are harmless.

**Checks**: `check_dijetgun_hepmc3.py FILE...` reports, for each file:
- the event count and the sampled energy and angle ranges;
- the four-momentum balance against √s;
- the heavy-flavour content and the mean B-hadron decay length;
- whether any K⁰_S or Λ was decayed by Pythia.

It exits non-zero if the balance or the K⁰_S/Λ check fails. The CI workflow
`.github/workflows/dijetgun.yml` runs the gun and this check for all flavours in the latest
`mucoll-sim` image.
