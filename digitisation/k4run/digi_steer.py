import os
from Gaudi.Configuration import *

from Configurables import LcioEvent, EventDataSvc, MarlinProcessorWrapper
from k4FWCore.parseArgs import parser

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
    type=str,
    default="192", #Magic number assumes 45 phi clones of each MC particle
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

the_args = parser.parse_known_args()[0]

algList = []
evtsvc = EventDataSvc()

read = LcioEvent()
read.OutputLevel = INFO
read.Files = ["input.slcio"]
algList.append(read)

DD4hep = MarlinProcessorWrapper("DD4hep")
DD4hep.OutputLevel = INFO
DD4hep.ProcessorType = "InitializeDD4hep"
DD4hep.Parameters = {
                     "DD4hepXMLFile": [the_args.DD4hepXMLFile],
                     "EncodingStringParameterName": ["GlobalTrackerReadoutID"]
                     }

AIDA = MarlinProcessorWrapper("AIDA")
AIDA.OutputLevel = INFO
AIDA.ProcessorType = "AIDAProcessor"
AIDA.Parameters = {
                   "Compress": ["1"],
                   "FileName": ["output_digi"],
                   "FileType": ["root"]
                   }

EventNumber = MarlinProcessorWrapper("EventNumber")
EventNumber.OutputLevel = INFO
EventNumber.ProcessorType = "Statusmonitor"
EventNumber.Parameters = {
                          "HowOften": ["1"]
                          }

LCIOWriter_all = MarlinProcessorWrapper("LCIOWriter_all")
LCIOWriter_all.OutputLevel = INFO
LCIOWriter_all.ProcessorType = "LCIOOutputProcessor"
LCIOWriter_all.Parameters = {
                             "DropCollectionNames": [],
                             "DropCollectionTypes": [],
                             "FullSubsetCollections": [],
                             "KeepCollectionNames": [],
                             "LCIOOutputFile": ["output_digi.slcio"],
                             "LCIOWriteMode": ["WRITE_NEW"]
                             }

LCIOWriter_light = MarlinProcessorWrapper("LCIOWriter_light")
LCIOWriter_light.OutputLevel = INFO
LCIOWriter_light.ProcessorType = "LCIOOutputProcessor"
LCIOWriter_light.Parameters = {
                               "DropCollectionNames": ["MCParticle", "MCPhysicsParticle"],
                               "DropCollectionTypes": ["SimTrackerHit", "SimCalorimeterHit", "LCRelation"],
                               "FullSubsetCollections": [],
                               "KeepCollectionNames": [],
                               "LCIOOutputFile": ["output_digi_light.slcio"],
                               "LCIOWriteMode": ["WRITE_NEW"]
                               }

VXDBarrelDigitiser = MarlinProcessorWrapper("VXDBarrelDigitiser")
VXDBarrelDigitiser.OutputLevel = INFO
VXDBarrelDigitiser.ProcessorType = "DDPlanarDigiProcessor"
VXDBarrelDigitiser.Parameters = {
                                 "CorrectTimesForPropagation": ["true"],
                                 "IsStrip": ["false"],
                                 "ResolutionT": ["0.03"],
                                 "ResolutionU": ["0.005"],
                                 "ResolutionV": ["0.005"],
                                 "SimTrackHitCollectionName": ["VertexBarrelCollection"],
                                 "SimTrkHitRelCollection": ["VXDBarrelHitsRelations"],
                                 "SubDetectorName": ["Vertex"],
                                 "TimeWindowMax": ["0.15"],
                                 "TimeWindowMin": ["-0.09"],
                                 "TrackerHitCollectionName": ["VXDBarrelHits"],
                                 "UseTimeWindow": ["true"]
                                 }

