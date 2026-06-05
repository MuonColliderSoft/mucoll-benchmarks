#!/usr/bin/env python
"""This script converts a FLUKA binary file to an SLCIO file with LCIO::MCParticle instances"""

import os
import argparse

parser = argparse.ArgumentParser(description='Convert FLUKA binary file to SLCIO file with MCParticles')
parser.add_argument('files_in', metavar='FILE_IN', help='Input binary FLUKA file(s)', nargs='+')
parser.add_argument('file_out', metavar='FILE_OUT.slcio', help='Output SLCIO file')
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the header', type=str)
parser.add_argument('-n', '--normalization', metavar='N',  help='Normalization of the generated sample', type=float, default=1.0)
parser.add_argument('-f', '--files_event', metavar='L',  help='Number of files to merge into a single LCIO event (default: 1)', type=int, default=1)
parser.add_argument('-l', '--lines_event', metavar='L',  help='Number of lines to merge into a single LCIO event (default: -1)', type=int, default=-1)
parser.add_argument('-m', '--max_lines', metavar='M',  help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file', action='store_true', default=False)
parser.add_argument('-v', '--version', metavar='VER',  help='Version of the FLUKA input format', type=str, required=True)
parser.add_argument('-z', '--invert_z',  help='Invert Z position/momentum', action='store_true', default=False)
parser.add_argument('--pdgs', metavar='ID',  help='PDG IDs of particles to be included', type=int, default=None, nargs='+')
parser.add_argument('--nopdgs', metavar='ID',  help='PDG IDs of particles to be excluded', type=int, default=None, nargs='+')
parser.add_argument('--np_min', metavar='E',  help='Minimum momentum of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('--t_max', metavar='T',  help='Maximum time of accepted particles [ns]', type=float, default=None)

args = parser.parse_args()

if not args.overwrite and os.path.isfile(args.file_out):
	raise FileExistsError(f'Output file already exists: {args.file_out:s}')


from math import sqrt
from pdb import set_trace as br
from array import array
from pyLCIO import UTIL, EVENT, IMPL, IO, IOIMPL

import random
import math
import numpy as np

from bib_pdgs import FLUKA_PIDS, PDG_PROPS
from data_formats import DATA_FORMATS

# Validating the FLUKA format version
if not args.version in DATA_FORMATS:
	raise LookupError(f'Unknown FLUKA format version: `{args.version}`\nSupported formats are: {list(DATA_FORMATS.keys())}')
# Defining the binary format of a single entry
line_dt = DATA_FORMATS[args.version]


def bytes_from_file(filename):
	"""Function to read a binary file into enumeratable list of values"""
	with open(filename, 'rb') as f:
		while True:
			chunk = np.fromfile(f, dtype=line_dt, count=1)
			if not len(chunk):
				return
			yield chunk


######################################## Start of the processing
print(f'Converting data from {len(args.files_in)} file(s)\n to SLCIO file: {args.file_out:s}\n with normalization: {args.normalization:.1f}')
print(f'Splitting into {args.files_event:d} files/event and {args.lines_event:d} particles/event');
if args.pdgs is not None:
	print(f'Will only use particles with PDG IDs: {args.pdgs}')

# Initialize the LCIO file writer
wrt = IOIMPL.LCFactory.getInstance().createLCWriter()
wrt.open(args.file_out, EVENT.LCIO.WRITE_NEW)

# Write a RunHeader
run = IMPL.LCRunHeaderImpl()
run.setRunNumber(0)
run.parameters().setValue('NInputFiles', len(args.files_in))
run.parameters().setValue('Normalization', args.normalization)
run.parameters().setValue('FilesPerEvent', args.files_event)
if args.t_max:
	run.parameters().setValue('Time_max', args.t_max)
if args.np_min:
	run.parameters().setValue('NeutronMomentum_min', args.np_min)
if args.pdgs:
	run.parameters().setValue('PdgIds', str(args.pdgs))
if args.nopdgs:
	run.parameters().setValue('NoPdgIds', str(args.nopdgs))
if args.comment:
	run.parameters().setValue('Comment', args.comment)
wrt.writeRunHeader(run)

# Bookkeeping variables
random.seed()
nEventFiles = 0
nEventLines = 0
nLines = 0
nEvents = 0
newEvent = True
col = None
evt = None

# Reading the complete files
for iF, file_in in enumerate(args.files_in):
	if args.max_lines and nLines >= args.max_lines:
		break
	# Looping over entries in the file
	for iL, data in enumerate(bytes_from_file(file_in)):
		if args.max_lines and nLines >= args.max_lines:
			break
		nLines += 1
	
		# Creating the LCIO event and collection if starting a new output event
		if newEvent:
			# Writing the current event
			if nEventLines > 0:
				wrt.writeEvent(evt)
				print(f'Wrote event: {nEvents:d} with {col.getNumberOfElements()} particles')
				nEvents += 1
			# Resetting counters
			newEvent = False
			nEventLines = 0
			nEventFiles = 0
			# Creating a new event
			col = IMPL.LCCollectionVec(EVENT.LCIO.MCPARTICLE)
			evt = IMPL.LCEventImpl()
			evt.setEventNumber(nEvents)
			evt.addCollection(col, 'MCParticle')

		# Extracting relevant values from the entry
		# Names should match the ones in FLUKA_FORMATS
		fid, e_kin, x,y,z, cx,cy,cz, time = (data[n][0] for n in [
			'fid', 'e_kin',
			'x','y','z',
			'cx', 'cy', 'cz',
			'time'
		])

		# Converting FLUKA ID to PDG ID
		try:
			pdg = FLUKA_PIDS[fid]
		except KeyError:
			print(f'WARNING: Unknown PDG ID for FLUKA ID: {fid}')
			continue

		# Converting the absolute time of the particle [s -> ns]
		t = time * 1e9

		# Skipping if particle's time is greater than allowed
		if args.t_max is not None and t > args.t_max:
			continue

		# Getting the charge and mass of the particle
		if pdg not in PDG_PROPS:
			print('WARNING! No properties defined for PDG ID: {0:d}'.format(pdg))
			print('         Skipping the particle...')
			continue
		charge, mass = PDG_PROPS[pdg]

		# Calculating the momentum vector
		mom_tot = sqrt(e_kin**2 + 2 * e_kin * mass)
		# Skipping if it's a neutron with too low momentum
		if args.np_min is not None and abs(pdg) == 2112 and mom_tot < args.np_min:
			continue
		mom = np.array([cx, cy, cz], dtype=np.float32) * mom_tot

		# Calculating the position vector [cm -> mm]
		pos = np.array([x, y, z], dtype=np.float64) * 10.0

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

		# Inverting Z position/momentum (if requested)
		if args.invert_z:
			pos[2] *= -1
			mom[2] *= -1

		# Creating the particle copies with random Phi rotation
		px, py, pz = mom
		x, y, z = pos
		for i, iP in enumerate(range(nP)):
			p = IMPL.MCParticleImpl(particle)
			# Rotating position and momentum vectors by a random angle in Phi
			if nP > 1:
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

		# Checking line counters
		nEventLines += 1
		if args.lines_event > 0 and nEventLines >= args.lines_event:
			newEvent = True
	# Checking file counters
	nEventFiles += 1
	if args.files_event > 0 and nEventFiles >= args.files_event:
		newEvent = True

# Writing the last event
if nEventLines > 0:
	wrt.writeEvent(evt)
	print(f'Wrote event: {nEvents:d} with {col.getNumberOfElements()} particles')
	nEvents += 1

print(f'+ Finished writing {nEvents:d} events to file: {args.file_out:s}')
wrt.close()
