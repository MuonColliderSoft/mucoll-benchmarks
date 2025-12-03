import os
from Gaudi.Configuration import *
from k4FWCore.parseArgs import parser

def get_reco_args():
    """
    Parse command line arguments for the reconstruction steering.
    """
    parser.add_argument(
        "--DD4hepXMLFile",
        help="Compact detector description file",
        type=str,
        default=os.environ.get("MUCOLL_GEO", ""),
    )

    parser.add_argument(
        "--DetectorSchema",
        help="Name of the detector schema",
        type=str,
        default=os.environ.get("MUCOLL_GEOM_NAME", ""),
    )

    parser.add_argument(
        "--MatFile",
        help="Material maps file for tracking",
        type=str,
        default=os.environ.get("MUCOLL_MATMAP", ""),
    )

    parser.add_argument(
        "--TGeoFile",
        help="TGeometry file for tracking",
        type=str,
        default=os.environ.get("MUCOLL_TGEO", ""),
    )

    parser.add_argument(
        "--TGeoDescFile",
        help="TGeometry Subdetector JSON file for tracking",
        type=str,
        default=os.environ.get("MUCOLL_TGEO_DESC", ""),
    )

    parser.add_argument(
        "--doTrackPerf",
        help="Run Performance Analysis on Tracking",
        action="store_true",
        default=False
    )

    parser.add_argument(
        "--TrackingThreads",
        help="Number of threads for tracking",
        type=int,
        default=1,
    )

    return parser.parse_known_args()[0]
