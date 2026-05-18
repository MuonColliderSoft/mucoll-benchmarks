from Gaudi.Configuration import *
from Configurables import GeoSvc, EventDataSvc, THistSvc

def set_reco_services(the_args):
    """
    Set up the necessary services for the reconstruction process.
    
    Parameters:
    the_args: Argument parser object containing configuration parameters.
    """
    geoservice = GeoSvc(
        "GeoSvc",
        detectors = [the_args.DD4hepXMLFile],
        materialFile = the_args.MatFile,
        OutputLevel = INFO,
        EnableGeant4Geo = False
    )

    evtsvc = EventDataSvc("EventDataSvc")

    THistSvc().Output = ["histos DATAFILE='reco_histograms.root' TYP='ROOT' OPT='RECREATE'"]
    THistSvc().PrintAll = True
    THistSvc().AutoSave = True
    THistSvc().AutoFlush = True

    return [evtsvc, geoservice]