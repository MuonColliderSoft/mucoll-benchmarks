#!/bin/env python3

from pyLCIO.drivers.Driver import Driver
from pyLCIO import EVENT, UTIL

import ROOT as R
import numpy as np
import math
import argparse
from utils import get_oldest_mcp_parent


class TheDriver(Driver):
    """Driver creating histograms of detector hits and their corresponding MCParticles"""

    DEFAULT_COLLECTIONS = ['VertexBarrelCollection', 'VertexEndcapCollection',
                           'InnerTrackerBarrelCollection', 'InnerTrackerEndcapCollection',
                           'OuterTrackerBarrelCollection', 'OuterTrackerEndcapCollection']
    CONST_C = R.TMath.C()

    def __init__(self, collections, output=None):
        """Constructor"""
        Driver.__init__(self)
        self.config = {
            'collections': collections,
            'output': output,
            't_min': -1e9,
            't_max': 1e9
        }
        self.out_file = R.TFile(self.config['output'], 'RECREATE')


    def startOfData(self):
        """Called by the event loop at the beginning of the loop"""

        names_F = ['edep', 'time', 'time0', 'path_len',
                   'pos_r', 'pos_z', 'pos_x', 'pos_y',
                   'mcp_vtx_r', 'mcp_vtx_z', 'mcp_vtx_x', 'mcp_vtx_y',
                   'mcp_bib_vtx_r', 'mcp_bib_vtx_z', 'mcp_bib_vtx_x', 'mcp_bib_vtx_y',
                   'mcp_theta', 'mcp_phi', 'mcp_bib_theta', 'mcp_bib_phi',
                   'mcp_time', 'mcp_bib_time',
                   'mcp_beta', 'mcp_gamma', 'mcp_e', 'mcp_p', 'mcp_pt', 'mcp_pz',
                   'mcp_bib_beta', 'mcp_bib_gamma', 'mcp_bib_e', 'mcp_bib_p', 'mcp_bib_pt', 'mcp_bib_pz'
                   ]
        names_I = ['layer', 'side', 'col_id',
                   'mcp_pdg', 'mcp_bib_pdg', 'mcp_bib_niters', 'mcp_gen', 'mcp_bib_gen']
        
        # Placeholder for CellID decoders
        self.cellID_decoders = {col_id: None for col_id, col_name in enumerate(self.config['collections'])}
        # Creating the TTree with branches
        self.data = {}
        self.tree = R.TTree('tree', 'SimTrackerHit properties')
        # self.tree.SetAutoFlush(200000)
        for name in names_F:
            self.data[name] = np.zeros(1, dtype=np.float32)
            self.tree.Branch(name, self.data[name], '{0:s}/F'.format(name))
        for name in names_I:
            self.data[name] = np.zeros(1, dtype=np.int32)
            self.tree.Branch(name, self.data[name], '{0:s}/I'.format(name))


    def processEvent( self, event ):
        """Called by the event loop for each event"""
        # Get the MCParticle collection
        mcParticles = event.getMcParticles()
        # Loop over hits in each hit collection
        for col_id, col_name in enumerate(self.config['collections']):
            col = event.getCollection(col_name)
            # Creating the CellID decoder for this collection
            if not self.cellID_decoders[col_id]:
                cell_id_encoding = col.getParameters().getStringVal(EVENT.LCIO.CellIDEncoding)
                cell_id_decoder = UTIL.BitField64(cell_id_encoding)
                self.cellID_decoders[col_id] = cell_id_decoder
            else:
                cell_id_decoder = self.cellID_decoders[col_id]
            # Filling the Tracker hit properties
            data = self.data
            nHits = col.getNumberOfElements()
            for iHit in range(nHits):
                # Hit time information
                hit = col.getElementAt(iHit)
                data['time'][0] = hit.getTime()
                pos = hit.getPositionVec()
                t0 = pos.Mag() / (self.CONST_C/1e6)
                data['time0'][0] = t0
                # Skipping hits outside of the time window
                if (data['time'][0] - t0) > self.config['t_max']:
                    continue
                if (data['time'][0] - t0) < self.config['t_min']:
                    continue
                # Decoding the CellID
                cell_id = int(hit.getCellID0() & 0xffffffff) | (int( hit.getCellID1() ) << 32)
                cell_id_decoder.setValue(cell_id)
                data['col_id'][0] = col_id
                data['side'][0] = int(cell_id_decoder['side'].value())
                data['layer'][0] = int(cell_id_decoder['layer'].value())
                # Hit general properties
                data['edep'][0] = hit.getEDep()
                data['path_len'][0] = hit.getPathLength()
                data['pos_x'][0] = pos.X()
                data['pos_y'][0] = pos.Y()
                data['pos_z'][0] = pos.Z()
                data['pos_r'][0] = pos.Perp()
                # MCParticle properties
                mcp = hit.getMCParticle()
                mcp_bib, mcp_bib_niters = get_oldest_mcp_parent(mcp)
                data['mcp_bib_niters'][0] = mcp_bib_niters
                for prefix, part in {'mcp': mcp, 'mcp_bib': mcp_bib}.items():
                    pos = part.getVertex()
                    lv = part.getLorentzVec()
                    data[prefix+'_vtx_x'][0] = pos[0]
                    data[prefix+'_vtx_y'][0] = pos[1]
                    data[prefix+'_vtx_z'][0] = pos[2]
                    data[prefix+'_vtx_r'][0] = math.sqrt(pos[0]*pos[0] + pos[1]*pos[1])
                    data[prefix+'_pdg'][0] = part.getPDG()
                    data[prefix+'_time'][0] = part.getTime()
                    data[prefix+'_gen'][0] = part.getGeneratorStatus()
                    data[prefix+'_theta'][0] = lv.Theta()
                    data[prefix+'_phi'][0] = lv.Phi()
                    data[prefix+'_p'][0] = lv.P()
                    data[prefix+'_pt'][0] = lv.Pt()
                    data[prefix+'_pz'][0] = lv.Pz()
                    data[prefix+'_beta'][0] = lv.Beta()
                    data[prefix+'_gamma'][0] = lv.Gamma()
                self.tree.Fill()

        print(f'  event: {event.getEventNumber():d}\t hits: {self.tree.GetEntriesFast():d}')

    def endOfData( self ):
        """Called by the event loop at the end of the loop"""
        # Storing histograms to the output ROOT file
        if self.config['output'] is not None:
            self.out_file.Write()
            self.out_file.Close()