VXDEndcapDigitiser = MarlinProcessorWrapper("VXDEndcapDigitiser")
VXDEndcapDigitiser.OutputLevel = INFO
VXDEndcapDigitiser.ProcessorType = "DDPlanarDigiProcessor"
VXDEndcapDigitiser.Parameters = {
                                 "CorrectTimesForPropagation": ["true"],
                                 "IsStrip": ["false"],
                                 "ResolutionT": ["0.03"],
                                 "ResolutionU": ["0.005"],
                                 "ResolutionV": ["0.005"],
                                 "SimTrackHitCollectionName": ["VertexEndcapCollection"],
                                 "SimTrkHitRelCollection": ["VXDEndcapHitsRelations"],
                                 "SubDetectorName": ["Vertex"],
                                 "TimeWindowMax": ["0.15"],
                                 "TimeWindowMin": ["-0.09"],
                                 "TrackerHitCollectionName": ["VXDEndcapHits"],
                                 "UseTimeWindow": ["true"]
                                 }

ITBarrelDigitiser = MarlinProcessorWrapper("ITBarrelDigitiser")
ITBarrelDigitiser.OutputLevel = INFO
ITBarrelDigitiser.ProcessorType = "DDPlanarDigiProcessor"
ITBarrelDigitiser.Parameters = {
                                "CorrectTimesForPropagation": ["true"],
                                "IsStrip": ["false"],
                                "ResolutionT": ["0.06"],
                                "ResolutionU": ["0.007"],
                                "ResolutionV": ["0.09"],
                                "SimTrackHitCollectionName": ["InnerTrackerBarrelCollection"],
                                "SimTrkHitRelCollection": ["ITBarrelHitsRelations"],
                                "SubDetectorName": ["InnerTrackers"],
                                "TimeWindowMax": ["0.3"],
                                "TimeWindowMin": ["-0.18"],
                                "TrackerHitCollectionName": ["ITBarrelHits"],
                                "UseTimeWindow": ["true"]
                                }

ITEndcapDigitiser = MarlinProcessorWrapper("ITEndcapDigitiser")
ITEndcapDigitiser.OutputLevel = INFO
ITEndcapDigitiser.ProcessorType = "DDPlanarDigiProcessor"
ITEndcapDigitiser.Parameters = {
                                "CorrectTimesForPropagation": ["true"],
                                "IsStrip": ["false"],
                                "ResolutionT": ["0.06"],
                                "ResolutionU": ["0.007"],
                                "ResolutionV": ["0.09"],
                                "SimTrackHitCollectionName": ["InnerTrackerEndcapCollection"],
                                "SimTrkHitRelCollection": ["ITEndcapHitsRelations"],
                                "SubDetectorName": ["InnerTrackers"],
                                "TimeWindowMax": ["0.3"],
                                "TimeWindowMin": ["-0.18"],
                                "TrackerHitCollectionName": ["ITEndcapHits"],
                                "UseTimeWindow": ["true"]
                                }

OTBarrelDigitiser = MarlinProcessorWrapper("OTBarrelDigitiser")
OTBarrelDigitiser.OutputLevel = INFO
OTBarrelDigitiser.ProcessorType = "DDPlanarDigiProcessor"
OTBarrelDigitiser.Parameters = {
                                "CorrectTimesForPropagation": ["true"],
                                "IsStrip": ["false"],
                                "ResolutionT": ["0.06"],
                                "ResolutionU": ["0.007"],
                                "ResolutionV": ["0.09"],
                                "SimTrackHitCollectionName": ["OuterTrackerBarrelCollection"],
                                "SimTrkHitRelCollection": ["OTBarrelHitsRelations"],
                                "SubDetectorName": ["OuterTrackers"],
                                "TimeWindowMax": ["0.3"],
                                "TimeWindowMin": ["-0.18"],
                                "TrackerHitCollectionName": ["OTBarrelHits"],
                                "UseTimeWindow": ["true"]
                                }

