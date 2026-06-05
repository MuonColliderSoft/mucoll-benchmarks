from Configurables import EventCounter
from GaudiKernel.Constants import INFO
def event_counter_cfg():
    """
    Create a new EventCounter instance with the given parameters.
    """
    return EventCounter(
        "EventCounter",
        Frequency = 10,
        OutputLevel = INFO
    )