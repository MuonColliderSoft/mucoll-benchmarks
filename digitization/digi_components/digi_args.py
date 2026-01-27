import os
from k4FWCore.parseArgs import parser

def get_digi_args():
    parser.add_argument(
        "--DD4hepXMLFile",
        help="Compact detector description file",
        type=str,
        default=os.environ.get("MUCOLL_GEO", ""),
    )

    parser.add_argument(
        "--OverlayFullPathToMuPlus",
        help="Path to files for muplus BIB overlay",
        type=str,
        default="/path/to/muplus/",
    )

    parser.add_argument(
        "--OverlayFullPathToMuMinus",
        help="Path to files for muminus BIB overlay",
        type=str,
        default="/path/to/muminus/",
    )

    parser.add_argument(
        "--OverlayFullNumberBackground",
        help="Number of background files used for BIB overlay",
        type=int,
        default=812, #Magic number assumes 45 phi clones of each MC particle
    )

    parser.add_argument(
        "--OverlayIPBackgroundFileNames",
        help="Path to files used for incoherent pairs overlay",
        type=str,
        default="/path/to/pairs.slcio",
    )

    parser.add_argument(
        "--doOverlayFull",
        help="Do BIB overlay",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--doOverlayIP",
        help="Do incoherent pairs overlay",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--doFilterDL",
        help="Do double-layer filtering",
        action="store_true",
        default=False,
    )
    
    parser.add_argument(
        "--RandSeed",
        help="Random seed for digitization",
        type=int,
        default=42,
    )

    return parser.parse_known_args()[0]