OTEndcapDigitiser = MarlinProcessorWrapper("OTEndcapDigitiser")
OTEndcapDigitiser.OutputLevel = INFO
OTEndcapDigitiser.ProcessorType = "DDPlanarDigiProcessor"
OTEndcapDigitiser.Parameters = {
                                "CorrectTimesForPropagation": ["true"],
                                "IsStrip": ["false"],
                                "ResolutionT": ["0.06"],
                                "ResolutionU": ["0.007"],
                                "ResolutionV": ["0.09"],
                                "SimTrackHitCollectionName": ["OuterTrackerEndcapCollection"],
                                "SimTrkHitRelCollection": ["OTEndcapHitsRelations"],
                                "SubDetectorName": ["OuterTrackers"],
                                "TimeWindowMax": ["0.3"],
                                "TimeWindowMin": ["-0.18"],
                                "TrackerHitCollectionName": ["OTEndcapHits"],
                                "UseTimeWindow": ["true"]
                                }

ECalBarrelDigi = MarlinProcessorWrapper("ECalBarrelDigi")
ECalBarrelDigi.OutputLevel = INFO
ECalBarrelDigi.ProcessorType = "RealisticCaloDigiSilicon"
ECalBarrelDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0001575"],
    "inputHitCollections": ["ECalBarrelCollection"],
    "outputHitCollections": ["EcalBarrelCollectionDigi"],
    "outputRelationCollections": ["EcalBarrelRelationsSimDigi"],
    "threshold": ["5e-05"],
    "thresholdUnit": ["GeV"],
    "timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    "timingResolution": ["0"],
    "timingWindowMax": ["10"],
    "timingWindowMin": ["-0.5"],
    "elec_range_mip": ["15000"]
}

ECalBarrelReco = MarlinProcessorWrapper("ECalBarrelReco")
ECalBarrelReco.OutputLevel = INFO
ECalBarrelReco.ProcessorType = "RealisticCaloRecoSilicon"
ECalBarrelReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.00641222630095"],
    "calibration_layergroups": ["41"],
    "inputHitCollections": ["EcalBarrelCollectionDigi"],
    "inputRelationCollections": ["EcalBarrelRelationsSimDigi"],
    "outputHitCollections": ["EcalBarrelCollectionRec"],
    "outputRelationCollections": ["EcalBarrelRelationsSimRec"]
}

ECalPlugDigi = MarlinProcessorWrapper("ECalPlugDigi")
ECalPlugDigi.OutputLevel = INFO
ECalPlugDigi.ProcessorType = "RealisticCaloDigiSilicon"
ECalPlugDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0001575"],
    "inputHitCollections": ["ECalPlugCollection"],
    "outputHitCollections": ["ECalPlugCollectionDigi"],
    "outputRelationCollections": ["ECalPlugRelationsSimDigi"],
    "threshold": ["5e-05"],
    "thresholdUnit": ["GeV"],
    "timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    "timingResolution": ["0"],
    "timingWindowMax": ["10"],
    "timingWindowMin": ["-0.5"],
    "elec_range_mip": ["15000"]
}

ECalPlugReco = MarlinProcessorWrapper("ECalPlugReco")
ECalPlugReco.OutputLevel = INFO
ECalPlugReco.ProcessorType = "RealisticCaloRecoSilicon"
ECalPlugReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.00641222630095"],
    "calibration_layergroups": ["41"],
    "inputHitCollections": ["ECalPlugCollectionDigi"],
    "inputRelationCollections": ["ECalPlugRelationsSimDigi"],
    "outputHitCollections": ["ECalPlugCollectionRec"],
    "outputRelationCollections": ["ECalPlugRelationsSimRec"]
}

ECalEndcapDigi = MarlinProcessorWrapper("ECalEndcapDigi")
ECalEndcapDigi.OutputLevel = INFO
ECalEndcapDigi.ProcessorType = "RealisticCaloDigiSilicon"
ECalEndcapDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0001575"],
    "inputHitCollections": ["ECalEndcapCollection"],
    "outputHitCollections": ["EcalEndcapCollectionDigi"],
    "outputRelationCollections": ["EcalEndcapRelationsSimDigi"],
    "threshold": ["5e-05"],
    "thresholdUnit": ["GeV"],
    "timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    "timingResolution": ["0"],
    "timingWindowMax": ["10"],
    "timingWindowMin": ["-0.5"],
    "elec_range_mip": ["15000"]
}

