#!/usr/bin/env python
"""This script converts a FLUKA binary file to an SLCIO file with LCIO::MCParticle instances"""

from bib_pdgs import FLUKA_PIDS, PDG_PROPS
import math
import random
from pyLCIO import UTIL, EVENT, IMPL, IO, IOIMPL
from array import array
from pdb import set_trace as br
from math import sqrt
import os
import argparse
import numpy as np


parser = argparse.ArgumentParser(
    description='Convert FLUKA binary file to SLCIO file with MCParticles')
parser.add_argument('files_in', metavar='FILE_IN',
                    help='Input binary FLUKA file(s)', nargs='+')
parser.add_argument('file_out', metavar='FILE_OUT.slcio',
                    help='Output SLCIO file')
parser.add_argument('-c', '--comment', metavar='TEXT',
                    help='Comment to be added to the header', type=str)
parser.add_argument('-b', '--bx_time', metavar='TIME',
                    help='Time of the bunch crossing [ns]', type=float, default=0.)
parser.add_argument('-n', '--normalization', metavar='N',
                    help='Normalization of the generated sample', type=float, default=1.0)
parser.add_argument('-f', '--files_event', metavar='L',
                    help='Number of files to merge into a single LCIO event (default: 1)', type=int, default=1)
parser.add_argument('-i', '--invert_z', metavar='I',
                    help='Invert to simulate mu- beam (default: 0)', type=int, default=0)
parser.add_argument('-m', '--max_lines', metavar='M',
                    help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file',
                    action='store_true', default=False)
parser.add_argument('--pdgs', metavar='ID',
                    help='PDG IDs of particles to be included', type=int, default=None, nargs='+')
parser.add_argument('--nopdgs', metavar='ID',
                    help='PDG IDs of particles to be excluded', type=int, default=None, nargs='+')
parser.add_argument('--ne_min', metavar='E',
                    help='Minimum energy of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('--t_max', metavar='T',
                    help='Maximum time of accepted particles [ns]', type=float, default=None)

args = parser.parse_args()

if not args.overwrite and os.path.isfile(args.file_out):
    raise FileExistsError(f'Output file already exists: {args.file_out:s}')


def bytes_from_file(filename):
    with open(filename, 'rb') as f:
        while True:
            chunk = np.fromfile(f, dtype=line_dt, count=1)
            if not len(chunk):
                return
            yield chunk


# Binary format of a single entry
'''
line_dt = np.dtype([
    ('fid',  np.int32),
    ('fid_mo',  np.int32),
    ('E', np.float64),
    ('x', np.float64),
    ('y', np.float64),
    ('z', np.float64),
    ('cx', np.float64),
    ('cy', np.float64),
    ('cz', np.float64),
    ('time', np.float64),
    ('x_mu', np.float64),
    ('y_mu', np.float64),
    ('z_mu', np.float64),
    ('x_mo', np.float64),
    ('y_mo', np.float64),
    ('z_mo', np.float64),
    ('px_mo', np.float64),
    ('py_mo', np.float64),
    ('pz_mo', np.float64),
    ('age_mo', np.float64)
])
'''
line_dt=np.dtype([
    ('fid',  np.int32),
    ('fid_mo',  np.int32),
    ('E', np.float64),
    ('x', np.float64),
    ('y', np.float64),
    ('z', np.float64),
    ('cx', np.float64),
    ('cy', np.float64),
    ('cz', np.float64),
    ('time', np.float64)
])

# Start of the processing
print(
    f'Converting data from {len(args.files_in)} file(s)\nto SLCIO file: {args.file_out:s}\nwith normalization: {args.normalization:.1f}')
print(f'Storing {args.files_event:d} files/event')
if args.pdgs is not None:
    print(f'Will only use particles with PDG IDs: {args.pdgs}')

# Initialize the LCIO file writer
wrt = IOIMPL.LCFactory.getInstance().createLCWriter()
wrt.open(args.file_out, EVENT.LCIO.WRITE_NEW)

# Write a RunHeader
run = IMPL.LCRunHeaderImpl()
run.setRunNumber(0)
run.parameters().setValue('InputFiles', len(args.files_in))
run.parameters().setValue('Normalization', args.normalization)
run.parameters().setValue('BXTime', args.bx_time)
run.parameters().setValue('FilesPerEvent', args.files_event)
if args.t_max:
    run.parameters().setValue('Time_max', args.t_max)
