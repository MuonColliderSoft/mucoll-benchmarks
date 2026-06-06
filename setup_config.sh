box_width=70

_mucoll_center_line() {
    local text="$1"
    local len=${#text}
    local pad=$(( (box_width - len) / 2 ))
    if [ "$pad" -lt 0 ]; then
        pad=0
    fi
    printf "   │%*s%s%*s│\n" "$pad" "" "$text" "$((box_width - pad - len))" ""
}

_mucoll_box_error() {
    local title="$1"
    local detail="$2"
    echo "   ╭──────────────────────────────────────────────────────────────────────╮"
    _mucoll_center_line "$title"
    if [ -n "$detail" ]; then
        _mucoll_center_line "$detail"
    fi
    echo "   ╰──────────────────────────────────────────────────────────────────────╯"
}

_mucoll_prepend_pythonpath() {
    local path="$1"
    case ":${PYTHONPATH:-}:" in
        *":${path}:"*) ;;
        *) export PYTHONPATH="${path}${PYTHONPATH:+:${PYTHONPATH}}" ;;
    esac
}

if [ $# -gt 2 ]; then
    echo "usage: source setup_config.sh [mucoll-benchmarks] [Geometry Name]"
    return 1
fi

if [ $# -ge 1 ]; then
    if [[ "$1" != /* ]]; then
        MUCOLL_BENCHMARKS="$(realpath "$1")"
    else
        MUCOLL_BENCHMARKS="$1"
    fi
else
    MUCOLL_BENCHMARKS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ ! -d "${MUCOLL_BENCHMARKS}" ]; then
    _mucoll_box_error "Benchmark directory does not exist" "${MUCOLL_BENCHMARKS}"
    return 1
fi

if [ $# -eq 2 ]; then
    GEOM_NAME="$2"
else
    GEOM_NAME="MAIA_v0"
fi

if [[ "$GEOM_NAME" == *MAIA* ]]; then
    GEOM_TYPE="MAIA"
    CONFIG_NAME="MAIAConfig"
elif [[ "$GEOM_NAME" == *MuSIC* ]]; then
    GEOM_TYPE="MuSIC"
    CONFIG_NAME="MuSICConfig"
elif [[ "$GEOM_NAME" == *MuColl* ]]; then
    GEOM_TYPE="MuColl"
    CONFIG_NAME="MuCollConfig"
else
    _mucoll_box_error "Unknown geometry type in argument" "$GEOM_NAME"
    return 1
fi

CONFIG_PATH="${MUCOLL_BENCHMARKS}/configs/${CONFIG_NAME}"
CONFIG_PACKAGE_PATH="${CONFIG_PATH}/${CONFIG_NAME}"
if [ ! -d "$CONFIG_PACKAGE_PATH" ]; then
    _mucoll_box_error "Config package not found" "$CONFIG_PACKAGE_PATH"
    return 1
fi

GEO_BASE="${MUCOLL_GEO_BASE:-/opt/spack/opt/spack}"
GEO_DIR=$(find "$GEO_BASE"/*/*/*/*/linux-x86_64/k4geo*/share/k4geo/MuColl/"$GEOM_TYPE"/compact/"$GEOM_NAME"/ 2>/dev/null | head -n 1)
if [ -n "$GEO_DIR" ]; then
    if [[ "$GEOM_TYPE" == "MuColl" ]]; then
        XML_NAME="${GEOM_NAME%%.*}.xml"
    else
        XML_NAME="${GEOM_NAME}.xml"
    fi
    GEO_PATH="$GEO_DIR/$XML_NAME"
else
    GEO_PATH=""
fi

if [ ! -f "$GEO_PATH" ]; then
    _mucoll_box_error "Geometry file not found for" "$GEOM_NAME"
    return 1
fi

k4AT_DIR=$(find "$GEO_BASE"/*/*/*/*/linux-x86_64/k4actstracking*/share/k4ActsTracking/data/ 2>/dev/null | head -n 1)
if [ -z "$k4AT_DIR" ]; then
    _mucoll_box_error "k4ActsTracking data directory not found" "$GEO_BASE"
    return 1
fi

if [[ "$GEOM_TYPE" == "MuColl" ]]; then
    START_NAME="${GEOM_NAME%%.*}"
else
    START_NAME="${GEOM_NAME}"
fi

if [ ! -f "$k4AT_DIR/${START_NAME}.root" ]; then
    _mucoll_box_error "TGeo file not found for" "$GEOM_NAME"
    return 1
fi

if [ ! -f "$k4AT_DIR/${START_NAME}.json" ]; then
    _mucoll_box_error "Subdetector JSON file not found for" "$GEOM_NAME"
    return 1
fi

if [[ "$GEOM_TYPE" == "MAIA" ]]; then
    MATMAP_PATH="$k4AT_DIR/MAIA_v0_material.json"
else
    MATMAP_PATH="$k4AT_DIR/material-maps.json"
fi
if [ ! -f "$MATMAP_PATH" ]; then
    _mucoll_box_error "Material map file not found" "$(basename "$MATMAP_PATH")"
    return 1
fi

export MUCOLL_GEOM_NAME="$GEOM_NAME"
export MUCOLL_GEO="$GEO_PATH"
export MUCOLL_TGEO="$k4AT_DIR/${START_NAME}.root"
export MUCOLL_TGEO_DESC="$k4AT_DIR/${START_NAME}.json"
export MUCOLL_MATMAP="$MATMAP_PATH"
export MUCOLL_CONFIG="$CONFIG_PATH"
export MUCOLL_CONFIG_NAME="$CONFIG_NAME"

_mucoll_prepend_pythonpath "$CONFIG_PACKAGE_PATH"
_mucoll_prepend_pythonpath "$CONFIG_PATH"
_mucoll_prepend_pythonpath "${MUCOLL_BENCHMARKS}/common"

echo ""
echo "   ╭──────────────────────────────────────────────────────────────────────╮"
_mucoll_center_line "Setting Muon Collider configuration"
echo "   ├──────────────────────────────────────────────────────────────────────┤"

vars=(MUCOLL_GEOM_NAME MUCOLL_CONFIG_NAME MUCOLL_CONFIG MUCOLL_GEO MUCOLL_TGEO MUCOLL_MATMAP MUCOLL_TGEO_DESC)
maxlen=0
for var in "${vars[@]}"; do
    len=${#var}
    (( len > maxlen )) && maxlen=$len
done

for var in "${vars[@]}"; do
    value="${!var}"
    if [ -f "$value" ]; then
        shown="$(basename "$value")"
    else
        shown="$value"
    fi
    line=$(printf "%-${maxlen}s = %s" "$var" "$shown")
    _mucoll_center_line "$line"
done

echo "   ╰──────────────────────────────────────────────────────────────────────╯"
echo ""