ECalEndcapReco = MarlinProcessorWrapper("ECalEndcapReco")
ECalEndcapReco.OutputLevel = INFO
ECalEndcapReco.ProcessorType = "RealisticCaloRecoSilicon"
ECalEndcapReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.00641222630095"],
    "calibration_layergroups": ["41"],
    "inputHitCollections": ["EcalEndcapCollectionDigi"],
    "inputRelationCollections": ["EcalEndcapRelationsSimDigi"],
    "outputHitCollections": ["EcalEndcapCollectionRec"],
    "outputRelationCollections": ["EcalEndcapRelationsSimRec"]
}

HCalBarrelDigi = MarlinProcessorWrapper("HCalBarrelDigi")
HCalBarrelDigi.OutputLevel = INFO
HCalBarrelDigi.ProcessorType = "RealisticCaloDigiScinPpd"
HCalBarrelDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0004925"],
    "inputHitCollections": ["HCalBarrelCollection"],
    "outputHitCollections": ["HcalBarrelCollectionDigi"],
    "outputRelationCollections": ["HcalBarrelRelationsSimDigi"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"],
    "ppd_npix_uncert": ["0"],
    "ppd_pix_spread": ["0"],
    "threshold": ["0.5"],
    "thresholdUnit": ["MIP"],
    #"timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    #"timingResolution": ["0"],
    #"timingWindowMax": ["10"],
    #"timingWindowMin": ["-0.5"]
}

HCalBarrelReco = MarlinProcessorWrapper("HCalBarrelReco")
HCalBarrelReco.OutputLevel = INFO
HCalBarrelReco.ProcessorType = "RealisticCaloRecoScinPpd"
HCalBarrelReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.0287783798145"],
    "calibration_layergroups": ["100"],
    "inputHitCollections": ["HcalBarrelCollectionDigi"],
    "inputRelationCollections": ["HcalBarrelRelationsSimDigi"],
    "outputHitCollections": ["HcalBarrelCollectionRec"],
    "outputRelationCollections": ["HcalBarrelRelationsSimRec"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"]
}

HCalEndcapDigi = MarlinProcessorWrapper("HCalEndcapDigi")
HCalEndcapDigi.OutputLevel = INFO
HCalEndcapDigi.ProcessorType = "RealisticCaloDigiScinPpd"
HCalEndcapDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0004725"],
    "inputHitCollections": ["HCalEndcapCollection"],
    "outputHitCollections": ["HcalEndcapCollectionDigi"],
    "outputRelationCollections": ["HcalEndcapRelationsSimDigi"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"],
    "ppd_npix_uncert": ["0"],
    "ppd_pix_spread": ["0"],
    "threshold": ["0.5"],
    "thresholdUnit": ["MIP"],
    #"timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    #"timingResolution": ["0"],
    #"timingWindowMax": ["10"],
    #"timingWindowMin": ["-0.5"]
}

HCalEndcapReco = MarlinProcessorWrapper("HCalEndcapReco")
HCalEndcapReco.OutputLevel = INFO
HCalEndcapReco.ProcessorType = "RealisticCaloRecoScinPpd"
HCalEndcapReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.0285819096797"],
    "calibration_layergroups": ["100"],
    "inputHitCollections": ["HcalEndcapCollectionDigi"],
    "inputRelationCollections": ["HcalEndcapRelationsSimDigi"],
    "outputHitCollections": ["HcalEndcapCollectionRec"],
    "outputRelationCollections": ["HcalEndcapRelationsSimRec"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"]
}

HCalRingDigi = MarlinProcessorWrapper("HCalRingDigi")
HCalRingDigi.OutputLevel = INFO
HCalRingDigi.ProcessorType = "RealisticCaloDigiScinPpd"
HCalRingDigi.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_mip": ["0.0004725"],
    "inputHitCollections": ["HCalRingCollection"],
    "outputHitCollections": ["HCalRingCollectionDigi"],
    "outputRelationCollections": ["HCalRingRelationsSimDigi"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"],
    "ppd_npix_uncert": ["0"],
    "ppd_pix_spread": ["0"],
    "threshold": ["0.5"],
    "thresholdUnit": ["MIP"],
    #"timingCorrectForPropagation": ["1"],
    "timingCut": ["1"],
    #"timingResolution": ["0"],
    #"timingWindowMax": ["10"],
    #"timingWindowMin": ["-0.5"]
}

