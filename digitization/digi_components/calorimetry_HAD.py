from GaudiKernel.Constants import INFO, WARNING
from Configurables import RealisticCaloDigiScinPpd, RealisticCaloRecoScinPpd

def HCalBarrelDigi_cfg(args):
    """
    Create a new HCal barrel digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayHCalBarrelCollection"]
    else:
        inputHitCollections = ["HCalBarrelCollection"]
    return RealisticCaloDigiScinPpd(
        "HCalBarrelDigi",
        calibration_mip = 0.0004925,
        threshold = 0.5,
        thresholdUnit = "MIP",
        #timingCorrectForPropagation = 1,
        timingCut = 1,
        #timingResolution = 0.0,
        #timingWindowMax = 10.0,
        #timingWindowMin = -0.5,
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        ppd_npix_uncert = 0.0,
        ppd_pix_spread = 0.0,
        CaloType = "had", CaloID = "hcal", CaloLayout = "barrel",
        inputHitCollections = inputHitCollections,
        outputHitCollections = ["HcalBarrelCollectionDigi"],
        outputRelationCollections = ["HcalBarrelRelationsSimDigi"],
        OutputLevel = INFO
    )

def HCalBarrelReco_cfg():
    """
    Create a new HCal barrel reco instance with the given parameters.
    """
    return RealisticCaloRecoScinPpd(
        "HCalBarrelReco",
        calibration_factorsMipGev = [0.0287783798145],
        calibration_layergroups = [100],
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        inputLinkCollections = ["HcalBarrelRelationsSimDigi"],
        outputHitCollections = ["HcalBarrelCollectionRec"],
        outputRelationCollections = ["HcalBarrelRelationsSimRec"],
        OutputLevel = INFO
    )

def HCalEndcapDigi_cfg(args):
    """
    Create a new HCal endcap digitiser instance with the given parameters.
    """
    if args.doOverlayFull:
        inputHitCollections = ["OverlayHCalEndcapCollection"]
    else:
        inputHitCollections = ["HCalEndcapCollection"]
    return RealisticCaloDigiScinPpd(
        "HCalEndcapDigi",
        calibration_mip = 0.0004725,
        threshold = 0.5,
        thresholdUnit = "MIP",
        #timingCorrectForPropagation = 1,
        timingCut = 1,
        #timingResolution = 0.0,
        #timingWindowMax = 10.0,
        #timingWindowMin = -0.5,
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        ppd_npix_uncert = 0.0,
        ppd_pix_spread = 0.0,
        CaloType = "had", CaloID = "hcal", CaloLayout = "endcap",
        inputHitCollections = inputHitCollections,
        outputHitCollections = ["HcalEndcapCollectionDigi"],
        outputRelationCollections = ["HcalEndcapRelationsSimDigi"],
        OutputLevel = INFO
    )

def HCalEndcapReco_cfg():
    """
    Create a new HCal endcap reco instance with the given parameters.
    """
    return RealisticCaloRecoScinPpd(
        "HCalEndcapReco",
        calibration_factorsMipGev = [0.0285819096797],
        calibration_layergroups = [100],
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        inputLinkCollections = ["HcalEndcapRelationsSimDigi"],
        outputHitCollections = ["HcalEndcapCollectionRec"],
        outputRelationCollections = ["HcalEndcapRelationsSimRec"],
        OutputLevel = INFO
    )

def HCalRingDigi_cfg(args):
    """
    Create a new HCal ring digi instance with the given parameters.
    """
    return RealisticCaloDigiScinPpd(
        "HCalRingDigi",
        calibration_mip = 0.0004725,
        threshold = 0.5,
        thresholdUnit = "MIP",
        #timingCorrectForPropagation = 1,
        timingCut = 1,
        #timingResolution = 0.0,
        #timingWindowMax = 10.0,
        #timingWindowMin = -0.5,
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        ppd_npix_uncert = 0.0,
        ppd_pix_spread = 0.0,
        CaloType = "had", CaloID = "hcal", CaloLayout = "ring",
        inputHitCollections = ["OverlayHCalRingCollection"],
        outputHitCollections = ["HCalRingCollectionDigi"],
        outputRelationCollections = ["HCalRingRelationsSimDigi"],
        OutputLevel = INFO
    )

def HCalRingReco_cfg():
    """
    Create a new HCal ring reco instance with the given parameters.
    """
    return RealisticCaloRecoScinPpd(
        "HCalRingReco",
        calibration_factorsMipGev = [0.0285819096797],
        calibration_layergroups = [100],
        ppd_mipPe = 15.0,
        ppd_npix = 2000,
        inputLinkCollections = ["HCalRingRelationsSimDigi"],
        outputHitCollections = ["HCalRingCollectionRec"],
        outputRelationCollections = ["HCalRingRelationsSimRec"],
        OutputLevel = INFO
    )