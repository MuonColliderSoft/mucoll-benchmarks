from Gaudi.Configuration import *
from GaudiKernel.Constants import INFO, WARNING, DEBUG
from Configurables import GeoSvc, EventDataSvc, THistSvc, UniqueIDGenSvc

def set_services(the_args, mt_args, histo_file):
    """
    Set up the necessary services.
    
    Parameters:
    the_args: Argument parser object containing configuration parameters.
    histo_file: Filename for the histogram output.
    """
    geoservice = GeoSvc(
        "GeoSvc",
        detectors = [the_args.DD4hepXMLFile],
        OutputLevel = WARNING,
        EnableGeant4Geo = False
    )

    id_service = UniqueIDGenSvc(
        "UniqueIDGenSvc", 
        Seed = getattr(the_args, "RandSeed", 0)
    )

    THistSvc().Output = [f"histos DATAFILE='{histo_file}' TYP='ROOT' OPT='RECREATE'"]
    THistSvc().PrintAll = True
    THistSvc().AutoSave = True
    THistSvc().AutoFlush = True

    if mt_args.useMT:
        return [geoservice, id_service]
    else:
        evtsvc = EventDataSvc("EventDataSvc")
        return [evtsvc, geoservice, id_service]
