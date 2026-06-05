from GaudiKernel.Constants import INFO, WARNING, DEBUG
from Configurables import TrackTruthAlg, TrackPerfHistAlg

def trackTruth_cfg():
    """
    Create a new TrackTruthAlg instance for associating tracks with MC particles.
    """
    return TrackTruthAlg(
        "AssociationCreator",
        OutputParticle2TrackRelationName = ["MCParticle_SiTracks"],
        InputTrackCollectionName = ["SiTracks"],
        InputTrackerHit2SimTrackerHitRelationName = ["MergedTrackerHitsRelations"],
        OutputLevel = INFO
    )

def trackPerf_cfg():
    """
    Create a new TrackPerfHistAlg instance for analyzing track performance.
    """
    return TrackPerfHistAlg(
        "TrackPerformance",
        InputMCParticleCollectionName = ["MCParticles"],
        InputMCTrackRelationCollectionName = ["MCParticle_SiTracks"],
        InputTrackCollectionName = ["SiTracks"],
        OutputLevel = INFO
    )
