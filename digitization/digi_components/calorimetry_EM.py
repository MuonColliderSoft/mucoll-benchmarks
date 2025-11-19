from GaudiKernel.Constants import INFO, WARNING
from Configurables import RealisticCaloDigiSilicon, RealisticCaloRecoSilicon

def ECalBarrelDigi_cfg(args):
    """
    Create a new ECal barrel digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayECalBarrelCollection"]
    else:
        inputHitCollections = ["ECalBarrelCollection"]
    return RealisticCaloDigiSilicon(
        "ECalBarrelDigi",
        calibration_mip = 0.0001575,
        threshold = 5e-05,
        thresholdUnit = "GeV",
        timingCorrectForPropagation = 1,
        timingCut = 1,
        timingResolution = 0.0,
        timingWindowMax = 10.0,
        timingWindowMin = -0.5,
        elec_range_mip = 15000.0,
        CaloType = "em", CaloID = "ecal", CaloLayout = "barrel",
        inputHitCollections = inputHitCollections,
        outputHitCollections = ["EcalBarrelCollectionDigi"],
        outputRelationCollections = ["EcalBarrelRelationsSimDigi"],
        OutputLevel = INFO
    )

def ECalBarrelReco_cfg():
    """
    Create a new ECal barrel reco instance with the given parameters.
    """
    return RealisticCaloRecoSilicon(
        "ECalBarrelReco",
        calibration_factorsMipGev = [0.00641222630095],
        calibration_layergroups = [50],
        inputLinkCollections = ["EcalBarrelRelationsSimDigi"],
        outputHitCollections = ["EcalBarrelCollectionRec"],
        outputRelationCollections = ["EcalBarrelRelationsSimRec"],
        OutputLevel = INFO
    )

def ECalPlugDigi_cfg(args):
    """
    Create a new ECal plug digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayECalPlugCollection"]
    else:
        inputHitCollections = ["ECalPlugCollection"]
    return RealisticCaloDigiSilicon(
        "ECalPlugDigi",
        calibration_mip = 0.0001575,
        threshold = 5e-05,
        thresholdUnit = "GeV",
        timingCorrectForPropagation = 1,
        timingCut = 1,
        timingResolution = 0.0,
        timingWindowMax = 10.0,
        timingWindowMin = -0.5,
        elec_range_mip = 15000.0,
        CaloType = "em", CaloID = "ecal", CaloLayout = "plug",
        inputHitCollections = inputHitCollections,
        outputHitCollections = ["ECalPlugCollectionDigi"],
        outputRelationCollections = ["ECalPlugRelationsSimDigi"],
        OutputLevel = INFO
    )

def ECalPlugReco_cfg():
    """
    Create a new ECal plug reco instance with the given parameters.
    """
    return RealisticCaloRecoSilicon(
        "ECalPlugReco",
        calibration_factorsMipGev = [0.00641222630095],
        calibration_layergroups = [50],
        inputLinkCollections = ["ECalPlugRelationsSimDigi"],
        outputHitCollections = ["ECalPlugCollectionRec"],
        outputRelationCollections = ["ECalPlugRelationsSimRec"],
        OutputLevel = INFO
    )

def ECalEndcapDigi_cfg(args):
    """
    Create a new ECal endcap digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayECalEndcapCollection"]
    else:
        inputHitCollections = ["ECalEndcapCollection"]
    return RealisticCaloDigiSilicon(
        "ECalEndcapDigi",
        calibration_mip = 0.0001575,
        threshold = 5e-05,
        thresholdUnit = "GeV",
        timingCorrectForPropagation = 1,
        timingCut = 1,
        timingResolution = 0.0,
        timingWindowMax = 10.0,
        timingWindowMin = -0.5,
        elec_range_mip = 15000.0,
        CaloType = "em", CaloID = "ecal", CaloLayout = "endcap",
        inputHitCollections = inputHitCollections,
        outputHitCollections = ["EcalEndcapCollectionDigi"],
        outputRelationCollections = ["EcalEndcapRelationsSimDigi"],
        OutputLevel = INFO
    )

def ECalEndcapReco_cfg():
    """
    Create a new ECal endcap reco instance with the given parameters.
    """
    return RealisticCaloRecoSilicon(
        "ECalEndcapReco",
        calibration_factorsMipGev = [0.00641222630095],
        calibration_layergroups = [50],
        inputLinkCollections = ["EcalEndcapRelationsSimDigi"],
        outputHitCollections = ["EcalEndcapCollectionRec"],
        outputRelationCollections = ["EcalEndcapRelationsSimRec"],
        OutputLevel = INFO
    )
