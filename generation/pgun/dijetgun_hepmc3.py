#!/usr/bin/env python3
"""Pythia8 dijet gun: flavour-labelled jet pairs with user-chosen kinematics.

Typically used for jet flavour-tagging studies and training samples.

Each event is a colour-singlet scalar produced at rest in a mu+ mu- collision at
sqrt(s) = M = 2E. It decays to a parton pair of a single flavour: b b~, c c~, s s~,
u u~, d d~ or g g. The parton energy E and the polar angle of the first parton are
sampled from user ranges, so every flavour covers the same (E, theta) plane.
The partons are showered (forceTimeShower) and hadronised by Pythia8, and the event
is written as HepMC3 ASCII for ddsim.

Pythia event record (mimics a real mu+ mu- -> X -> q q~ event):
  1, 2 : mu-, mu+ beams                (status -12, HepMC status 4)
  3    : scalar X, PDG 25 by default   (status -22)
  4, 5 : hard partons, mother = 3      (status 23)

Particles with c*tau0 > --tau0max (default 10 mm: K0S, Lambda, Sigma, Xi, Omega, ...)
are left undecayed for Geant4. Beam-spot smearing is left to ddsim (--vertexSigma).

Needs the pythia8 and pyHepMC3 Python modules from a MuColl stack built with +gen
(e.g. the mucoll-sim images). Stacks without MuonColliderSoft/mucoll-spack#119 do not
put pythia8 on the Python path; there, run first:
    export PYTHONPATH=$PYTHIA8/lib:$PYTHONPATH
"""

import argparse
import math
import os
import sys

VERSION = "1.0"
FLAVOURS = {"d": 1, "u": 2, "s": 3, "c": 4, "b": 5, "g": 21}


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Colour-singlet scalar at rest decaying to one parton flavour, "
                    "showered and hadronised by Pythia8, written as HepMC3 ASCII.")
    p.add_argument("--flavour", required=True, choices=FLAVOURS.keys(),
                   help="parton flavour of the decay")
    p.add_argument("--output", required=True, help="output HepMC3 ASCII file (.hepmc3)")
    p.add_argument("--overwrite", action="store_true", help="overwrite an existing output")
    p.add_argument("--events", type=int, default=1000, help="number of events [%(default)s]")
    p.add_argument("--seed", type=int, default=12345,
                   help="random seed, 1..900000000 [%(default)s]")
    p.add_argument("--energy", type=float, nargs=2, default=[20., 2000.],
                   metavar=("EMIN", "EMAX"), help="parton energy range in GeV [%(default)s]")
    p.add_argument("--energy-sampling", choices=["flat", "log"], default="log",
                   help="flat in E or flat in log E [%(default)s]")
    p.add_argument("--angle-sampling", choices=["eta", "costheta"], default="eta",
                   help="flat in eta or in cos(theta) [%(default)s]")
    p.add_argument("--theta-min", type=float, default=10.,
                   help="partons in [theta-min, 180 - theta-min] degrees [%(default)s]")
    p.add_argument("--tau0max", type=float, default=10.,
                   help="c*tau0 [mm] above which Geant4 decays particles [%(default)s]")
    p.add_argument("--resonance-id", type=int, default=25,
                   help="PDG id given to the scalar [%(default)s]")
    p.add_argument("--cmnd", help="extra Pythia settings file (e.g. a tune), read before init")
    p.add_argument("--print", type=int, default=0, dest="nprint",
                   help="list the first N Pythia events [%(default)s]")
    args = p.parse_args(argv)

    emin, emax = args.energy
    if args.events <= 0:
        p.error("--events must be positive")
    if not 1 <= args.seed <= 900000000:
        p.error("--seed must be in [1, 900000000]")
    if not 0. < emin <= emax:
        p.error("--energy needs 0 < EMIN <= EMAX")
    if not 0. < args.theta_min < 90.:
        p.error("--theta-min must be in (0, 90) degrees")
    if not args.overwrite and os.path.exists(args.output):
        p.error(f"output exists (use --overwrite): {args.output}")
    return args


