#!/usr/bin/env python
"""
fluka_to_edm4hep.py
 Convert FLUKA binary file to EDM4HEP file with MCParticles.
 This script incorporates the ability to duplicate & coherently 
 rotate mother-muons to augment BIB statistics.
"""

import os
import argparse
import numpy as np


parser = argparse.ArgumentParser(description='Convert FLUKA binary file to EDM4HEP file with MCParticles')
parser.add_argument('files_in', metavar='FILE_IN', help='Input binary FLUKA file(s)', nargs='+')
parser.add_argument('file_out', metavar='FILE_OUT.edm4hep.root', help='Output EDM4HEP file')
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the header', type=str)
parser.add_argument('-n', '--normalization', metavar='N',  help='Normalization of the generated sample', type=float, default=1.0)
parser.add_argument('-f', '--files_event', metavar='L',  help='Number of files to merge into a single EDM4HEP event (default: 1)', type=int, default=1)
parser.add_argument('-s', '--split', help='Write each mother-muon decay as its own EDM4HEP event, instead of merging all of a file\'s muons into one event', action='store_true', default=False)
parser.add_argument('-m', '--max_lines', metavar='M',  help='Maximum number of lines to process', type=int, default=None)
parser.add_argument('-o', '--overwrite',  help='Overwrite existing output file', action='store_true', default=False)
parser.add_argument('-z', '--invert_z', help='Invert Z position and Z momentum (use for the second beam direction)', action='store_true', default=False)
parser.add_argument('--np_min', metavar='P',  help='Minimum momentum of accepted neutrons [GeV]', type=float, default=None)
parser.add_argument('--t_max', metavar='T',  help='Maximum time of accepted particles [ns]', type=float, default=None)
parser.add_argument('-v', '--verbose', help='Print verbose debug output tracing the program flow', action='store_true', default=False)

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

# Binary format of a single entry: data_formats.py format '2'.
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

# Print a debug message when --verbose is set.
def dbg(msg):
	if args.verbose:
		print(f'[DEBUG] {msg}')

# Human-readable names for the PDG IDs common in BIB, so the debug trace
# says "photon" instead of just "22". Falls back to the raw ID otherwise.
PDG_NAMES = {
	22: 'photon', 11: 'e-', -11: 'e+', 13: 'mu-', -13: 'mu+',
	2112: 'neutron', -2112: 'anti-neutron', 2212: 'proton', -2212: 'anti-proton',
	211: 'pi+', -211: 'pi-', 111: 'pi0', 130: 'K0L', 310: 'K0S',
	321: 'K+', -321: 'K-', 12: 'nu_e', 14: 'nu_mu',
}
def pdg_name(pdg):
	return PDG_NAMES.get(pdg, f'PDG {pdg}')

# Number of copies of one decay to produce for norm factor
# Possibly fractional, uses stochastic rounding
def num_copies():
	whole = math.floor(args.normalization)
	frac = args.normalization - whole
	return int(whole) + (1 if random.random() < frac else 0)

# Add a single rotated copy (index iP of nP) of one mother-muon's secondaries
# into `col`. All secondaries of a given copy share the same rotation, 
# preserving correlations within the decay.
def add_rotated_copy(col, particles, iP, nP):
	dPhi = iP * (2 * math.pi / nP)
	co = math.cos(dPhi)
	si = math.sin(dPhi)
	if iP == 0:
		dbg(f'      copy 1/{nP}: original orientation (no rotation)')
	else:
		dbg(f'      copy {iP+1}/{nP}: rotated by phi = {dPhi:.2f} rad ({iP}/{nP} of 2pi)')
	for pdg, t, mass, charge, px, py, pz, x_mm, y_mm, z_mm in particles:
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
		particle.setVertex(edm4hep.Vector3d(cur_x, cur_y, z_mm))
		particle.setMomentum(edm4hep.Vector3d(cur_px, cur_py, pz))

######################################## Start of the processing
print(f'Converting data from {len(args.files_in)} file(s)\nto EDM4HEP file: {args.file_out:s}\nwith normalization: {args.normalization:.1f}')
if args.split:
	print('Splitting: one event per mother-muon decay')
else:
	print(f'Storing {args.files_event:d} files/event');

dbg('==================== verbose mode ON ====================')
dbg( 'Settings for this run:')
dbg(f'    record size    : {line_dt.itemsize} bytes per particle')
dbg(f'    files / event  : {args.files_event}')
dbg(f'    split mothers  : {"yes (one event per muon)" if args.split else "no"}')
dbg(f'    normalization  : {args.normalization} (copies per muon decay)')
dbg(f'    max lines      : {args.max_lines if args.max_lines else "no limit"}')
dbg(f'    invert z       : {"yes" if args.invert_z else "no"}')
dbg(f'    neutron p min  : {str(args.np_min) + " GeV" if args.np_min is not None else "no cut"}')
dbg(f'    time max       : {str(args.t_max) + " ns" if args.t_max is not None else "no cut"}')
dbg(f'    input files    : {len(args.files_in)}')
for f in (args.files_in if len(args.files_in) <= 5 else args.files_in[:5]):
	dbg(f'        {f}')
if len(args.files_in) > 5:
	dbg(f'        ... and {len(args.files_in) - 5} more')

# Initialize the EDM4HEP file writer
writer = Writer(args.file_out)

# Write a RunHeader
frame = podio.Frame()
frame.put_parameter("InputFiles", len(args.files_in))
frame.put_parameter("Normalization", str(args.normalization))
frame.put_parameter("FilesPerEvent", str(args.files_event))
frame.put_parameter("SplitMothers", str(args.split))

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