HCalRingReco = MarlinProcessorWrapper("HCalRingReco")
HCalRingReco.OutputLevel = INFO
HCalRingReco.ProcessorType = "RealisticCaloRecoScinPpd"
HCalRingReco.Parameters = {
    "CellIDLayerString": ["layer"],
    "calibration_factorsMipGev": ["0.0285819096797"],
    "calibration_layergroups": ["100"],
    "inputHitCollections": ["HCalRingCollectionDigi"],
    "inputRelationCollections": ["HCalRingRelationsSimDigi"],
    "outputHitCollections": ["HCalRingCollectionRec"],
    "outputRelationCollections": ["HCalRingRelationsSimRec"],
    "ppd_mipPe": ["15"],
    "ppd_npix": ["2000"]
}

MuonDigitiser = MarlinProcessorWrapper("MuonDigitiser")
MuonDigitiser.OutputLevel = INFO
MuonDigitiser.ProcessorType = "DDSimpleMuonDigi"
MuonDigitiser.Parameters = {
                            "CalibrMUON": ["70.1"],
                            "MUONCollections": ["YokeBarrelCollection", "YokeEndcapCollection"],
                            "MUONOutputCollection": ["MuonHits"],
                            "MaxHitEnergyMUON": ["2.0"],
                            "MuonThreshold": ["1e-06"],
                            "RelationOutputCollection": ["MuonHitsRelations"]
                            }

FilterDL_VXDB = MarlinProcessorWrapper("FilterDL_VXDB")
FilterDL_VXDB.OutputLevel = INFO
FilterDL_VXDB.ProcessorType = "FilterDoubleLayerHits"
FilterDL_VXDB.Parameters = {
                            "DoubleLayerCuts": ["0", "1", "2.0", "35.0", "2", "3", "1.7", "18.0", "4", "5", "1.5", "10.0", "6", "7", "1.4", "6.5"],
                            "FillHistograms": ["false"],
                            "InputCollection": ["VXDBarrelHits"],
                            "OutputCollection": ["VXDBarrelHits_DLFiltered"],
                            "SubDetectorName": ["Vertex"]
                            }

FilterDL_VXDE = MarlinProcessorWrapper("FilterDL_VXDE")
FilterDL_VXDE.OutputLevel = INFO
FilterDL_VXDE.ProcessorType = "FilterDoubleLayerHits"
FilterDL_VXDE.Parameters = {
                            "DoubleLayerCuts": ["0", "1", "2.2", "8.0", "2", "3", "1.4", "2.8", "4", "5", "0.86", "0.7", "6", "7", "0.7", "0.3"],
                            "FillHistograms": ["false"],
                            "InputCollection": ["VXDEndcapHits"],
                            "OutputCollection": ["VXDEndcapHits_DLFiltered"],
                            "SubDetectorName": ["Vertex"]
                            }

OverlayFull = MarlinProcessorWrapper("OverlayFull")
OverlayFull.OutputLevel = INFO
OverlayFull.ProcessorType = "OverlayTimingRandomMix"
OverlayFull.Parameters = {
    "PathToMuPlus": [the_args.OverlayFullPathToMuPlus],
    "PathToMuMinus": [the_args.OverlayFullPathToMuMinus],
    "Collection_IntegrationTimes": [
        "VertexBarrelCollection", "-0.5", "15.",
        "VertexEndcapCollection", "-0.5", "15.",
        "InnerTrackerBarrelCollection", "-0.5", "15.",
        "InnerTrackerEndcapCollection", "-0.5", "15.",
        "OuterTrackerBarrelCollection", "-0.5", "15.",
        "OuterTrackerEndcapCollection", "-0.5", "15.",
        "ECalBarrelCollection", "-0.5", "15.",
        "ECalPlugCollection", "-0.5", "15.",
        "ECalEndcapCollection", "-0.5", "15.",
        "HCalBarrelCollection", "-0.5", "15.",
        "HCalEndcapCollection", "-0.5", "15.",
        "HCalRingCollection", "-0.5", "15.",
        "YokeBarrelCollection", "-0.5", "15.",
        "YokeEndcapCollection", "-0.5", "15."
    ],
    "IntegrationTimeMin": ["-0.5"],
    "MCParticleCollectionName": ["MCParticle"],
    "MergeMCParticles": ["false"],
    "NumberBackground": [the_args.OverlayFullNumberBackground]
}