def describe(args):
    s = (f"flavour={args.flavour} energy=[{args.energy[0]:g},{args.energy[1]:g}] GeV "
         f"({args.energy_sampling}) theta=[{args.theta_min:g},{180. - args.theta_min:g}] deg "
         f"({args.angle_sampling}) tau0Max={args.tau0max:g} mm "
         f"resonanceId={args.resonance_id} seed={args.seed}")
    if args.cmnd:
        s += f" cmnd={args.cmnd}"
    return s


# --- Sampling ------------------------------------------------------------------------

def sample_energy(rndm, args):
    emin, emax = args.energy
    if args.energy_sampling == "flat":
        return emin + rndm.flat() * (emax - emin)
    return emin * (emax / emin) ** rndm.flat()


def sample_theta(rndm, args):
    theta_min = math.radians(args.theta_min)
    if args.angle_sampling == "eta":
        eta_max = -math.log(math.tan(0.5 * theta_min))
        eta = (2. * rndm.flat() - 1.) * eta_max
        return 2. * math.atan(math.exp(-eta))
    return math.acos((2. * rndm.flat() - 1.) * math.cos(theta_min))


# --- Pythia --------------------------------------------------------------------------

def fill_event(event, pdt, args, energy, theta, phi):
    """Beams, scalar at rest and two back-to-back partons, in Pythia's event record."""
    import pythia8

    flavour = FLAVOURS[args.flavour]
    mass = 2. * energy
    m_mu = pdt.m0(13)
    p_beam = math.sqrt(max(0., energy * energy - m_mu * m_mu))

    event.reset()  # leaves only entry 0, the "system" particle
    event[0].p(pythia8.Vec4(0., 0., 0., mass))
    event[0].m(mass)

    # 1, 2: incoming beams; daughter = 3.
    event.append(13, -12, 0, 0, 3, 0, 0, 0, pythia8.Vec4(0., 0., p_beam, energy), m_mu)
    event.append(-13, -12, 0, 0, 3, 0, 0, 0, pythia8.Vec4(0., 0., -p_beam, energy), m_mu)
    # 3: the scalar, at rest; daughters 4-5.
    event.append(args.resonance_id, -22, 1, 2, 4, 5, 0, 0,
                 pythia8.Vec4(0., 0., 0., mass), mass)

    # 4, 5: partons. A quark pair is one colour line; a gluon pair is a closed loop.
    gluons = flavour == 21
    m = 0. if gluons else pdt.m0(flavour)
    p = math.sqrt(energy * energy - m * m)
    px = p * math.sin(theta) * math.cos(phi)
    py = p * math.sin(theta) * math.sin(phi)
    pz = p * math.cos(theta)
    id1, id2 = (21, 21) if gluons else (flavour, -flavour)
    col1, acol1 = (101, 102) if gluons else (101, 0)
    col2, acol2 = (102, 101) if gluons else (0, 101)
    event.append(id1, 23, 3, 0, 0, 0, col1, acol1, pythia8.Vec4(px, py, pz, energy), m, mass)
    event.append(id2, 23, 3, 0, 0, 0, col2, acol2, pythia8.Vec4(-px, -py, -pz, energy), m, mass)


def make_pythia(args):
    import pythia8

    pythia = pythia8.Pythia("", False)  # quiet banner
    for setting in [
        "ProcessLevel:all = off",  # hard event filled by hand
        "Random:setSeed = on",
        f"Random:seed = {args.seed}",
        "ParticleDecays:limitTau0 = on",
        f"ParticleDecays:tau0Max = {args.tau0max}",
        "Next:numberCount = 1000",
        "Next:numberShowEvent = 0",
        "Next:numberShowProcess = 0",
        "Next:numberShowInfo = 0",
    ]:
        pythia.readString(setting)
    if args.cmnd and not pythia.readFile(args.cmnd):
        sys.exit(f"Error: could not read {args.cmnd}")
    if not pythia.init():
        sys.exit("Error: Pythia initialisation failed")
    return pythia


# --- HepMC3 conversion ---------------------------------------------------------------

