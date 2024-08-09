#!/usr/bin/env python
"""
This script generates a file with LCIO::MCParticles of specified parameters

Most --arguments support three kinds of inputs:
 * `value` - the same value will be used for each particle
 * `min max` - a random value in the range [min; max) will be used for each particle
 * `0 mean sigma` - a random value sampled from a gaussian distribution will be used for each particle
"""

import os
import argparse

parser = argparse.ArgumentParser(description='Generate LCIO::MCParticles with specified parameters')
parser.add_argument('output', metavar='FILE_OUT.slcio', help='Output LCIO file')
parser.add_argument('-s', '--seed', metavar='seed', type=int, help='Seed to use for random generator', default=12345)
parser.add_argument('-c', '--comment', metavar='TEXT',  help='Comment to be added to the run header', type=str)
parser.add_argument('-e', '--events', metavar='N', type=int, default=1,  help='# of events to generate (default: 1)')
parser.add_argument('-p', '--particles', metavar='N', type=int, default=1,  help='# of particles/event to generate (default: 1)')
parser.add_argument('-o', '--overwrite', action='store_true',  help='Overwrite existing output file')
parser.add_argument('--pdg', metavar='ID', type=int, default=[13], nargs='+',  help='PdgIds of the allowed particles (default: [13])')
parser.add_argument('--dt', metavar='V', type=float, nargs='*', default=0,  help='Time offset [ns] (default: 0)')
parser.add_argument('--dz', metavar='V', type=float, nargs='*', default=0,  help='Vertex position along Z [mm] (default: 0)')
parser.add_argument('--d0', metavar='V', type=float, nargs='*', default=0,  help='Vertex position along R [mm] (default: 0)')
parser.add_argument('--pt', metavar='V', type=float, nargs='*',  help='Tranverse momentum [GeV]')
parser.add_argument('--p', metavar='V', type=float, nargs='*',  help='Total momentum [GeV]')
parser.add_argument('--theta', metavar='A', type=float, default=[90], nargs='+',  help='Polar angle [deg] (default: 90)')
parser.add_argument('--phi', metavar='A', type=float, default=[0,360], nargs='+',  help='Azimuthal angle [deg] (default: random)')

args = parser.parse_args()


from pyLCIO import UTIL, EVENT, IMPL, IO, IOIMPL
from pdgs import PDG_PROPS
from array import array
import numpy as np
import math

# Validating the arguments
if not args.overwrite and os.path.isfile(args.output):
	raise FileExistsError(f'Output file already exists: {args.output:s}')
if (args.pt is None and args.p is None) or (args.pt is not None and args.p is not None):
	raise RuntimeError('Exactly one of --pt or --p has to be specified')
for pdg in args.pdg:
	if pdg not in PDG_PROPS:
		raise RuntimeError(f'Particle properties not defined for pdgId: {pdg}')


# Generating sampling distributions for each property (1 value/event)
sample_size = args.events * args.particles
rng = np.random.default_rng(args.seed)
samples = {}
configs = {
	'dt': args.dt,
	'dz': args.dz,
	'd0': args.d0,
	# Converting degrees to radians
	'theta': [math.radians(a) for a in args.theta],
	'phi': [math.radians(a) for a in args.phi]
}
if args.pt is not None:
	configs['pt'] = args.pt
else:
	configs['p'] = args.p
for name, values in configs.items():
	if values is None:
		continue
	if not isinstance(values, list):
		samples[name] = np.ones(sample_size) * values
	elif len(values) == 1:
		samples[name] = np.ones(sample_size) * values[0]
	elif len(values) == 2:
		samples[name] = rng.random(sample_size) * (values[1] - values[0]) + values[0]
	elif len(values) == 3:
		samples[name] = np.random.normal(values[1], values[2], sample_size)
# Adding randomised phi angle for d0 (independent from the particle's direction)
samples['dphi'] = rng.random(sample_size) * math.pi * 2.

# Opening the output file
wrt = IOIMPL.LCFactory.getInstance().createLCWriter( )
wrt.open( args.output , EVENT.LCIO.WRITE_NEW )
print(f'Opening output file: {args.output}')

# Writing the run headers
run = IMPL.LCRunHeaderImpl()
run.setRunNumber(0)
run.parameters().setValue('pdgIds', str(args.pdg))
run.parameters().setValue('events', args.events)
run.parameters().setValue('particles/event', args.particles)
if args.comment:
	run.parameters().setValue('comment', args.comment)
for name, values in configs.items():
	header = str(values) if isinstance(values, list) else values
	run.parameters().setValue(name, header)
wrt.writeRunHeader(run)

# Setting counters
n_events = 0
n_particles = 0

# Choosing pdgId of each particle randomly if # of pdgIds is different from # of particles/event
n_pdgs = len(args.pdg)
choose_random_pdg = True if args.particles != n_pdgs else False
# Creating actual particles
for e in range(args.events):
	col = IMPL.LCCollectionVec(EVENT.LCIO.MCPARTICLE)
	evt = IMPL.LCEventImpl()
	evt.setEventNumber(e)
	evt.setRunNumber(run.getRunNumber())
	evt.addCollection(col, "MCParticle")
	for p in range(args.particles):
		s = e*args.particles + p
		pdg_idx = p
		if choose_random_pdg:
			pdg_idx = np.random.choice(n_pdgs, 1)[0]
		pdg = args.pdg[pdg_idx]
		# Calculating all properties for this particle in the event
		theta = samples['theta'][s]
		phi = samples['phi'][s]
		dt = samples['dt'][s]
		# Calculating momentum vector
		if 'pt' in configs:
			pt = samples['pt'][s]
			px = pt * math.cos(phi)
			py = pt * math.sin(phi)
			pz = pt / math.tan(theta)
		elif 'p' in configs:
			p = samples['p'][s]
			px = p * math.cos(phi) * math.sin(theta)
			py = p * math.sin(phi) * math.sin(theta)
			pz = p * math.cos(theta)
		momentum = array('f', [px, py, pz])
		# Calculating vertex position
		vx = samples['d0'][s] * math.cos(samples['dphi'][s])
		vy = samples['d0'][s] * math.sin(samples['dphi'][s])
		vz = samples['dz'][s]
		vtx = array('d', [vx, vy, vz])
		# Assigning properties to the MCParticle
		mcp = IMPL.MCParticleImpl()
		mcp.setGeneratorStatus(1)
		mcp.setMass(PDG_PROPS[pdg][1])
		mcp.setCharge(PDG_PROPS[pdg][0])
		mcp.setPDG(pdg)
		mcp.setMomentum(momentum)
		mcp.setVertex(vtx)
		mcp.setTime(dt)
		# Adding particle to the event
		col.addElement(mcp)
		n_particles += 1
	# Writing the event
	wrt.writeEvent(evt)
	n_events += 1
	if n_events % (args.events / 10) == 0:
		print(f'Wrote event {n_events}/{args.events}')
# Closing the output file
wrt.close()
print(f'Wrote {n_particles} partiles in {n_events} events to file: {args.output}')

