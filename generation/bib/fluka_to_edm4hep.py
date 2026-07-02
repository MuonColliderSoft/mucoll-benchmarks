#!/usr/bin/env python
"""Convert a FLUKA binary file to an EDM4HEP file with MCParticle instances."""

import os
import argparse
import numpy as np


parser = argparse.ArgumentParser(description='Convert FLUKA binary file to EDM4HEP file with MCParticles')
parser.add_argument('files_in', metavar='FILE_IN', help='Input binary FLUKA file(s)', nargs='+')
parser.add_argument('file_out', metavar='FILE_OUT.edm4hep.root', help='Output EDM4HEP file')
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the header', type=str)
parser.add_argument('-b', '--bx_time', metavar='TIME',  help='Time of the bunch crossing [s]', type=float, default=0.0)
parser.add_argument('-n', '--normalization', metavar='N',  help='Normalization of the generated sample', type=float, default=1.0)
parser.add_argument('-f', '--files_event', metavar='L',  help='Number of files to merge into a single EDM4HEP event (default: 1)', type=int, default=1)
parser.add_argument('-m', '--max_lines', metavar='M',  help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file', action='store_true', default=False)
parser.add_argument('-z', '--invert_z', help='Invert Z position and Z momentum (use for the second beam direction)', action='store_true', default=False)
parser.add_argument('--np_min', metavar='P',  help='Minimum momentum of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('--t_max', metavar='T',  help='Maximum time of accepted particles [ns]', type=float, default=None)

args = parser.parse_args()

if not args.overwrite and os.path.isfile(args.file_out):
	raise FileExistsError(f'Output file already exists: {args.file_out:s}')


import edm4hep
import podio
from podio.root_io import Writer
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

# Binary format of a single entry, as specified in data_formats.py
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
	('age', np.float64),
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

######################################## Start of the processing
print(f'Converting data from {len(args.files_in)} file(s)\nto EDM4HEP file: {args.file_out:s}\nwith normalization: {args.normalization:.1f}')
print(f'Storing {args.files_event:d} files/event');

# Initialize the EDM4HEP file writer
writer = Writer(args.file_out)

# Write a RunHeader
frame = podio.Frame()
frame.put_parameter("InputFiles", len(args.files_in))
frame.put_parameter("Normalization", str(args.normalization))
frame.put_parameter("BXTime", str(args.bx_time))
frame.put_parameter("FilesPerEvent", str(args.files_event))

if args.t_max:
	frame.put_parameter("Time_max", str(args.t_max))
if args.np_min:
	frame.put_parameter("NeutronMomentum_min", str(args.np_min))
if args.comment:
	frame.put_parameter("Comment", str(args.comment))
if args.invert_z:
	frame.put_parameter("InvertZ", "True")

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
		nLines += 1

		# Extracting relevant values from the line
		fid, e, x, y, z, cx, cy, cz, toff = (data[n][0] for n in [
			'fid', 'E',
			'x', 'y', 'z',
			'cx', 'cy', 'cz',
			'age'
		])

		# Converting FLUKA ID to PDG ID
		try:
			pdg = FLUKA_PIDS[fid]
		except KeyError:
			print(f'WARNING: Unknown PDG ID for FLUKA ID: {fid}')
			continue

		# Calculating the absolute time of the particle [ns]
		t = toff * 1e9

		# Skipping if particle's time is greater than allowed
		if args.t_max is not None and t > args.t_max:
			continue

		# Getting the charge and mass of the particle
		if pdg not in PDG_PROPS:
			print('WARNING! No properties defined for PDG ID: {0:d}'.format(pdg))
			print('         Skipping the particle...')
			continue
		charge, mass = PDG_PROPS[pdg]

		# Calculating the total momentum from the kinetic energy [GeV]
		mom_tot = math.sqrt(e**2 + 2 * e * mass)

		# Skipping if it's a neutron with too low momentum
		if args.np_min is not None and abs(pdg) == 2112 and mom_tot < args.np_min:
			continue

		# Calculating the components of the momentum vector [GeV]
		mom = np.array([cx, cy, cz], dtype=np.float32) * mom_tot

		# Calculating how many random copies of the particle to create according to the weight
		nP_frac, nP = math.modf(args.normalization)
		if nP_frac > 0 and random.random() < nP_frac:
			nP += 1
		nP = int(nP)

		# Convert position from cm (FLUKA) to mm (EDM4HEP)
		x_mm, y_mm, z_mm = x * 10.0, y * 10.0, z * 10.0
		px, py, pz = float(mom[0]), float(mom[1]), float(mom[2])

		if args.invert_z:
			z_mm *= -1
			pz   *= -1

		# Create one collection entry per copy, each with a random Phi rotation
		for iP in range(nP):
			cur_x, cur_y, cur_z = x_mm, y_mm, z_mm
			cur_px, cur_py, cur_pz = px, py, pz
			if nP > 1:
				dPhi = random.random() * math.pi * 2
				co = math.cos(dPhi)
				si = math.sin(dPhi)
				cur_x = co * x_mm - si * y_mm
				cur_y = si * x_mm + co * y_mm
				cur_px = co * px - si * py
				cur_py = si * px + co * py
			particle = col.create()
			particle.setPDG(pdg)
			particle.setGeneratorStatus(1)
			particle.setTime(t)
			particle.setMass(mass)
			particle.setCharge(charge)
			particle.setVertex(edm4hep.Vector3d(cur_x, cur_y, cur_z))
			particle.setMomentum(edm4hep.Vector3d(cur_px, cur_py, cur_pz))

	# Updating counters
	nEventFiles += 1
	if nEventFiles >= args.files_event or iF+1 == len(args.files_in):
		nEvents += 1
		nEventFiles = 0
		n_particles = col.size()  # save before move invalidates col
		evt.put(cppyy.gbl.std.move(col), "MCParticles")
		writer.write_frame(evt, 'events')
		print(f'Wrote event: {nEvents:d} with {n_particles} particles')
	
print(f'Wrote {nEvents:d} events to file: {args.file_out:s}')

writer._writer.finish()