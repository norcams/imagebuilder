#!/usr/bin/bash
#
# Build NREC images sequentially, one after another, in place of a cron job
# per image.
#
# The colour palette and the XY/line/cnt helpers below are kept whole for
# future use, so unused variables and uncalled functions are expected here
# shellcheck disable=SC2034,SC2329

# Continue past a failed build, but treat unset variables and broken pipes as
# errors. Not -e: one image failing must not stop the rest of the run
set -uo pipefail

#--------------------------------------------------------------------+
#Color picker, usage: printf ${BLD}${CUR}${RED}${BBLU}"Hello!)"${DEF}|
#-------------------------+--------------------------------+---------+
#       Text color        |       Background color         |         |
#-----------+-------------+--------------+-----------------+         |
# Base color|Lighter shade|  Base color  | Lighter shade   |         |
#-----------+-------------+--------------+-----------------+         |
BLK='\e[30m'; blk='\e[90m'; BBLK='\e[40m'; bblk='\e[100m' #| Black   |
RED='\e[31m'; red='\e[91m'; BRED='\e[41m'; bred='\e[101m' #| Red     |
GRN='\e[32m'; grn='\e[92m'; BGRN='\e[42m'; bgrn='\e[102m' #| Green   |
YLW='\e[33m'; ylw='\e[93m'; BYLW='\e[43m'; bylw='\e[103m' #| Yellow  |
BLU='\e[34m'; blu='\e[94m'; BBLU='\e[44m'; bblu='\e[104m' #| Blue    |
MGN='\e[35m'; mgn='\e[95m'; BMGN='\e[45m'; bmgn='\e[105m' #| Magenta |
CYN='\e[36m'; cyn='\e[96m'; BCYN='\e[46m'; bcyn='\e[106m' #| Cyan    |
WHT='\e[37m'; wht='\e[97m'; BWHT='\e[47m'; bwht='\e[107m' #| White   |
#----------------------------------------------------------+---------+
# Effects                                                            |
#--------------------------------------------------------------------+
DEF='\e[0m'   #Default color and effects                             |
BLD='\e[1m'   #Bold\brighter                                         |
DIM='\e[2m'   #Dim\darker                                            |
CUR='\e[3m'   #Italic font                                           |
UND='\e[4m'   #Underline                                             |
INV='\e[7m'   #Inverted                                              |
COF='\e[?25l' #Cursor Off                                            |
CON='\e[?25h' #Cursor On                                             |
#--------------------------------------------------------------------+
# Text positioning, usage: XY 10 10 "Hello World!"                   |
# shellcheck disable=SC2059
XY   () { printf "\e[${2};${1}H${3}";   } #                          |
#--------------------------------------------------------------------+
# Print line, usage: line - 10 | line -= 20 | line "Hello World!" 20 |
# shellcheck disable=SC2059
line () { printf -v LINE "%$2s"; printf -- "${LINE// /$1}"; } #      |
# Create sequence like {0..X}                                        |
# shellcheck disable=SC2059,SC2086,SC2206
cnt () { printf -v _N %$1s; _N=(${_N// / 1}); printf "${!_N[*]}"; } #|
#--------------------------------------------------------------------+

# Under cron stdout is a pipe, and the escape sequences above would end up
# verbatim in the log and in the mail. Blank the palette unless we are on a
# terminal
if [ ! -t 1 ]; then
    for _colour in BLK blk BBLK bblk RED red BRED bred GRN grn BGRN bgrn \
                   YLW ylw BYLW bylw BLU blu BBLU bblu MGN mgn BMGN bmgn \
                   CYN cyn BCYN bcyn WHT wht BWHT bwht \
                   DEF BLD DIM CUR UND INV COF CON; do
        printf -v "$_colour" '%s' ''
    done
    unset _colour
fi

# Set path
PATH=/usr/bin:/usr/sbin
export PATH

# Variables. Overridable so the script can be exercised outside a builder node
BUILD_PATH=${BUILD_PATH:-/home/imagebuilder/build_scripts}
LOG_PATH=${LOG_PATH:-/var/log/imagebuilder}
TEMPLATE_ROOT=${TEMPLATE_ROOT:-/etc/imagebuilder}
LOCK_FILE=${LOCK_FILE:-${LOG_PATH}/build-images.lock}

#---------------------------------------------------------------------
# Image categories
#
# Everything that differs between kinds of image lives here. Adding a
# category means adding a line to each map below and a letter to the getopts
# string, rather than another array, another flag and another build loop.
#---------------------------------------------------------------------

# Build order
CATEGORIES=(std uib gpu win)

# How a build script name maps to a category. std has no pattern: it is the
# fallback for anything the others do not claim
declare -A CATEGORY_PATTERN=(
    [uib]='_uib_puppet$'
    [gpu]='_nv_vgpu$'
    [win]='^winsrv_.*_wrapper$'
)

# The template directory imagebuilder should use
declare -A CATEGORY_TEMPLATE=(
    [std]="${TEMPLATE_ROOT}/default"
    [uib]="${TEMPLATE_ROOT}/uib_puppet"
    [gpu]="${TEMPLATE_ROOT}/nv_vgpu"
    [win]="${TEMPLATE_ROOT}/default"
)

# What -l and the summary call them
declare -A CATEGORY_LABEL=(
    [std]='Standard images'
    [uib]='UiB images'
    [gpu]='vGPU images'
    [win]='Windows images'
)

# The option that selects a whole category
declare -A OPTION_CATEGORY=(
    [S]=std
    [B]=uib
    [G]=gpu
    [W]=win
)

# Windows builds are not wired up yet. Listing and selecting them works, so
# that turning this off is the only change needed later
WIN_PLACEHOLDER=1

# Every build script found, and which category it belongs to. One map rather
# than an array per category: bash has no arrays of arrays, and the nameref
# tricks that fake them are not worth the reading
declare -A IMAGE_CATEGORY=()
declare -a ALL_IMAGES=()

# Images to build, and the categories selected wholesale with -S/-B/-G/-W
declare -a SELECTED=()
declare -A SELECT_ALL=()

# Option variables
LIST=0
DRYRUN=0
TIMEOUT=0

# Every -i given, kept so they can be checked before anything is built
requested_images=()

# Outcomes, for the summary and the exit code
built_images=()
failed_images=()
skipped_images=()

#---------------------------------------------------------------------
# Functions
#---------------------------------------------------------------------

# Which category a build script name belongs to. Used for both discovery and
# -i, so the two cannot disagree about what a name means
categorise() {
    local name=$1 cat
    for cat in "${CATEGORIES[@]}"; do
        [ -n "${CATEGORY_PATTERN[$cat]:-}" ] || continue
        if [[ $name =~ ${CATEGORY_PATTERN[$cat]} ]]; then
            printf '%s' "$cat"
            return
        fi
    done
    printf 'std'
}

# Seconds as 1h02m03s, dropping the units that are zero
duration() {
    local total=$1
    if [ "$total" -ge 3600 ]; then
        printf '%dh%02dm%02ds' $((total / 3600)) $((total % 3600 / 60)) $((total % 60))
    elif [ "$total" -ge 60 ]; then
        printf '%dm%02ds' $((total / 60)) $((total % 60))
    else
        printf '%ds' "$total"
    fi
}

usage() {
    echo "Usage: $0 [-h] [-S] [-B] [-G] [-W] [-t <sec>] [-l] [-i <image>]..."
    echo
    echo 'Options:'
    echo '  -S  Build all standard images. Negates -i options'
    echo '  -B  Build all UiB images. Negates -i options'
    echo '  -G  Build all vgpu images. Negates -i options'
    echo '  -W  Build all Windows images. Negates -i options'
    echo '  -i  Specify image to build. Can be used multiple times'
    echo '  -t  Terminate build job if still running after this duration. See timeout(1)'
    echo '  -l  List all images and exit'
    echo '  -n  Dry-run: Only show what would be done'
    echo '  -h  Display help'
    echo
}

function build_image() {
    local image=$1
    local exitval start elapsed
    printf '%b>>>>>>>>>>>>>>>> BUILDING IMAGE >>%b %b%s %b[timeout: %s]%b\n' \
	   "${BMGN}${BLD}${wht}" "$DEF" "${cyn}${BLD}" "$image" "${DEF}${DIM}" "$TIMEOUT" "$DEF"
    if [ $DRYRUN -eq 0 ]; then
	start=$SECONDS
	timeout "$TIMEOUT" "${BUILD_PATH}/${image}"
	exitval=$?
	elapsed=$(duration $((SECONDS - start)))
	if [ $exitval -eq 0 ]; then
	    printf '[%bSUCCESS%b] Build completed in %s: %b%s%b\n' \
		   "${grn}${BLD}" "$DEF" "$elapsed" "$BLD" "$image" "$DEF"
	    built_images+=("$image")
        elif [ $exitval -eq 124 ]; then
	    printf '[%bERROR%b] TIMEOUT: Build timed out after %s: %b%s%b\n' \
		   "${RED}${BLD}" "$DEF" "$TIMEOUT" "$BLD" "$image" "$DEF" >&2
	    jq -nc '{"result": "failed"}' >> "${LOG_PATH}/${image}-report.jsonl"
	    failed_images+=("$image")
	else
	    printf '[%bERROR%b] Build failed after %s (exit %s): %b%s%b\n' \
		   "${RED}${BLD}" "$DEF" "$elapsed" "$exitval" "$BLD" "$image" "$DEF" >&2
	    jq -nc '{"result": "failed"}' >> "${LOG_PATH}/${image}-report.jsonl"
	    failed_images+=("$image")
	fi
    else
	printf '%b(DRY-RUN)%b %btimeout %s %s/%s%b\n' \
	       "$GRN" "$DEF" "$DIM" "$TIMEOUT" "$BUILD_PATH" "$image" "$DEF"
	built_images+=("$image")
    fi
    echo
}

#---------------------------------------------------------------------
# Find images
#---------------------------------------------------------------------

if [ ! -d "$BUILD_PATH" ]; then
    printf 'No build scripts directory: %s\n' "$BUILD_PATH" >&2
    exit 1
fi

# A glob rather than $(ls): a build script whose name contains a space used to
# be split into two images that do not exist
for script_path in "$BUILD_PATH"/*; do
    [ -f "$script_path" ] || continue
    script=${script_path##*/}
    # A windows image installs two scripts: winsrv_<version>_wrapper, which is
    # the entry point, and winsrv_<version>, which the wrapper calls. The
    # second is not an image of its own, and running it directly starts a
    # build on the windows build host outside its schedule, so it is not
    # something anything here should ever pick up
    if [[ $script =~ ^winsrv_ ]] && [[ ! $script =~ _wrapper$ ]]; then
        continue
    fi
    IMAGE_CATEGORY[$script]=$(categorise "$script")
    ALL_IMAGES+=("$script")
done

#---------------------------------------------------------------------
# Options
#---------------------------------------------------------------------

# Display usage and exit with error if no options given
if [ $# -eq 0 ]; then
    usage >&2
    exit 1
fi

while getopts "SBGWlnhi:t:" arg; do
    case $arg in
	S|B|G|W)
	    SELECT_ALL[${OPTION_CATEGORY[$arg]}]=1
	    ;;
	i)
	    requested_images+=("$OPTARG")
	    SELECTED+=("$OPTARG")
	    ;;
	t)
	    # timeout(1) takes a number with an optional s/m/h/d suffix. Catch
	    # a bad one now rather than once per build
	    if ! [[ $OPTARG =~ ^[0-9]+([.][0-9]+)?[smhd]?$ ]]; then
		printf 'Invalid timeout: %s. See timeout(1)\n' "$OPTARG" >&2
		exit 1
	    fi
	    TIMEOUT=$OPTARG
	    ;;
	l)
	    LIST=1
	    ;;
	n)
	    DRYRUN=1
	    ;;
	h)
	    usage
	    exit 0
	    ;;
	*)
	    # An unknown option is an error, so that a typo in a cron entry or
	    # a unit file does not look like a successful run
	    usage >&2
	    exit 1
	    ;;
    esac
