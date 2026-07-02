"""Definitions of different versions of the binary FLUKA output formats"""

import numpy as np

# Format definitions of the FLUKA-generated Beam Induced Background (BIB) samples
DATA_FORMATS = {
	# Kinematics of the BIB particle + mother particle + position of the muon decay
	'1': np.dtype([
		('fid',    np.int32),
		('fid_mo', np.int32),
		('e_kin',  np.float64),
		('x',      np.float64),
		('y',      np.float64),
		('z',      np.float64),
		('cx',     np.float64),
		('cy',     np.float64),
		('cz',     np.float64),
		('time',   np.float64),
		('x_mu',   np.float64),
		('y_mu',   np.float64),
		('z_mu',   np.float64),
		('x_mo',   np.float64),
		('y_mo',   np.float64),
		('z_mo',   np.float64),
		('px_mo',  np.float64),
		('py_mo',  np.float64),
		('pz_mo',  np.float64),
		('age_mo', np.float64)
		]),
	# No info about the mother particle
	'2': np.dtype([
		('fid',    np.int32),
		('fid_mo', np.int32),
		('e_kin',  np.float64),
		('x',      np.float64),
		('y',      np.float64),
		('z',      np.float64),
		('cx',     np.float64),
		('cy',     np.float64),
		('cz',     np.float64),
		('time',   np.float64),
		('x_mu',   np.float64),
		('y_mu',   np.float64),
		('z_mu',   np.float64)
	]),
	# Added back kinematics of the mother particle, w/o age
	'3': np.dtype([
		('fid',    np.int32),
		('fid_mo', np.int32),
		('e_kin',  np.float64),
		('x',      np.float64),
		('y',      np.float64),
		('z',      np.float64),
		('cx',     np.float64),
		('cy',     np.float64),
		('cz',     np.float64),
		('time',   np.float64),
		('x_mu',   np.float64),
		('y_mu',   np.float64),
		('z_mu',   np.float64),
		('x_mo',   np.float64),
		('y_mo',   np.float64),
		('z_mo',   np.float64),
		('px_mo',  np.float64),
		('py_mo',  np.float64),
		('pz_mo',  np.float64)
	]),

	# Format definitions of the Incoherent Pair Production (IPP) samples generated with Guinea Pig
	'ip1': np.dtype([
		('fid',    np.int32),
		('fid_mo', np.int32),
		('e_kin',  np.float64),
		('x',      np.float64),
		('y',      np.float64),
		('z',      np.float64),
		('cx',     np.float64),
		('cy',     np.float64),
		('cz',     np.float64),
		('time',   np.float64)
	])
}