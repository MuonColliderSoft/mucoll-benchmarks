def choose_parallelism():
    """Set number of threads based CPU count"""
    import os
    
    cpu_count = os.cpu_count()
    if cpu_count is None:
        return 1
    elif cpu_count <= 4:
        return cpu_count
    else:
        return cpu_count - 2

def get_mt_args():
    """Parse command line arguments for multi-threading configuration."""
    from k4FWCore.parseArgs import parser
    
    parser.add_argument(
        "--useMT",
        help="Enable multi-threading",
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--numThreads",
        help="Number of threads to use",
        type=int,
        default=choose_parallelism(),
    )

    return parser.parse_known_args()[0]

def get_k4run_mt(threads, event_slots):
    """Create a k4run instance configured for multi-threading."""
    from Gaudi.Configuration import INFO, WARNING
    from Configurables import HiveWhiteBoard, HiveSlimEventLoopMgr, AvalancheSchedulerSvc

    wb = HiveWhiteBoard(
        "EventDataSvc", 
    #    EventSlots = event_slots,
    )
    elm = HiveSlimEventLoopMgr(
        "HiveSlimEventLoopMgr",
        SchedulerName = "AvalancheSchedulerSvc",
        OutputLevel = WARNING,
    )
    sch = AvalancheSchedulerSvc(
        ThreadPoolSize = threads,
        ShowDataFlow = True,
        OutputLevel = WARNING,
    )

    return wb, elm, sch