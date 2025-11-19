from GaudiKernel.Constants import INFO, WARNING, DEBUG
from Configurables import ACTSSeededCKFTrackingAlg, ACTSDuplicateRemoval, FilterTracksAlg, TrackTruthAlg, RefitFinal

def new_CKFTracker(DetectorSchema, MatFile, TGeoFile, TGeoDescFile):
    """
    Create a new ACTSSeededCKFTrackingAlg instance for CKF tracking.
    """
    if DetectorSchema == "MAIA_v0":
        return ACTSSeededCKFTrackingAlg(
            "Reconstructor",
            MatFile = MatFile,
            TGeoFile = TGeoFile,
            TGeoDescFile = TGeoDescFile,
            DetectorSchema = DetectorSchema,
            RunCKF = "True",
            CKF_Chi2CutOff = 10,
            SeedFinding_RMax = 150,
            SeedFinding_MinPt = 500,
            SeedFinding_ImpactMax = 3,
            CKF_NumMeasurementsCutOff = 1,
            SeedFinding_SigmaScattering = 50,
            SeedFinding_CollisionRegion = 6,
            SeedFinding_RadLengthPerSeed = 0.1,
            SeedingLayers = [
                "13", "2", "13", "6", "13", "10", "13", "14",
                "14", "2", "14", "6", "14", "10", "14", "14",
                "15", "2", "15", "6", "15", "10", "15", "14",
                "8", "2", "17", "2", "18", "2"],
            OutputTrackCollectionName = ["AllTracks"],
            OutputSeedCollectionName = ["SeedTracks"],
            InputTrackerHitCollectionName = ["MergedTrackerHits"],
            OutputLevel = INFO
        )
    else:
        return ACTSSeededCKFTrackingAlg(
            "Reconstructor",
            MatFile = MatFile,
            TGeoFile = TGeoFile,
            TGeoDescFile = TGeoDescFile,
            DetectorSchema = DetectorSchema,
            RunCKF = "True",
            CKF_Chi2CutOff = 10,
            SeedFinding_RMax = 150,
            SeedFinding_MinPt = 500,
            SeedFinding_DeltaRMin = 2,
            SeedFinding_DeltaRMax = 60,
            CKF_NumMeasurementsCutOff = 1,
            SeedFinding_SigmaScattering = 3,
            SeedFinding_CollisionRegion = 3.5,
            SeedFinding_RadLengthPerSeed = 0.1,
            SeedingLayers = [
                "13", "2", "13", "6", "13", "10", "13", "14",
                "14", "2", "14", "6", "14", "10", "14", "14",
                "15", "2", "15", "6", "15", "10", "15", "14"],
            OutputTrackCollectionName = ["AllTracks"],
            OutputSeedCollectionName = ["SeedTracks"],
            InputTrackerHitCollectionName = ["MergedTrackerHits"],
            OutputLevel = INFO
        )

def new_deduper():
    """
    Create a new ACTSDuplicateRemoval instance for removing duplicate tracks.
    """
    return ACTSDuplicateRemoval(
        "Deduper",
        InputTrackCollectionName = ["AllTracks"],
        OutputTrackCollectionName = ["DedupedTracks"],
        OutputLevel = INFO
    )


def new_track_filter():
    """
    Create a new FilterTracksAlg instance for filtering tracks.
    """
    return FilterTracksAlg(
        "Filterer",
        InputTrackCollectionName = ["DedupedTracks"],
        MinPt = "0.5",
        MaxD0 = 10,
        MaxZ0 = 10,
        NHitsInner = "0",
        NHitsOuter = "0",
        NHitsTotal = "0",
        NHitsVertex = "0",
        OutputTrackCollectionName = ["SiTracks"],
        OutputLevel = INFO
    )

def new_track_truth():
    """
    Create a new TrackTruth instance for track truth matching.
    """
    return TrackTruthAlg(
        "TruthMatcher",
        InputTrackCollectionName = ["SiTracks"],
        InputTrackerHit2SimTrackerHitRelationName = ["MergedTrackerHitsRelations"],
        OutputParticle2TrackRelationName = ["SiTrackRelations"],
        OutputLevel = INFO
    )

def new_track_refitter():
    """
    Create a new TrackRefitter instance for refitting tracks.
    """
    return RefitFinal(
        "Refitter",
#        DoCutsOnRedChi2Nhits = True,
        EnergyLossOn = True,
        InputRelationCollectionName = ["SiTrackRelations"],
        InputTrackCollectionName = ["SiTracks"],
        Max_Chi2_Incr = 1.79769e+30,
        MinClustersOnTrackAfterFit = 3,
        MultipleScatteringOn = True,
#        NHitsCuts = ["1,2", "1", "3,4", "1", "5,6", "0"],
        OutputRelationCollectionName = ["SiTracks_Refitted_Relation"],
        OutputTrackCollectionName = ["SiTracks_Refitted"],
#        ReducedChi2Cut = 10.,
        ReferencePoint = -1,
        SmoothOn = False,
        extrapolateForward = True,
        OutputLevel = INFO
    )
