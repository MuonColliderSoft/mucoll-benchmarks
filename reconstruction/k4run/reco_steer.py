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
    "--MatFile",
    help="Material maps file for tracking",
    type=str,
    default="/path/to/material-maps.json",
)

parser.add_argument(
    "--TGeoFile",
    help="TGeometry file for tracking",
    type=str,
    default="/path/to/tgeo.root",
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

Config = MarlinProcessorWrapper("Config")
Config.OutputLevel = INFO
Config.ProcessorType = "CLICRecoConfig"
Config.Parameters = {
                     "VertexUnconstrained": ["OFF"],
                     "VertexUnconstrainedChoices": ["ON", "OFF"]
                     }

AIDA = MarlinProcessorWrapper("AIDA")
AIDA.OutputLevel = INFO
AIDA.ProcessorType = "AIDAProcessor"
AIDA.Parameters = {
                   "Compress": ["1"],
                   "FileName": ["output_reco"],
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
                             "LCIOOutputFile": ["output_reco.slcio"],
                             "LCIOWriteMode": ["WRITE_NEW"]
                             }

LCIOWriter_light = MarlinProcessorWrapper("LCIOWriter_light")
LCIOWriter_light.OutputLevel = INFO
LCIOWriter_light.ProcessorType = "LCIOOutputProcessor"
LCIOWriter_light.Parameters = {
                               "DropCollectionNames": [],
                               "DropCollectionTypes": ["SimCalorimeterHit", "CalorimeterHit", "SimTrackerHit", "TrackerHitPlane", "Track", "LCRelation"],
                               "FullSubsetCollections": [],
                               "KeepCollectionNames": ["SiTracks_Refitted", "SiTracks_Refitted_Relations", "PandoraPFOs", "MCPhysicsParticle"],
                               "LCIOOutputFile": ["output_reco_light.slcio"],
                               "LCIOWriteMode": ["WRITE_NEW"]
                               }

CKFTracking = MarlinProcessorWrapper("CKFTracking")
CKFTracking.OutputLevel = INFO
CKFTracking.ProcessorType = "ACTSSeededCKFTrackingProc"
CKFTracking.Parameters = {
    "CKF_Chi2CutOff": ["10"],
    "CKF_NumMeasurementsCutOff": ["1"],
    "MatFile": [the_args.MatFile],
    "PropagateBackward": ["False"],
    "RunCKF": ["True"],
    "SeedFinding_CollisionRegion": ["3.5"],
    "SeedFinding_DeltaRMax": ["60"],
    "SeedFinding_DeltaRMin": ["2"],
    "SeedFinding_DeltaRMaxBottom": ["50"],
    "SeedFinding_DeltaRMaxTop": ["50"],
    "SeedFinding_DeltaRMinBottom": ["5"],
    "SeedFinding_DeltaRMinTop": ["2"],
    "SeedFinding_ImpactMax": ["3"],
    "SeedFinding_MinPt": ["500"],
    "SeedFinding_RMax": ["150"],
    "SeedFinding_ZMax": ["500"],
    "SeedFinding_RadLengthPerSeed": ["0.1"],
    "SeedFinding_zBottomBinLen": ["1"],
    "SeedFinding_zTopBinLen": ["1"],
    "SeedFinding_phiBottomBinLen": ["1"],
    "SeedFinding_phiTopBinLen": ["1"],
    "SeedFinding_SigmaScattering": ["3"],
    "SeedingLayers": [
        "13", "2", "13", "6", "13", "10", "13", "14", 
        "14", "2", "14", "6", "14", "10", "14", "14", 
        "15", "2", "15", "6", "15", "10", "15", "14",
        ],
    "TGeoFile": [the_args.TGeoFile],
    "TrackCollectionName": ["AllTracks"],
    "TrackerHitCollectionNames": ["VXDBarrelHits", "ITBarrelHits", "OTBarrelHits", "VXDEndcapHits", "ITEndcapHits", "OTEndcapHits"],
    "CaloFace_Radius": ["1500"],
    "CaloFace_Z": ["2307"]
}

TrackDeduplication = MarlinProcessorWrapper("TrackDeduplication")
TrackDeduplication.OutputLevel = INFO
TrackDeduplication.ProcessorType = "ACTSDuplicateRemoval"
TrackDeduplication.Parameters = {
                                 "InputTrackCollectionName": ["AllTracks"],
                                 "OutputTrackCollectionName": ["SiTracks"]
                                 }


DDMarlinPandora = MarlinProcessorWrapper("DDMarlinPandora")
DDMarlinPandora.OutputLevel = INFO
DDMarlinPandora.ProcessorType = "DDPandoraPFANewProcessor"
DDMarlinPandora.Parameters = {
                              "ClusterCollectionName": ["PandoraClusters"],
                              "CreateGaps": ["false"],
                              "CurvatureToMomentumFactor": ["0.00015"],
                              "D0TrackCut": ["200"],
                              "D0UnmatchedVertexTrackCut": ["5"],
                              "DigitalMuonHits": ["0"],
                              "ECalBarrelNormalVector": ["0", "0", "1"],
                              "ECalCaloHitCollections": ["EcalBarrelCollectionRec", "EcalEndcapCollectionRec", "EcalPlugCollectionRec"],
                              "ECalMipThreshold": ["0.5"],
                              "ECalScMipThreshold": ["0"],
                              "ECalScToEMGeVCalibration": ["1"],
                              "ECalScToHadGeVCalibrationBarrel": ["1"],
                              "ECalScToHadGeVCalibrationEndCap": ["1"],
                              "ECalScToMipCalibration": ["1"],
                              "ECalSiMipThreshold": ["0"],
                              "ECalSiToEMGeVCalibration": ["1"],
                              "ECalSiToHadGeVCalibrationBarrel": ["1"],
                              "ECalSiToHadGeVCalibrationEndCap": ["1"],
                              "ECalSiToMipCalibration": ["1"],
                              "ECalToEMGeVCalibration": ["1.02373335516"],
                              "ECalToHadGeVCalibrationBarrel": ["1.24223718397"],
                              "ECalToHadGeVCalibrationEndCap": ["1.24223718397"],
                              "ECalToMipCalibration": ["181.818"],
                              "EMConstantTerm": ["0.01"],
                              "EMStochasticTerm": ["0.17"],
                              "FinalEnergyDensityBin": ["110."],
                              "HCalBarrelNormalVector": ["0", "0", "1"],
                              "HCalCaloHitCollections": ["HcalBarrelCollectionRec", "HcalEndcapCollectionRec", "HcalRingCollectionRec"],
                              "HCalMipThreshold": ["0.3"],
                              "HCalToEMGeVCalibration": ["1.02373335516"],
                              "HCalToHadGeVCalibration": ["1.01799349172"],
                              "HCalToMipCalibration": ["40.8163"],
                              "HadConstantTerm": ["0.03"],
                              "HadStochasticTerm": ["0.6"],
                              "InputEnergyCorrectionPoints": [],
                              "KinkVertexCollections": ["KinkVertices"],
                              "LayersFromEdgeMaxRearDistance": ["250"],
                              "MCParticleCollections": ["MCParticle"],
                              "MaxBarrelTrackerInnerRDistance": ["200"],
                              "MaxClusterEnergyToApplySoftComp": ["2000."],
                              "MaxHCalHitHadronicEnergy": ["1000000"],
                              "MaxTrackHits": ["5000"],
                              "MaxTrackSigmaPOverP": ["0.15"],
                              "MinBarrelTrackerHitFractionOfExpected": ["0"],
                              "MinCleanCorrectedHitEnergy": ["0.1"],
                              "MinCleanHitEnergy": ["0.5"],
                              "MinCleanHitEnergyFraction": ["0.01"],
                              "MinFtdHitsForBarrelTrackerHitFraction": ["0"],
                              "MinFtdTrackHits": ["0"],
                              "MinMomentumForTrackHitChecks": ["0"],
                              "MinTpcHitFractionOfExpected": ["0"],
                              "MinTrackECalDistanceFromIp": ["0"],
                              "MinTrackHits": ["0"],
                              "MuonBarrelBField": ["-1.34"],
                              "MuonCaloHitCollections": ["MuonHits"],
                              "MuonEndCapBField": ["0.01"],
                              "MuonHitEnergy": ["0.5"],
                              "MuonToMipCalibration": ["19607.8"],
                              "NEventsToSkip": ["0"],
                              "NOuterSamplingLayers": ["3"],
                              "OutputEnergyCorrectionPoints": [],
                              "PFOCollectionName": ["PandoraPFOs"],
                              "PandoraSettingsXmlFile": ["PandoraSettings/PandoraSettingsDefault.xml"],
                              "ProngVertexCollections": ["ProngVertices"],
                              "ReachesECalBarrelTrackerOuterDistance": ["-100"],
                              "ReachesECalBarrelTrackerZMaxDistance": ["-50"],
                              "ReachesECalFtdZMaxDistance": ["1"],
                              "ReachesECalMinFtdLayer": ["0"],
                              "ReachesECalNBarrelTrackerHits": ["0"],
                              "ReachesECalNFtdHits": ["0"],
                              "RelCaloHitCollections": ["CaloHitsRelations", "MuonHitsRelations"],
                              "RelTrackCollections": ["SiTracks_Relations"],
                              "ShouldFormTrackRelationships": ["1"],
                              "SoftwareCompensationEnergyDensityBins": ["0", "2.", "5.", "7.5", "9.5", "13.", "16.", "20.", "23.5", "28.", "33.", "40.", "50.", "75.", "100."],
                              "SoftwareCompensationWeights": ["1.61741", "-0.00444385", "2.29683e-05", "-0.0731236", "-0.00157099", "-7.09546e-07", "0.868443", "1.0561", "-0.0238574"],
                              "SplitVertexCollections": ["SplitVertices"],
                              "StartVertexAlgorithmName": ["PandoraPFANew"],
                              "StartVertexCollectionName": ["PandoraStartVertices"],
                              "StripSplittingOn": ["0"],
                              "TrackCollections": ["SiTracks"],
                              "TrackCreatorName": ["DDTrackCreatorCLIC"],
                              "TrackStateTolerance": ["0"],
                              "TrackSystemName": ["DDKalTest"],
                              "UnmatchedVertexTrackMaxEnergy": ["5"],
                              "UseEcalScLayers": ["0"],
                              "UseNonVertexTracks": ["1"],
                              "UseOldTrackStateCalculation": ["0"],
                              "UseUnmatchedNonVertexTracks": ["0"],
                              "UseUnmatchedVertexTracks": ["1"],
                              "V0VertexCollections": ["V0Vertices"],
                              "YokeBarrelNormalVector": ["0", "0", "1"],
                              "Z0TrackCut": ["200"],
                              "Z0UnmatchedVertexTrackCut": ["5"],
                              "ZCutForNonVertexTracks": ["250"]
                              }

PFOSelection = MarlinProcessorWrapper("PFOSelection")
PFOSelection.OutputLevel = INFO
PFOSelection.ProcessorType = "CLICPfoSelector"
PFOSelection.Parameters = {
                           "ChargedPfoLooseTimingCut": ["3"],
                           "ChargedPfoNegativeLooseTimingCut": ["-1"],
                           "ChargedPfoNegativeTightTimingCut": ["-0.5"],
                           "ChargedPfoPtCut": ["0"],
                           "ChargedPfoPtCutForLooseTiming": ["4"],
                           "ChargedPfoTightTimingCut": ["1.5"],
                           "CheckKaonCorrection": ["0"],
                           "CheckProtonCorrection": ["0"],
                           "ClusterLessPfoTrackTimeCut": ["10"],
                           "CorrectHitTimesForTimeOfFlight": ["0"],
                           "DisplayRejectedPfos": ["1"],
                           "DisplaySelectedPfos": ["1"],
                           "FarForwardCosTheta": ["0.975"],
                           "ForwardCosThetaForHighEnergyNeutralHadrons": ["0.95"],
                           "ForwardHighEnergyNeutralHadronsEnergy": ["10"],
                           "HCalBarrelLooseTimingCut": ["20"],
                           "HCalBarrelTightTimingCut": ["10"],
                           "HCalEndCapTimingFactor": ["1"],
                           "InputPfoCollection": ["PandoraPFOs"],
                           "KeepKShorts": ["1"],
                           "MaxMomentumForClusterLessPfos": ["2"],
                           "MinECalHitsForTiming": ["5"],
                           "MinHCalEndCapHitsForTiming": ["5"],
                           "MinMomentumForClusterLessPfos": ["0.5"],
                           "MinPtForClusterLessPfos": ["0.5"],
                           "MinimumEnergyForNeutronTiming": ["1"],
                           "Monitoring": ["0"],
                           "MonitoringPfoEnergyToDisplay": ["1"],
                           "NeutralFarForwardLooseTimingCut": ["2"],
                           "NeutralFarForwardTightTimingCut": ["1"],
                           "NeutralHadronBarrelPtCutForLooseTiming": ["3.5"],
                           "NeutralHadronLooseTimingCut": ["2.5"],
                           "NeutralHadronPtCut": ["0"],
                           "NeutralHadronPtCutForLooseTiming": ["8"],
                           "NeutralHadronTightTimingCut": ["1.5"],
                           "PhotonFarForwardLooseTimingCut": ["2"],
                           "PhotonFarForwardTightTimingCut": ["1"],
                           "PhotonLooseTimingCut": ["2"],
                           "PhotonPtCut": ["0"],
                           "PhotonPtCutForLooseTiming": ["4"],
                           "PhotonTightTimingCut": ["1"],
                           "PtCutForTightTiming": ["0.75"],
                           "SelectedPfoCollection": ["SelectedPandoraPFOs"],
                           "UseClusterLessPfos": ["1"],
                           "UseNeutronTiming": ["0"]
                           }

FastJetProcessor = MarlinProcessorWrapper("FastJetProcessor")
FastJetProcessor.OutputLevel = INFO
FastJetProcessor.ProcessorType = "FastJetProcessor"
FastJetProcessor.Parameters = {
    "algorithm": ["antikt_algorithm", "0.4"],
    "clusteringMode": ["Inclusive", "5"],
    "jetOut": ["JetOut"],
    "recParticleIn": ["SelectedPandoraPFOs"],
    "recombinationScheme": ["E_scheme"]
}

algList.append(AIDA)
algList.append(EventNumber)
algList.append(Config)
algList.append(DD4hep)
algList.append(CKFTracking)
algList.append(TrackDeduplication)
algList.append(DDMarlinPandora)
algList.append(PFOSelection)
algList.append(FastJetProcessor)
algList.append(LCIOWriter_all)
algList.append(LCIOWriter_light)

from Configurables import ApplicationMgr
ApplicationMgr( TopAlg = algList,
                EvtSel = 'NONE',
                EvtMax   = -1,
                ExtSvc = [evtsvc],
                OutputLevel=INFO
              )