done

# Display all images and exit
if [ $LIST -eq 1 ]; then
    for cat in "${CATEGORIES[@]}"; do
	printf '%s:\n' "${CATEGORY_LABEL[$cat]}"
	for image in "${ALL_IMAGES[@]}"; do
	    if [ "${IMAGE_CATEGORY[$image]}" = "$cat" ]; then
		printf '  %s\n' "$image"
	    fi
	done
    done
    exit 0
fi

# Check every -i before building anything. A typo used to run a path that does
# not exist, report it as a failed build, and leave a report file behind for an
# image nobody has
unknown_images=()
for image in "${requested_images[@]}"; do
    if [ -z "${IMAGE_CATEGORY[$image]:-}" ]; then
	unknown_images+=("$image")
    fi
done
if [ ${#unknown_images[@]} -gt 0 ]; then
    printf 'No such image: %s\n' "${unknown_images[@]}" >&2
    printf "Run '%s -l' for the images that exist\n" "$0" >&2
    exit 1
fi

# -S, -B, -G and -W replace any -i for that category
for cat in "${CATEGORIES[@]}"; do
    [ -n "${SELECT_ALL[$cat]:-}" ] || continue
    keep=()
    for image in "${SELECTED[@]}"; do
	if [ "${IMAGE_CATEGORY[$image]}" != "$cat" ]; then
	    keep+=("$image")
	fi
    done
    for image in "${ALL_IMAGES[@]}"; do
	if [ "${IMAGE_CATEGORY[$image]}" = "$cat" ]; then
	    keep+=("$image")
	fi
    done
    SELECTED=("${keep[@]}")
done

#---------------------------------------------------------------------
# MAIN
#---------------------------------------------------------------------

# One run at a time. These builds share a project, and two runs would compete
# for the temporary security groups and keypairs. Taken after -l and -h so
# that looking at the list never blocks
if ! exec 9>"$LOCK_FILE"; then
    printf 'Cannot open lock file: %s\n' "$LOCK_FILE" >&2
    exit 1
fi
if ! flock -n 9; then
    printf 'Another run is already in progress (%s)\n' "$LOCK_FILE" >&2
    exit 1
fi

export IMAGEBUILDER_REPORT=true

run_start=$SECONDS

for cat in "${CATEGORIES[@]}"; do
    batch=()
    for image in "${SELECTED[@]}"; do
	if [ "${IMAGE_CATEGORY[$image]}" = "$cat" ]; then
	    batch+=("$image")
	fi
    done
    [ ${#batch[@]} -gt 0 ] || continue

    export IB_TEMPLATE_DIR="${CATEGORY_TEMPLATE[$cat]}"
    for img in "${batch[@]}"; do
	if [ "$cat" = win ] && [ $WIN_PLACEHOLDER -eq 1 ]; then
	    # Do NOT build these if cron failed.
	    export PLACEHOLDER=true
	    echo "Do NOT build $img! Poke Tor if cron job failed"
	    skipped_images+=("$img")
	else
	    build_image "$img"
	fi
    done
done

#---------------------------------------------------------------------
# Summary
#---------------------------------------------------------------------

printf '%b%s%b %d built, %d failed, %d skipped in %s\n' \
       "$BLD" 'Summary:' "$DEF" \
       "${#built_images[@]}" "${#failed_images[@]}" "${#skipped_images[@]}" \
       "$(duration $((SECONDS - run_start)))"

if [ ${#skipped_images[@]} -gt 0 ]; then
    printf '  %bskipped:%b %s\n' "$YLW" "$DEF" "${skipped_images[*]}"
fi

# Report what failed and exit non-zero, so that cron, a systemd unit or a
# monitoring check can tell a bad run from a good one
if [ ${#failed_images[@]} -gt 0 ]; then
    printf '  %bfailed:%b %s\n' "${RED}${BLD}" "$DEF" "${failed_images[*]}" >&2
    exit 1
fi

exit 0
