# BIB generation scripts

These scripts convert custom particle definitions from BIB generators to the stadard format used by the detector simulation framework.
Several different scripts are available for different data formats.

> **NOTE:** Typically we apply some filtering of particles during the conversion step, to reduce simulation time, e.g. slow neutrons or particles arriving too late.
> Check available options in each script: `python3 <script>.py --help`

- - -

#### FLUKA -> LCIO

`fluka_to_slcio.py` - converts a BIB sample generated in FLUKA (stored in a custom binary format) to LCIO format

Typical use example:

```bash
python3 fluka_to_slcio.py -v 2 input1.dat input2.dat ... inputN.dat output.slcio
```

Version `-v` of the input binary format must be always specified.
All the supported format versions are defined [here](/generation/bib/data_formats.py).

By default it will combine all particles from each input `.dat` file into a single event in the output `.slcio` file, e.g. sample of 5 input files with 200 particles/file will be stored as 5 events with 200 particles/event in the output `.slcio` file.


Several useful options:

* `-f N` - merges `N` input files into a single event. Use `-f -1` to treat all files as a continuous stream of particles
* `-l N` - merges `N` input particles into a single event. Use `-l -1` (default) to put all particles into a single event
* `-n N` - adds `N-1` copies of each input particle randomly distributed in Phi to the same `LCIO` event, to increase statistics

- - -

#### MARS15 -> LCIO

`bib_to_slcio.py` - converts a BIB sample generated in MARS15 (stored in a custom text format, 1 particle/line) to LCIO format

Typical use example:

```bash
python3 bib_to_slcio.py --weight 400000 --decays 5000000 input_file output.slcio
```

> **ATTENTION:**
> To have correct normalisation, copies of each particle are created, randomly distributed in Phi, according to the factor calculated from the `--weight` and `--decays` command-line parameters of the script. The `--decays` parameter represents the number of initial muon decays simulated for the input file, and is encoded in the name of the file, e.g. for file `mumi-5e6-40m-lowth` you should use `--decays 5000000`. Then, assuming the nominal beam intensity of `2e11` muons per bunch you should use `--weight 400000` to obtain the desired `5e6 * 4e5 = 2e11` initial decays.

Each line of the input MARS15 file has a particle definition in the following format:

```csv
NI,JJ,X,Y,Z,PX,PY,PZ,TOFF,W,ZDEC,XORIG,YORIG,ZORIG,WORIG,EORIG,IORIG,KORIG
FORMAT(I11,I7,3F11.3,11(1PE14.6),I7,I3)
```

with the following meanings:
* `NI` - history number
* `JJ` - particle ID, reaching detector
* `X,Y,Z` - coordinates on interface surface (cm)
* `PX,PY,PZ` - momentum components  (GeV/c)
* `TOFF` - time with respect to bunch crossing.
* `W` - particle weight.
* `ZDEC` - decay coordinate along beam line.
* `XORIG,YRIG,ZORIG` - coordinate of particle origin (cm),
* `WORIG,EORIG,IORIG` - weight, energy, particle ID of  particle origin
* `KORIG` - type of process in which particle were created

Particle ID definitions in the MARS15 files are the following:

```
PARTICLE ID:
   1   2   3   4   5   6   7   8   9  10  11  12   13   14  15  16  17  18  19   20  21
   p   n  pi+ pi-  K+  K- mu+ mu-  g  e-  e+ pbar  pi0  d   t   He3 He4 num nuam nue nuae
   22  23  24 25  26  27   28   29   30   31   32   33   34  35   36   37   38    39    40
   K0L K0S K0 AK0 LAM ALAM SIG+ SIG0 SIG- nbar KSI0 KSI- OM- sib- si0b sib+ AKSI0 ksib+ omb+

KORIG = 0 - primary beam
        1 - muons, unstable particle decay
        2 - muons, prompt at hA-vertex
        3 - muons, Bethe-Heitler pair
        4 - muons, e+e- annihilation
        5 - hadrons, hA-vertex
        6 - hadrons, elastic
        7 - hadrons, from muons
        8 - hadrons, unstable particle decay
        9 - hadrons, EMS (electromagnetic showers)
       10 - hadrons, recoil LEN
       11 - hadrons, from neutrinos
       12 - EMS, induced by photons from pi0-decay
       13 - EMS, induced by synchrotron photons
       14 - EMS, induced by g,e+,e-, at hA vertex
       15 - EMS, induced by knock-on electrons from muons or hadrons
       16 - EMS, induced by g,e+,e- from unstable particle decay
       17 - EMS, induced by prompt e+e- from muons or hadrons
       18 - EMS, induced by brems photons from muon
       19 - EMS, induced by photons from stopped muons
       20 - EMS, induced by photons from low-energy neutron
       21 - muons, vector mesons
```
