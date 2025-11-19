from GaudiKernel.Constants import INFO, WARNING
from Configurables import OverlayTimingRandomMix

def overlay_full_cfg(args):
    """
    Create a new overlay instance with the given parameters.
    """
    return OverlayTimingRandomMix(
        "OverlayFull",
        BackgroundFileNames = [[args.OverlayFullPathToMuPlus], [args.OverlayFullPathToMuMinus]],
        TimeWindows = {
            "VertexBarrelCollection": [-0.5, 15.],
            "VertexEndcapCollection": [-0.5, 15.],
            "InnerTrackerBarrelCollection": [-0.5, 15.],
            "InnerTrackerEndcapCollection": [-0.5, 15.],
            "OuterTrackerBarrelCollection": [-0.5, 15.],
            "OuterTrackerEndcapCollection": [-0.5, 15.],
            "ECalBarrelCollection": [-0.5, 15.],
            "ECalPlugCollection": [-0.5, 15.],
            "ECalEndcapCollection": [-0.5, 15.],
            "HCalBarrelCollection": [-0.5, 15.],
            "HCalEndcapCollection": [-0.5, 15.],
            "HCalRingCollection": [-0.5, 15.],
            "YokeBarrelCollection": [-0.5, 15.],
            "YokeEndcapCollection": [-0.5, 15.] },
        BackgroundMCParticleCollectionName = "MCParticles",
        MergeMCParticles = False,
        NumberBackground = [args.OverlayFullNumberBackground, args.OverlayFullNumberBackground],
        SimTrackerHits = [
            "VertexBarrelCollection", "VertexEndcapCollection", 
            "InnerTrackerBarrelCollection", "InnerTrackerEndcapCollection",
            "OuterTrackerBarrelCollection", "OuterTrackerEndcapCollection"],
        SimCalorimeterHits = [
            "ECalBarrelCollection", "ECalEndcapCollection", 
            "HCalBarrelCollection", "HCalEndcapCollection",
            "YokeBarrelCollection", "YokeEndcapCollection"],
        MCParticles = ["MCParticles"],
        OutputSimTrackerHits = [
            "OverlayVertexBarrelCollection", "OverlayVertexEndcapCollection", 
            "OverlayInnerTrackerBarrelCollection", "OverlayInnerTrackerEndcapCollection",
            "OverlayOuterTrackerBarrelCollection", "OverlayOuterTrackerEndcapCollection"],
        OutputSimCalorimeterHits = [
            "OverlayECalBarrelCollection", "OverlayECalEndcapCollection", 
            "OverlayHCalBarrelCollection", "OverlayHCalEndcapCollection",
            "OverlayYokeBarrelCollection", "OverlayYokeEndcapCollection"],
        OutputCaloHitContributions = [
            "OverlayECalBarrelContributionCollection", "OverlayECalEndcapContributionCollection",
            "OverlayHCalBarrelContributionCollection", "OverlayHCalEndcapContributionCollection",
            "OverlayYokeBarrelContributionCollection", "OverlayYokeEndcapContributionCollection"],
        OutputLevel = INFO
    )
