from .atlantic import parse_atlantic
from .jadia import parse_jadia
from .leisure_frontier import parse_leisure_frontier
from .ridewell import parse_ridewell
from .tong_tar import parse_tong_tar

PARSERS = {
    "tong_tar": parse_tong_tar,
    "leisure_frontier": parse_leisure_frontier,
    "atlantic": parse_atlantic,
    "ridewell": parse_ridewell,
    "jadia": parse_jadia,
}

