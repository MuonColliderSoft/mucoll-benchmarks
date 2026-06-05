from GaudiKernel.Constants import INFO, WARNING
from Configurables import FilterDoubleLayerHits

def filterDL_vertexBarrel_cfg():
    """
    Create a new filter for double layer hits in the vertex detector.
    """
    return FilterDoubleLayerHits(
        "FilterDL_VXDB",
        DoubleLayerCuts = ["0", "1", "2.0", "35.0", "2", "3", "1.7", "18.0", "4", "5", "1.5", "10.0", "6", "7", "1.4", "6.5"],
        FillHistograms = False,
        SubDetectorName = "Vertex",
        InputCollection = ["VXDBarrelHits"],
        OutputCollection = ["VXDBarrelHits_DLFiltered"],
        OutputLevel = INFO
    )

def filterDL_vertexEndcap_cfg():
    """
    Create a new filter for double layer hits in the vertex endcap.
    """
    return FilterDoubleLayerHits(
        "FilterDL_VXDE",
        DoubleLayerCuts = ["0", "1", "2.2", "8.0", "2", "3", "1.4", "2.8", "4", "5", "0.86", "0.7", "6", "7", "0.7", "0.3"],
        FillHistograms = False,
        SubDetectorName = "Vertex",
        InputCollection = ["VXDEndcapHits"],
        OutputCollection = ["VXDEndcapHits_DLFiltered"],
        OutputLevel = INFO
    )