if args.ne_min:
    run.parameters().setValue('NeutronEnergy_min', args.ne_min)
if args.pdgs:
    run.parameters().setValue('PdgIds', str(args.pdgs))
if args.nopdgs:
    run.parameters().setValue('NoPdgIds', args.nopdgs)
if args.comment:
    run.parameters().setValue('Comment', args.comment)
wrt.writeRunHeader(run)

# Bookkeeping variables
random.seed()
nEventFiles = 0
nLines = 0
nEvents = 0
col = None
evt = None

# Reading the complete files
for iF, file_in in enumerate(args.files_in):
    # Creating the LCIO event and collection
    if nEventFiles == 0:
        col = IMPL.LCCollectionVec(EVENT.LCIO.MCPARTICLE)
        evt = IMPL.LCEventImpl()

        evt.setEventNumber(nEvents)
        evt.addCollection(col, 'MCParticle')
    # Looping over particles from the file
    for iL, data in enumerate(bytes_from_file(file_in)):
        if args.max_lines and nLines >= args.max_lines:
            break

        # Extracting relevant values from the line
        #fid, e, x, y, z, cx, cy, cz, time = (data[n][0] for n in [
        fid,e_kin, x,y,z, cx,cy,cz, time = (data[n][0] for n in [
            'fid', 'E',
            'x', 'y', 'z',
            'cx', 'cy', 'cz', 'time'
        ])

        # Converting FLUKA ID to PDG ID
        try:
            pdg = FLUKA_PIDS[fid]
        except KeyError:
            print(f'WARNING: Unknown PDG ID for FLUKA ID: {fid}')
            continue

        # Calculating the absolute time of the particle [ns]
        t = time*1.E9 - args.bx_time

        # Skipping if particle's time is greater than allowed
        if args.t_max is not None and t > args.t_max:
            continue

        # Calculating the components of the momentum vector
        #mom = np.array([cx, cy, cz], dtype=np.float32)
        #mom *= e

        # Skipping if it's a neutron with too low kinetic energy
        # if args.ne_min is not None and abs(pdg) == 2112 and np.linalg.norm(mom) < args.ne_min:
        if args.ne_min is not None and abs(pdg) == 2112 and e_kin < args.ne_min:
            continue

        # Getting the charge and mass of the particle
        if pdg not in PDG_PROPS:
            print(
                'WARNING! No properties defined for PDG ID: {0:d}'.format(pdg))
            print('         Skpping the particle...')
            continue
        charge, mass = PDG_PROPS[pdg]

		# Calculating the components of the momentum vector from the kinetic energy
        mom_tot = sqrt(e_kin**2 + 2 * e_kin * mass)
        mom = np.array([cx, cy, cz], dtype=np.float32)
        mom *= mom_tot

        # Calculating how many random copies of the particle to create according to the weight
        nP_frac, nP = math.modf(args.normalization)
        if nP_frac > 0 and random.random() < nP_frac:
            nP += 1
        nP = int(nP)

        # Creating the particle with original parameters
        particle = IMPL.MCParticleImpl()
        particle.setPDG(pdg)
        particle.setGeneratorStatus(1)
        particle.setTime(t)
        particle.setMass(mass)
        particle.setCharge(charge)
        pos = np.array([x*10, y*10, z*10], dtype=np.float64)

        if args.invert_z:
            pos[2] = -pos[2]
            mom[2] = -mom[2]

        # Creating the particle copies with random Phi rotation
        px, py, pz = mom
        for i, iP in enumerate(range(nP)):
            p = IMPL.MCParticleImpl(particle)
            # Rotating position and momentum of the copies by a random angle in Phi
            if i > 0:
                dPhi = random.random() * math.pi * 2
                co = math.cos(dPhi)
                si = math.sin(dPhi)
                pos[0] = co * x*10 - si * y*10
                pos[1] = si * x*10 + co * y*10
                mom[0] = co * px - si * py
                mom[1] = si * px + co * py
            p.setVertex(pos)
            p.setMomentum(mom)
            # Adding particle to the collection
            col.addElement(p)

    # Updating counters
    nEventFiles += 1
    if nEventFiles >= args.files_event or iF+1 == len(args.files_in):
        nEvents += 1
        nEventFiles = 0
        wrt.writeEvent(evt)
        print(
            f'Wrote event: {nEvents:d} with {col.getNumberOfElements()} particles')

print(f'Wrote {nEvents:d} events to file: {args.file_out:s}')
wrt.close()
