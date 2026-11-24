#!/usr/bin/env python3
"""Sanity checks for HepMC3 files from dijetgun_hepmc3.py.

For each file, reports:
- the number of events;
- the largest four-momentum imbalance of the final state against sqrt(s) = 2E;
- the average number of final-state particles;
- how many events contain a weakly decaying B or C hadron;
- the average number of K0S and Lambda per event (these should be undecayed, status 1);
- the mean B-hadron decay length;
- the range of sampled parton energies and polar angles.

Usage: check_dijetgun_hepmc3.py FILE.hepmc3 [FILE.hepmc3 ...]
"""

import math
import sys

from pyHepMC3 import HepMC3 as hm


# Weakly decaying (ground-state) hadrons; excited states such as B* decay strongly or
# electromagnetically at their production point.
WEAK_B = {511, 521, 531, 541, 5122, 5132, 5232, 5332}
WEAK_C = {411, 421, 431, 4122, 4132, 4232, 4332}


def is_weak_decayer(pid, q):
    """Weakly decaying B (q = 5) or C (q = 4) hadron."""
    return abs(pid) in (WEAK_B if q == 5 else WEAK_C)


def int_attr(evt, name):
    a = evt.attribute_as_string(name)
    return int(a) if a else None


def float_attr(evt, name):
    a = evt.attribute_as_string(name)
    return float(a) if a else float("nan")


def check(path):
    reader = hm.ReaderAscii(path)
    n = 0
    max_imbalance = 0.
    n_final = n_b = n_c = n_k0s = n_lambda = n_bad_v0 = 0
    b_decay_lengths = []
    energies, thetas, flavours = [], [], set()
    evt = hm.GenEvent()
    while not reader.failed():
        reader.read_event(evt)
        if reader.failed():
            break
        n += 1
        energy = float_attr(evt, "parton_energy")
        energies.append(energy)
        thetas.append(math.degrees(float_attr(evt, "parton_theta")))
        flavours.add(int_attr(evt, "flavour"))

        px = py = pz = e = 0.
        has_b = has_c = False
        for p in evt.particles():
            pid, st = p.pid(), p.status()
            if st == 1:
                mom = p.momentum()
                px += mom.px(); py += mom.py(); pz += mom.pz(); e += mom.e()
                n_final += 1
            if abs(pid) == 310:
                n_k0s += 1
                n_bad_v0 += st != 1
            if abs(pid) == 3122:
                n_lambda += 1
                n_bad_v0 += st != 1
            if st == 2 and is_weak_decayer(pid, 5):
                has_b = True
                pv, ev = p.production_vertex(), p.end_vertex()
                if pv and ev:
                    d = ev.position() - pv.position()
                    b_decay_lengths.append(math.sqrt(d.x() ** 2 + d.y() ** 2 + d.z() ** 2))
            if st == 2 and is_weak_decayer(pid, 4):
                has_c = True
        n_b += has_b
        n_c += has_c
        imbalance = max(abs(px), abs(py), abs(pz), abs(e - 2. * energy))
        max_imbalance = max(max_imbalance, imbalance)
    reader.close()

    if n == 0:
        print(f"{path}: no events")
        return False
    mean_l = sum(b_decay_lengths) / len(b_decay_lengths) if b_decay_lengths else 0.
    print(f"{path}")
    print(f"  events: {n}   flavour attribute: {sorted(flavours)}")
    print(f"  parton energy: {min(energies):.1f} - {max(energies):.1f} GeV   "
          f"theta: {min(thetas):.1f} - {max(thetas):.1f} deg")
    print(f"  max final-state 4-momentum imbalance: {max_imbalance:.2e} GeV")
    print(f"  final-state particles / event: {n_final / n:.1f}")
    print(f"  events with a B hadron: {n_b / n:.0%}   with a C hadron: {n_c / n:.0%}")
    print(f"  K0S / event: {n_k0s / n:.2f}   Lambda / event: {n_lambda / n:.2f}   "
          f"(decayed by Pythia: {n_bad_v0})")
    print(f"  mean B-hadron decay length: {mean_l:.2f} mm ({len(b_decay_lengths)} B hadrons)")
    return max_imbalance < 1e-3 * max(energies) and n_bad_v0 == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ok = all([check(f) for f in sys.argv[1:]])
    sys.exit(0 if ok else 1)
