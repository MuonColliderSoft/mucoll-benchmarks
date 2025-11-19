from GaudiKernel.Constants import INFO, WARNING
from Configurables import DDMuonDigiSimple

def MuonBarrelDigi_cfg(args):
    """
    Create a new Muon Barrel digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayYokeBarrelCollection"]
    else:
        inputHitCollections = ["YokeBarrelCollection"]
    return DDMuonDigiSimple(
        "MuonBarrelDigitiser",
        calibrationCoeffmuon = 70.1,
        MuonThreshold = 1e-06,
        maxMuonHitEnergy = 2.0,
        CaloLayout = "barrel",
        MUONCollection = inputHitCollections,
        MUONOutputCollections = ["MuonBarrelHits"],
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
    return DDMuonDigiSimple(
        "MuonEndcapDigitiser",
        calibrationCoeffmuon = 70.1,
        MuonThreshold = 1e-06,
        maxMuonHitEnergy = 2.0,
        CaloLayout = "endcap",
        MUONCollection = inputHitCollections,
        MUONOutputCollections = ["MuonEndcapHits"],
        RelationOutputCollection = ["MuonEndcapHitsRelations"],
        OutputLevel = INFO
    )