'''-------------------------------------------------------------'''
'''  BIB pruning steering file                                   '''
'''-------------------------------------------------------------'''
# Copies an EDM4hep file to a new EDM4hep file, dropping the MCParticle
# collection (named "MCParticles" in the simulation output) along with the
# now-orphaned CaloHitContribution collections (the "*Contributions"
# collections, whose only purpose is to link calo hits to MCParticles).
# Useful for shrinking large BIB samples where the truth record is not needed.
#
# Note: dropping the contributions leaves the SimCalorimeterHit collections
# with dangling contribution references; podio resolves these to null on read,
# so the output is still usable.
#
# Run with:
#   k4run BIB_pruning.py --inputFile <in.edm4hep.root> \
#                        --outputFile <out.edm4hep.root>

from Gaudi.Configuration import WARNING
from k4FWCore import IOSvc, ApplicationMgr
from k4FWCore.parseArgs import parser

parser.add_argument(
    "--inputFile",
    help="Input EDM4hep file",
    type=str,
    default="input.edm4hep.root",
)
parser.add_argument(
    "--outputFile",
    help="Output EDM4hep file (MCParticles dropped)",
    type=str,
    default="pruned.edm4hep.root",
)
args = parser.parse_known_args()[0]

# Collections to remove: the MC truth record plus the CaloHitContribution
# collections that only exist to reference it (matched by the "*Contributions"
# suffix).
DROP_COLLECTIONS = ["MCParticles", "*Contributions"]

# Read everything, write everything except the dropped collections.
io_svc = IOSvc("IOSvc")
io_svc.Input = args.inputFile
io_svc.Output = args.outputFile
io_svc.outputCommands = ["keep *"] + [f"drop {c}" for c in DROP_COLLECTIONS]

# No algorithms: this is a pure copy-with-drop job. k4run/ApplicationMgr drives
# the event loop and the IOSvc handles the read/write.
ApplicationMgr(
    TopAlg=[],
    EvtSel="NONE",
    EvtMax=-1,
    ExtSvc=[io_svc],
    OutputLevel=WARNING,
)