def to_hepmc(event, hm, run_info):
    """Convert a Pythia event record into a HepMC3 GenEvent (GeV, mm).

    Each particle's production vertex is the end vertex shared by its mothers, placed at
    the particle's production point. The HepMC status follows Pythia's statusHepMC()
    (1 final, 2 decayed, 4 beam; other history entries keep Pythia's |status|).
    """
    evt = hm.GenEvent(run_info, hm.Units.GEV, hm.Units.MM)
    n = event.size()

    particles = [None] * n
    for i in range(1, n):
        pp = event[i]
        gp = hm.GenParticle(hm.FourVector(pp.px(), pp.py(), pp.pz(), pp.e()),
                            pp.id(), pp.statusHepMC())
        gp.set_generated_mass(pp.m())
        particles[i] = gp

    end_vertex = {}   # Pythia index -> GenVertex where the particle ends
    vertices = []
    n_conflicts = 0
    for i in range(1, n):
        mothers = [m for m in event[i].motherList() if m > 0]
        if not mothers:
            continue
        vtx = next((end_vertex[m] for m in mothers if m in end_vertex), None)
        if vtx is None:
            pp = event[i]
            vtx = hm.GenVertex(hm.FourVector(pp.xProd(), pp.yProd(), pp.zProd(), pp.tProd()))
            vertices.append(vtx)
        for m in mothers:
            if m not in end_vertex:
                end_vertex[m] = vtx
                vtx.add_particle_in(particles[m])
            elif end_vertex[m] is not vtx:
                n_conflicts += 1
        vtx.add_particle_out(particles[i])

    for vtx in vertices:
        evt.add_vertex(vtx)
    # Particles with no mother and no daughter would otherwise be dropped.
    for i in range(1, n):
        if not particles[i].in_event():
            evt.add_particle(particles[i])
    return evt, n_conflicts


def main(argv=None):
    args = parse_args(argv)
    try:
        import pythia8  # noqa: F401
        from pyHepMC3 import HepMC3 as hm
    except ImportError as err:
        sys.exit(f"Error: {err}. This script needs the pythia8 and pyHepMC3 Python modules "
                 "from a MuColl stack built with +gen. If $PYTHIA8 is set, try: "
                 "export PYTHONPATH=$PYTHIA8/lib:$PYTHONPATH")

    pythia = make_pythia(args)
    flavour = FLAVOURS[args.flavour]
    m_parton = 0. if flavour == 21 else pythia.particleData.m0(flavour)
    if args.energy[0] <= 2. * m_parton:
        sys.exit(f"Error: EMIN must exceed twice the {args.flavour} mass ({2. * m_parton:g} GeV)")

    run_info = hm.GenRunInfo()
    run_info.add_attribute("generator", hm.StringAttribute(f"dijetgun_hepmc3.py {VERSION}"))
    run_info.add_attribute("pythia_version",
                           hm.DoubleAttribute(pythia.settings.parm("Pythia:versionNumber")))
    run_info.add_attribute("flavour", hm.IntAttribute(flavour))
    run_info.add_attribute("configuration", hm.StringAttribute(describe(args)))
    writer = hm.WriterAscii(args.output, run_info)
    if writer.failed():
        sys.exit(f"Error: could not open {args.output}")

    print(f"dijetgun_hepmc3.py {VERSION}: {describe(args)}")
    n_written = n_failed = n_conflicts = 0
    for i_event in range(args.events):
        energy = sample_energy(pythia.rndm, args)
        theta = sample_theta(pythia.rndm, args)
        phi = 2. * math.pi * pythia.rndm.flat()

        fill_event(pythia.event, pythia.particleData, args, energy, theta, phi)
        pythia.forceTimeShower(4, 5, 2. * energy)
        if not pythia.next():
            n_failed += 1
            if n_failed > 10 + args.events // 10:
                print("Error: too many failed events, stopping", file=sys.stderr)
                break
            continue
        if i_event < args.nprint:
            pythia.event.list()

        evt, conflicts = to_hepmc(pythia.event, hm, run_info)
        n_conflicts += conflicts
        evt.set_event_number(i_event)
        evt.add_attribute("flavour", hm.IntAttribute(flavour))
        evt.add_attribute("parton_energy", hm.DoubleAttribute(energy))
        evt.add_attribute("parton_theta", hm.DoubleAttribute(theta))
        evt.add_attribute("parton_phi", hm.DoubleAttribute(phi))
        writer.write_event(evt)
        n_written += 1
    writer.close()

    pythia.stat()
    print(f"Wrote {n_written} events ({n_failed} failed) to {args.output}")
    if n_conflicts:
        print(f"Warning: {n_conflicts} mother links could not be represented in HepMC3",
              file=sys.stderr)
    return 0 if n_written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
