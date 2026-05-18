from GaudiKernel.Constants import INFO, WARNING, DEBUG
from Configurables import CollectionMerger

def mergehits_cfg():
    """
    Create a new CollectionMerger instance for merging hits.
    """
    return CollectionMerger(
        "MergeHits",
        InputCollections = ["VXDBarrelHits", "ITBarrelHits", "OTBarrelHits", "VXDEndcapHits", "ITEndcapHits", "OTEndcapHits"],
        OutputCollection = "MergedTrackerHits",
        OutputLevel = INFO
    )

def mergehitsrelations_cfg():
    """
    Create a new CollectionMerger instance for merging hits relations.
    """
    return CollectionMerger(
        "MergeHitsRelations",
        InputCollections = ["VXDBarrelHitsRelations", "ITBarrelHitsRelations", "OTBarrelHitsRelations",
                            "VXDEndcapHitsRelations", "ITEndcapHitsRelations", "OTEndcapHitsRelations"],
        OutputCollection = "MergedTrackerHitsRelations",
        OutputLevel = INFO
    )
