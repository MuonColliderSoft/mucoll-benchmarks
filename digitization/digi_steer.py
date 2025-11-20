'''-------------------------------------------------------------'''
'''  Digitization Steering File for the Muon Collider Detector  '''
'''-------------------------------------------------------------'''
from GaudiKernel.Constants import INFO, WARNING
# Collect Arguements
from digi_components.digi_args import get_digi_args
args = get_digi_args()

# Set Up Services
from muc_services import set_services
services = list(set_services(args, "digi_histograms.root"))

# Import the Algorithm List
from digiAlgList import makeDigiAlgList
algList = makeDigiAlgList(args)

# Set up Multi-Threading if enabled
from muc_mt import get_mt_args, get_k4run_mt
mt_args = get_mt_args()
if mt_args.useMT:
    whiteboard, selm, sch = get_k4run_mt(
        mt_args.numThreads, mt_args.numThreads
    )
    services += [whiteboard]

'''-------------------------------------------------------------'''
'''    Run the Digitization Algorithms in the ApplicationMgr    '''
'''-------------------------------------------------------------'''
# Declare Input and Output for the IOSvc
from k4FWCore import IOSvc, ApplicationMgr
svc = IOSvc(
    "IOSvc",
    Input = ["sim_output.edm4hep.root"],  # Input file from simulation
    Output = "digi_output.edm4hep.root" # Output file for digitization
)

# Run the Application Manager
ApplicationMgr(
    TopAlg = algList,
    EvtSel = 'NONE',
    EvtMax   = 10,
    ExtSvc = services,
    EventLoop = selm if mt_args.useMT else None,
    OutputLevel=INFO
)