# Executing the script
if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Analysing MCParticles responsible for SimTrackerHits')
    parser.add_argument('input', metavar='input.slcio', type=str, 
                        help='Input LCIO file')
    parser.add_argument('-o', '--output', metavar='analysis.root', type=str, default='analysis.root',
                        help='Path to the output ROOT file')
    parser.add_argument('-c', '--collections', type=str, nargs='+', default=TheDriver.DEFAULT_COLLECTIONS,
                        help='Names of collections to analyse')
    parser.add_argument('-m', '--max_events', metavar='N', type=int, 
                        help='Maximum number of events to process', default=-1)
    parser.add_argument('--t_min', type=float,
                        help='Lowest time-TOF of the hits to consider [ns]')
    parser.add_argument('--t_max', type=float,
                        help='Highest time-TOF of the hits to consider [ns]')
    args = parser.parse_args()

    from pyLCIO.drivers.EventMarkerDriver import EventMarkerDriver
    from pyLCIO.io.EventLoop import EventLoop
    from pprint import pprint

    # Initialising the Driver
    driver = TheDriver(collections=args.collections, output=args.output)
    if args.t_min is not None:
        driver.config['t_min'] = args.t_min
    if args.t_max is not None:
        driver.config['t_max'] = args.t_max
    print(f'+ Initialised analysis with configuration:')
    pprint(driver.config, indent=2)
    # Initialising the EventLoop
    analyzer = EventLoop()
    analyzer.addFile(args.input)
    analyzer.add(driver)
    # Starting the analysis
    n_events = analyzer.reader.getNumberOfEvents()
    print(f'+ Starting analysis of events: {n_events}')
    analyzer.loop(min(n_events, args.max_events))
    print('+ Finished analysis')

