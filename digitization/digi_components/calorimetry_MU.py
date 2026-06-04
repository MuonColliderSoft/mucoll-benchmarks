from GaudiKernel.Constants import INFO, WARNING
from Configurables import DDSimpleMuonDigi

def MuonBarrelDigi_cfg(args):
    """
    Create a new Muon Barrel digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayYokeBarrelCollection"]
    else:
        inputHitCollections = ["YokeBarrelCollection"]
    return DDSimpleMuonDigi(
        "MuonBarrelDigitiser",
        CalibrMUON = 70.1,
        MuonThreshold = 1e-06,
        MaxHitEnergyMUON = 2.0,
        MUONCollection = inputHitCollections,
        MUONOutputCollection = ["MuonBarrelHits"],
        RelationOutputCollection = ["MuonBarrelHitsRelations"],
        OutputLevel = INFO
    )


def MuonEndcapDigi_cfg(args):
    """
    Create a new Muon Endcap digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayYokeEndcapCollection"]
    else:
        inputHitCollections = ["YokeEndcapCollection"]
    return DDSimpleMuonDigi(
        "MuonEndcapDigitiser",
        CalibrMUON = 70.1,
        MuonThreshold = 1e-06,
        MaxHitEnergyMUON = 2.0,
        MUONCollection = inputHitCollections,
        MUONOutputCollection = ["MuonEndcapHits"],
        RelationOutputCollection = ["MuonEndcapHitsRelations"],
        OutputLevel = INFO
    )
