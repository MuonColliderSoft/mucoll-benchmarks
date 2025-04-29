#!/usr/bin/env python
"""This script converts a FLUKA binary file to an ROOT file with EDM4HEP::MCParticle instances"""

import os
import argparse
import numpy as np


parser = argparse.ArgumentParser(description='Convert FLUKA binary file to ROOT file with MCParticles')
parser.add_argument('files_in', metavar='FILE_IN', help='Input binary FLUKA file(s)', nargs='+')
parser.add_argument('file_out', metavar='FILE_OUT.root', help='Output ROOT file')
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the header', type=str)
parser.add_argument('-b', '--bx_time', metavar='TIME',  help='Time of the bunch crossing [s]', type=float, default=0.0)
parser.add_argument('-n', '--normalization', metavar='N',  help='Normalization of the generated sample', type=float, default=1.0)
parser.add_argument('-f', '--files_event', metavar='L',  help='Number of files to merge into a single LCIO event (default: 1)', type=int, default=1)
parser.add_argument('-m', '--max_lines', metavar='M',  help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file', action='store_true', default=False)
parser.add_argument('-z', '--invert_z',  help='Invert Z position/momentum', action='store_true', default=False)
parser.add_argument('--pdgs', metavar='ID',  help='PDG IDs of particles to be included', type=int, default=None, nargs='+')
parser.add_argument('--nopdgs', metavar='ID',  help='PDG IDs of particles to be excluded', type=int, default=None, nargs='+')
parser.add_argument('--ne_min', metavar='E',  help='Minimum energy of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('--t_max', metavar='T',  help='Maximum time of accepted particles [ns]', type=float, default=None)

args = parser.parse_args()

if not args.overwrite and os.path.isfile(args.file_out):
	raise FileExistsError(f'Output file already exists: {args.file_out:s}')


from math import sqrt
from pdb import set_trace as br
from array import array

import edm4hep
import podio
import cppyy


import random
import math

from bib_pdgs import FLUKA_PIDS, PDG_PROPS

def bytes_from_file(filename):
	with open(filename, 'rb') as f:
		while True:
			chunk = np.fromfile(f, dtype=line_dt, count=1)
			if not len(chunk):
				return
			yield chunk

# Binary format of a single entry
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
    ('time', np.float64),
    ('x_mu', np.float64),
	('y_mu', np.float64),
    ('z_mu', np.float64)
])

######################################## Start of the processing
print(f'Converting data from {len(args.files_in)} file(s)\nto ROOT file: {args.file_out:s}\nwith normalization: {args.normalization:.1f}')
print(f'Storing {args.files_event:d} files/event');
if args.pdgs is not None:
	print(f'Will only use particles with PDG IDs: {args.pdgs}')

# Initialize the EDM4HEP file writer
writer = podio.root_io.Writer(args.file_out)

# Write a RunHeader
frame = podio.Frame()
frame.put_parameter("InputFiles", len(args.files_in))
frame.put_parameter("Normalization", str(args.normalization))
frame.put_parameter("BXTime", str(args.bx_time))
frame.put_parameter("FilesPerEvent", str(args.files_event))

if args.t_max:
	frame.put_parameter("Time_max", str(args.t_max))
if args.ne_min:
	frame.put_parameter("NeutronEnergy_min", str(args.ne_min))
if args.pdgs:
	frame.put_parameter("PdgIds", str(args.pdgs))
if args.nopdgs:
	frame.put_parameter("NoPdgIds", str(args.nopdgs))
if args.comment:
	frame.put_parameter("Comment", str(args.comment))

writer.write_frame(frame, 'header')
	
# Bookkeeping variables
random.seed()
nEventFiles = 0
nLines = 0
nEvents = 0
col = None
evt = None

# Reading the complete files
for iF, file_in in enumerate(args.files_in):
	# Creating the EDM4HEP event and collection
	if nEventFiles == 0:
		col = edm4hep.MCParticleCollection()
		evt = podio.Frame()
		evt.put_parameter("eventNumber", str(nEvents))

	# Looping over particles from the file
	for iL, data in enumerate(bytes_from_file(file_in)):
		if args.max_lines and nLines >= args.max_lines:
			break

		# Extracting relevant values from the line
		fid,e, x,y,z, cx,cy,cz, time = (data[n][0] for n in [
			'fid', 'E',
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

		# Calculating the absolute time of the particle [ns]
		t = time * 1e9

		# Converting the len units from cm to mm
		x = x * 10
		y = y * 10
		z = z * 10

		# Skipping if particle's time is greater than allowed
		if args.t_max is not None and t > args.t_max:
			continue

		# Calculating the components of the momentum vector
		mom = edm4hep.Vector3d(cx *e, cy *e, cz *e)

		# Skipping if it's a neutron with too low kinetic energy
		if args.ne_min is not None and abs(pdg) == 2112 and (mom.x**2+mom.y**2+mom.z**2) < args.ne_min:
			continue

		# Getting the charge and mass of the particle
		if pdg not in PDG_PROPS:
			print('WARNING! No properties defined for PDG ID: {0:d}'.format(pdg))
			print('         Skpping the particle...')
			continue
		charge, mass = PDG_PROPS[pdg]

		# Calculating how many random copies of the particle to create according to the weight
		nP_frac, nP = math.modf(args.normalization)
		if nP_frac > 0 and random.random() < nP_frac:
			nP += 1
		nP = int(nP)
		
		# Creating the particle with original parameters
		#particle = edm4hep.MutableMCParticle() 
		particle = col.create()
		particle.setPDG(pdg)
		particle.setGeneratorStatus(1)
		particle.setTime(t)
		particle.setMass(mass)
		particle.setCharge(charge)
		pos = edm4hep.Vector3d(x, y, z)

		# Inverting Z position/momentum (if requested)
		if args.invert_z:
			pos.z *= -1
			mom.z *= -1

		particle.setVertex(pos)
		particle.setMomentum(mom)
		# Creating the particle copies with random Phi rotation
		for i, iP in enumerate(range(nP)):
			# Rotating position and momentum of the copies by a random angle in Phi
			if i > 0:
				particle = col.create()
				dPhi = random.random() * math.pi * 2
				co = math.cos(dPhi)
				si = math.sin(dPhi)
				pos.x = co * x - si * y
				pos.y = si * x + co * y
				mom.x = co * mom.x - si * mom.y
				mom.y = si * mom.x + co * mom.y
				particle.setVertex(pos)
				particle.setMomentum(mom)
                                
	if nEventFiles >= args.files_event or iF+1 == len(args.files_in):
		nEvents +=1
		nEventFiles = 0
		print(f'Writing event: {nEvents:d} with {col.size()} particles')
		evt.put(cppyy.gbl.std.move(col), "MCParticles")
		writer.write_frame(evt, 'events')
	
print(f'Wrote {nEvents:d} events to file: {args.file_out:s}')

