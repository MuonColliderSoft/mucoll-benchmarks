'''-------------------------------------------------------------'''
''' Reconstruction Steering File for the Muon Collider Detector '''
'''-------------------------------------------------------------'''
from GaudiKernel.Constants import INFO, WARNING, DEBUG
# Collect Arguements
from reco_components.reco_args import get_reco_args
args = get_reco_args()

services = []

# Set up Multi-Threading if enabled
from muc_mt import get_mt_args, get_k4run_mt
mt_args = get_mt_args()
if mt_args.useMT:
    whiteboard, selm, sch = get_k4run_mt(
        mt_args.numThreads, mt_args.numThreads
    )
    services += [whiteboard]

# Set Up Services
from muc_services import set_services
services += list(set_services(args, mt_args, "reco_histograms.root"))

# Import the Algorithm List
from recoAlgList import makeRecoAlgList
algList = makeRecoAlgList(args)

'''-------------------------------------------------------------'''
'''   Run the Reconstruction Algorithms in the ApplicationMgr   '''
'''-------------------------------------------------------------'''
# Declare Input and Output for the IOSvc
from k4FWCore import IOSvc, ApplicationMgr
svc = IOSvc(
    "IOSvc",
    Input = ["digi_output.edm4hep.root"], # Input file from digitization
    Output = "reco_output.edm4hep.root" # Output file for reconstruction
)

# Run the Application Manager
ApplicationMgr(
    TopAlg = algList,
    EvtSel = 'NONE',
    EvtMax = 10,
    ExtSvc = services,
    OutputLevel = WARNING,
)
if mt_args.useMT:
    ApplicationMgr().EventLoop = selm