OverlayIP = MarlinProcessorWrapper("OverlayIP")
OverlayIP.OutputLevel = INFO
OverlayIP.ProcessorType = "OverlayTimingGeneric"
OverlayIP.Parameters = {
    "AllowReusingBackgroundFiles": ["true"],
    "BackgroundFileNames": [the_args.OverlayIPBackgroundFileNames],
    "Collection_IntegrationTimes": [
        "VertexBarrelCollection", "-0.5", "15.",
        "VertexEndcapCollection", "-0.5", "15.",
        "InnerTrackerBarrelCollection", "-0.5", "15.",
        "InnerTrackerEndcapCollection", "-0.5", "15.",
        "OuterTrackerBarrelCollection", "-0.5", "15.",
        "OuterTrackerEndcapCollection", "-0.5", "15.",
        "ECalBarrelCollection", "-0.5", "15.",
        "ECalPlugCollection", "-0.5", "15.",
        "ECalEndcapCollection", "-0.5", "15.",
        "HCalBarrelCollection", "-0.5", "15.",
        "HCalEndcapCollection", "-0.5", "15.",
        "HCalRingCollection", "-0.5", "15.",
        "YokeBarrelCollection", "-0.5", "15.",
        "YokeEndcapCollection", "-0.5", "15."
    ],
    "Delta_t": ["10000"],
    "IntegrationTimeMin": ["-0.5"],
    "MCParticleCollectionName": ["MCParticle"],
    "MCPhysicsParticleCollectionName": ["MCPhysicsParticles_IP"],
    "MergeMCParticles": ["true"],
    "NBunchtrain": ["1"],
    "NumberBackground": ["1"],
    "PhysicsBX": ["1"],
    "Poisson_random_NOverlay": ["false"],
    "RandomBx": ["false"],
    "StartBackgroundFileIndex": ["0"],
    "TPCDriftvelocity": ["0.05"]
}

algList.append(AIDA)
algList.append(EventNumber)
algList.append(DD4hep)
if the_args.doOverlayFull:
    algList.append(OverlayFull)   # Full BX BIB overlay
if the_args.doOverlayIP:
    algList.append(OverlayIP)     # Incoherent pairs full BX BIB overlay
algList.append(VXDBarrelDigitiser)
algList.append(VXDEndcapDigitiser)
algList.append(ITBarrelDigitiser)
algList.append(ITEndcapDigitiser)
algList.append(OTBarrelDigitiser)
algList.append(OTEndcapDigitiser)
if the_args.doFilterDL:
    algList.append(FilterDL_VXDB)
    algList.append(FilterDL_VXDE)
algList.append(ECalBarrelDigi)
algList.append(ECalBarrelReco)
algList.append(ECalPlugDigi)
algList.append(ECalPlugReco)
algList.append(ECalEndcapDigi)
algList.append(ECalEndcapReco)
algList.append(HCalBarrelDigi)
algList.append(HCalBarrelReco)
algList.append(HCalEndcapDigi)
algList.append(HCalEndcapReco)
algList.append(HCalRingDigi)
algList.append(HCalRingReco)
algList.append(MuonDigitiser)
algList.append(LCIOWriter_all)
algList.append(LCIOWriter_light)

from Configurables import ApplicationMgr
ApplicationMgr( TopAlg = algList,
                EvtSel = 'NONE',
                EvtMax   = -1,
                ExtSvc = [evtsvc],
                OutputLevel=INFO
              )
