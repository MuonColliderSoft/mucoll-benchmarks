#!/usr/bin/env python
"""This script converts a MARS file to an SLCIO file with MCParticles that can be used by ILCSoft"""

import os
import argparse


parser = argparse.ArgumentParser(description='Convert MARS text file to SLCIO file with MCParticles')
parser.add_argument('file_in', metavar='FILE_IN', help='Path to the input MARS15 file')
parser.add_argument('file_out', metavar='FILE_OUT.slcio', help='Path to the output SLCIO file')
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the header', type=str)
parser.add_argument('-d', '--decays', metavar='D',  help='Number of decays simulated in the input sample (default: 5e5)', type=float, default=5e5)
parser.add_argument('-i', '--invert_pdgs', help='Invert PDG IDs selection', default=False, action='store_true')
parser.add_argument('-l', '--lines_event', metavar='L',  help='Number of lines to put in a single LCIO event (default: 1000)', type=int, default=1000)
parser.add_argument('-m', '--max_lines', metavar='M',  help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-n', '--np_min', metavar='N',  help='Minimum momentum of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file', action='store_true', default=False)
parser.add_argument('-p', '--pdgs', metavar='ID',  help='PDG IDs of particles to be included', type=int, default=None, nargs='+')
parser.add_argument('-t', '--t_max', metavar='T',  help='Maximum time of accepted particles [ns]', type=float, default=None)
parser.add_argument('-w', '--weight', metavar='W',  help='Weight nominator in the input sample (default: 427780)', type=float, default=427780)

args = parser.parse_args()

if not args.overwrite and os.path.isfile(args.file_out):
    raise FileExistsError('Output file already exists: {0:s}'.format(args.file_out))

print("Converting MARS data from file\n  {0:s}\nto SLCIO file\n  {1:s}\nwith N decays: {2:.0f}".format(args.file_in, args.file_out, args.decays))
print("Splitting by {0:d} lines/event".format(args.lines_event));
if args.pdgs is not None:
    flag = 'in' if not args.invert_pdgs else 'NOT in'
    print("Will only use particles with PDG IDs {0:s} the list: {1}".format(flag, args.pdgs))


from math import sqrt
from pdb import set_trace as br
from array import array
from pyLCIO import UTIL, EVENT, IMPL, IO, IOIMPL

import random
import math

from bib_pdgs import MARS_PIDS, PDG_PROPS

N_WORDS = 18

wrt = IOIMPL.LCFactory.getInstance().createLCWriter()
wrt.open( args.file_out, EVENT.LCIO.WRITE_NEW )

# Write a RunHeader
run = IMPL.LCRunHeaderImpl()
run.setRunNumber(0)
run.parameters().setValue("Generator", "MARS15")
run.parameters().setValue("NDecays", args.decays)
run.parameters().setValue("WNominator", args.weight)
if args.t_max:
    run.parameters().setValue("Time_max", args.t_max)
if args.np_min:
    run.parameters().setValue("NeutronMomentum_min", args.np_min)
if args.pdgs:
    run.parameters().setValue("PdgIds", str(args.pdgs))
    run.parameters().setValue("NoPdgIds", args.invert_pdgs)
if args.comment:
    run.parameters().setValue('Comment', args.comment)
wrt.writeRunHeader(run)

# Calculating the correction to particle weights (from the original MARS2ROOT conversion script)
w_corr = args.weight/args.decays;

random.seed()
nEventLines = 0
nEvents = 0
col = None
evt = None

with open(args.file_in) as file_in:
    for iL, line in enumerate(file_in):
        if nEventLines == 0:
            col = IMPL.LCCollectionVec(EVENT.LCIO.MCPARTICLE)
            # Creating the LCIO event and collection
            evt = IMPL.LCEventImpl()

            evt.setEventNumber(nEvents)
            evt.addCollection(col, "MCParticle")
        if args.max_lines and iL >= args.max_lines:
            break

        # Splitting the values into words and converting values to numbers
        ss = line.split()
        if len(ss) != N_WORDS:
            print('WARNING: wrong number of values on line {0:d}: {1:d}'.format(iL, len(ss)))

        # Converting string values to integers
        ni, jj = map(int, ss[:2])

        # Getting the particle PDG parameters
        try:
            pdg = MARS_PIDS[jj]
            charge, mass = PDG_PROPS[pdg]
        except KeyError:
            print('WARNING: No PDG available for particle with MARS ID: {0:d}'.format(jj))
            print('         Skipping the particle...')
            continue

        # Skipping if this pdgId should be excluded
        if args.pdgs is not None:
            if args.invert_pdgs and pdg in args.pdgs:
                continue
            elif not args.invert_pdgs and pdg not in args.pdgs:
                continue

        # Converting the rest of string values to floats
        x,y,z, px,py,pz, toff, w = map(float, ss[2:10])

        # Skipping if it's a neutron with too low momentum
        if args.np_min is not None and abs(pdg) == 2112 and sqrt(px*px + py*py + pz*pz) < args.np_min:
            continue

        # Converting time: s -> ns
        toff *= 1e9

        # Skipping if particle's time is greater than allowed
        if args.t_max is not None and toff > args.t_max:
            continue

        # Correcting the weight
        w *= w_corr

        # Converting vertex coordinates: cm -> mm
        x *= 10
        y *= 10
        z *= 10

        # Calculating how many copies of the particle to create according to the weight
        nW = math.floor(w)
        if random.random() < math.modf(w)[0]:
            nW += 1

        # Creating the particle with original parameters
        particle = IMPL.MCParticleImpl()
        particle.setPDG(pdg)
        particle.setGeneratorStatus(1)
        particle.setTime(toff)
        particle.setMass(mass)
        particle.setCharge(charge)
        pos = array('d', [x, y, z])
        mom = array('f', [px, py, pz])

        # Creating the particle copies with random Phi rotation
        for iP in range(nW):
            p = IMPL.MCParticleImpl(particle)
            # Rotating position and momentum by random angle in Phi
            dPhi = random.random() * math.pi * 2
            co = math.cos(dPhi)
            si = math.sin(dPhi)
            pos[0] = co * x - si * y
            pos[1] = si * x + co * y
            mom[0] = co * px - si * py
            mom[1] = si * px + co * py
            p.setVertex(pos)
            p.setMomentum(mom)
            # Adding particle to the collection
            col.addElement(p)

        # Updating counters
        nEventLines += 1
        if nEventLines >= args.lines_event:
            nEvents +=1
            nEventLines = 0
            wrt.writeEvent(evt)
            print('Wrote event: {0:d}  (line {1:d})'.format(nEvents, iL+1))

    # Writing the last event
    if nEventLines > 0:
        wrt.writeEvent(evt)
        nEvents += 1
        print('Wrote event: {0:d}'.format(nEvents))

print('Wrote {0:d} events to file: {1:s}'.format(nEvents, args.file_out))
