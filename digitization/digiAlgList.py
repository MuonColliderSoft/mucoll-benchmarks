from GaudiKernel.Constants import INFO, WARNING

def makeDigiAlgList(the_args):
    '''-------------------------------------------------------------'''
    '''    Add the Digitization Algorithms to the Algorithm List    '''
    '''-------------------------------------------------------------'''
    algList = []
    # Event Counter
    from event_counter import event_counter_cfg
    algList.append(event_counter_cfg())

    # BIB Overlay
    if the_args.doOverlayFull:
        from digi_components.overlay_full import overlay_full_cfg
        algList.append(overlay_full_cfg(the_args))

    # Tracker Digitization
    from digi_components.tracking_vertex import VXDBarrel_cfg, VXDEndcap_cfg
    from digi_components.tracking_inner import ITBarrel_cfg, ITEndcap_cfg
    from digi_components.tracking_outer import OTBarrel_cfg, OTEndcap_cfg
    algList.append(VXDBarrel_cfg(the_args))
    algList.append(VXDEndcap_cfg(the_args))
    algList.append(ITBarrel_cfg(the_args))
    algList.append(ITEndcap_cfg(the_args))
    algList.append(OTBarrel_cfg(the_args))
    algList.append(OTEndcap_cfg(the_args))

    # EM, Hadronic, Muon Calorimeter Digitization
    from digi_components.calorimetry_EM import ECalBarrelDigi_cfg, ECalBarrelReco_cfg
    from digi_components.calorimetry_EM import ECalPlugDigi_cfg, ECalPlugReco_cfg
    from digi_components.calorimetry_EM import ECalEndcapDigi_cfg, ECalEndcapReco_cfg
    algList.append(ECalBarrelDigi_cfg(the_args))
    algList.append(ECalBarrelReco_cfg())
    #algList.append(ECalPlugDigi_cfg(the_args))
    #algList.append(ECalPlugReco_cfg())
    algList.append(ECalEndcapDigi_cfg(the_args))
    algList.append(ECalEndcapReco_cfg())
    from digi_components.calorimetry_HAD import HCalBarrelDigi_cfg, HCalBarrelReco_cfg
    from digi_components.calorimetry_HAD import HCalEndcapDigi_cfg, HCalEndcapReco_cfg
    from digi_components.calorimetry_HAD import HCalRingDigi_cfg, HCalRingReco_cfg
    algList.append(HCalBarrelDigi_cfg(the_args))
    algList.append(HCalBarrelReco_cfg())
    algList.append(HCalEndcapDigi_cfg(the_args))
    algList.append(HCalEndcapReco_cfg())
    #algList.append(HCalRingDigi_cfg(the_args))
    #algList.append(HCalRingReco_cfg())
    from digi_components.calorimetry_MU import MuonBarrelDigi_cfg, MuonEndcapDigi_cfg
    algList.append(MuonBarrelDigi_cfg(the_args))
    algList.append(MuonEndcapDigi_cfg(the_args))

    # Vertex Filtering
    if the_args.doFilterDL:
        from digi_components.filterDL_vertex import filterDL_vertexBarrel_cfg, filterDL_vertexEndcap_cfg
        algList.append(filterDL_vertexBarrel_cfg())
        algList.append(filterDL_vertexEndcap_cfg())

    return algList