# Buffer of particles, grouped by their mother-muon position.
mother_particles = {}

# Reading the complete files
for iF, file_in in enumerate(args.files_in):
	# Creating the EDM4HEP event and collection
	if nEventFiles == 0:
		col = edm4hep.MCParticleCollection()
		evt = podio.Frame()
		evt.put_parameter("eventNumber", str(nEvents))
		# Start each event with an empty particle buffer
		mother_particles = {}
		# Stable "muon #N" labels, indexed in order of appearance
		mother_num = {}
		dbg('')
		dbg(f'=============== EVENT {nEvents} ===============')

	dbg(f'  reading file {iF+1}/{len(args.files_in)}: {os.path.basename(file_in)}')
	file_lines_read = 0
	file_lines_kept = 0


	# Looping over particles from the file
	for iL, data in enumerate(bytes_from_file(file_in)):
		if args.max_lines and nLines >= args.max_lines:
			dbg(f'    (hit max lines = {args.max_lines}, stop reading this file)')
			break
		nLines += 1
		file_lines_read += 1

		# Extracting relevant values from the line
		fid, e, x, y, z, cx, cy, cz, toff, x_mu, y_mu, z_mu = (data[n][0] for n in [
			'fid', 'E',
			'x', 'y', 'z',
			'cx', 'cy', 'cz',
			'time',
			'x_mu', 'y_mu', 'z_mu'
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
			dbg(f'    particle {iL}: {pdg_name(pdg)} SKIPPED - arrives at t={t:.2f} ns (later than t_max={args.t_max} ns)')
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
			dbg(f'    particle {iL}: {pdg_name(pdg)} SKIPPED - momentum {mom_tot:.3g} GeV below np_min {args.np_min} GeV')
			continue

		# Calculating the components of the momentum vector [GeV]
		mom = np.array([cx, cy, cz], dtype=np.float32) * mom_tot

		# Convert position from cm (FLUKA) to mm (EDM4HEP)
		x_mm, y_mm, z_mm = x * 10.0, y * 10.0, z * 10.0
		px, py, pz = float(mom[0]), float(mom[1]), float(mom[2])

		if args.invert_z:
			z_mm *= -1
			pz   *= -1

		# Buffer the particle under its mother-muon decay vertex.
		mother = (float(x_mu), float(y_mu), float(z_mu))
		muon_id = mother_num.setdefault(mother, len(mother_num) + 1)
		mother_particles.setdefault(mother, []).append(
			(pdg, t, mass, charge, px, py, pz, x_mm, y_mm, z_mm))
		file_lines_kept += 1
		dbg(f'    particle {iL}: {pdg_name(pdg)} kept - E={e:.3g} GeV, arrives t={t:.2f} ns, belongs to muon #{muon_id}')

	dbg(f'  file summary: {file_lines_read} read, {file_lines_kept} kept, '
		f'{file_lines_read - file_lines_kept} skipped; '
		f'{len(mother_particles)} muon group(s) buffered so far')

	# Updating counters
	nEventFiles += 1
	if nEventFiles >= args.files_event or iF+1 == len(args.files_in):
		nEventFiles = 0

		if args.split:
			# One event per rotated copy of each mother-muon decay: every copy
			# gets its own frame, so a single decay is never merged with others.
			dbg(f'  building events: one per copy of each mother muon '
				f'({len(mother_particles)} muon(s), ~{args.normalization} copy(ies) each)')
			for mother, particles in mother_particles.items():
				muon_id = mother_num[mother]
				nP = num_copies()
				dbg(f'    muon #{muon_id}: {len(particles)} particle(s) -> {nP} event(s), one per copy')
				for iP in range(nP):
					m_col = edm4hep.MCParticleCollection()
					m_evt = podio.Frame()
					m_evt.put_parameter("eventNumber", str(nEvents))
					add_rotated_copy(m_col, particles, iP, nP)
					n_particles = m_col.size()  # save before move invalidates m_col
					m_evt.put(cppyy.gbl.std.move(m_col), "MCParticles")
					writer.write_frame(m_evt, 'events')
					print(f'Wrote event: {nEvents:d} with {n_particles} particles from mother muon #{muon_id:d} (copy {iP+1}/{nP})')
					nEvents += 1
		else:
			# Legacy mode: all mother muons of this file group merged into a single event
			# (one bunch crossing).
			dbg(f'  building event {nEvents}: {len(mother_particles)} muon group(s), '
				f'making ~{args.normalization} copy(ies) of each')
			for mother, particles in mother_particles.items():
				muon_id = mother_num[mother]
				nP = num_copies()
				dbg(f'    muon #{muon_id}: {len(particles)} particle(s) -> writing {nP} copy(ies)')
				for iP in range(nP):
					add_rotated_copy(col, particles, iP, nP)

			n_particles = col.size()  # save before move invalidates col
			evt.put(cppyy.gbl.std.move(col), "MCParticles")
			writer.write_frame(evt, 'events')
			print(f'Wrote event: {nEvents:d} with {n_particles} particles from {len(mother_particles):d} mother muon(s)')
			nEvents += 1
	
print(f'Wrote {nEvents:d} events to file: {args.file_out:s}')
dbg('')
dbg(f'=============== ALL DONE ===============')
dbg(f'  read {nLines} particle(s) from {len(args.files_in)} file(s), wrote {nEvents} event(s)')
dbg( '  closing output file...')
writer._writer.finish()