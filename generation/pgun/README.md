# Particle-gun generation scripts

Scripts for producing samples of particles to be used as input for detector simulation.
Typically used for detector-response validation or efficiency studies.

## Sampling pT flat in log(pT)

`pgun_edm4hep.py` samples `--pt min max` flat in pT by default. Add `--log-pt` to sample the same range flat in log(pT), which populates log-spaced pT bins evenly:

```bash
python pgun_edm4hep.py -e 10000 -p 1 --pdg 211 --pt 1 100 --log-pt --theta 10 170 --phi 0 360 -s 20211 -- gen-pion.edm4hep.root
```

## Capping the total momentum

With `--pt`, a uniform θ range lets p = pT / sin θ exceed what the collider can produce at small angles. `--p-max P` draws each (pT, θ) pair again until p ≤ P [GeV], so every event is kept but the forward high-pT corner is left empty:

```bash
python pgun_edm4hep.py -e 10000 -p 1 --pdg 13 -13 --pt 0.5 5000 --log-pt --p-max 5000 --theta 10 170 --dz 0 0 1.5 -s 1001 -- gen-muon.edm4hep.root
```
