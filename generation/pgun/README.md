# Particle-gun generation scripts

Scripts for producing samples of particles to be used as input for detector simulation.
Typically used for detector-response validation or efficiency studies.

## Sampling pT flat in log(pT)

`pgun_edm4hep.py` samples `--pt min max` flat in pT by default. Add `--log-pt` to sample the same range flat in log(pT), which populates log-spaced pT bins evenly:

```bash
python pgun_edm4hep.py -e 10000 -p 1 --pdg 211 --pt 1 100 --log-pt --theta 10 170 --phi 0 360 -s 20211 -- gen-pion.edm4hep.root
```
