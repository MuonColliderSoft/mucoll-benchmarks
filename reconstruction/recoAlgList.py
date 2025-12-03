from Gaudi.Configuration import *

def makeRecoAlgList(the_args):
    '''-------------------------------------------------------------'''
    '''   Add the Reconstruction Algorithms to the Algorithm List   '''
    '''-------------------------------------------------------------'''
    algList = []
    # Merging
    from reco_components.mergers import mergehits_cfg, mergehitsrelations_cfg
    algList.append(mergehits_cfg())
    algList.append(mergehitsrelations_cfg())

    # CKF Tracking
    from reco_components.CKF_tracking import CKFTracker_cfg, deduper_cfg, track_filter_cfg, track_truth_cfg, track_refitter_cfg
    algList.append(CKFTracker_cfg(the_args))
    algList.append(deduper_cfg())
    algList.append(track_filter_cfg())
    algList.append(track_truth_cfg(the_args))
    algList.append(track_refitter_cfg())

    # Track Performance Monitoring
    if the_args.doTrackPerf:
        from reco_components.track_performance import trackTruth_cfg, trackPerf_cfg
        algList.append(trackTruth_cfg())
        algList.append(trackPerf_cfg())

    # Pandora PFOs
    from reco_components.pandora import pandoraPFA_cfg #, fastJet_cfg
    algList.append(pandoraPFA_cfg())
    # algList.append(fastJet_cfg())

    return algList
