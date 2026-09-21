#!/usr/bin/env bash
# Read a whole device into segmented, deflate-compressed EnCase E01 evidence.
# Run from trusted Kali media as root; never mount the source.
set -Eeuo pipefail
IFS=$'\n\t'

usage() {
  cat <<'EOF'
Usage: sudo ./acquire_e01.sh SOURCE_DEVICE DESTINATION_DIRECTORY CASE_ID [DESCRIPTION]

Creates a compressed E01 image, verifies it with ewfverify, and records hashes.
Use a whole device (/dev/sdb, /dev/nvme0n1), not a partition. Compression
reduces zero-filled/repetitive data but cannot promise a particular final size.
EOF
}
die() { echo "ERROR: $*" >&2; exit 1; }
note() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

[[ $EUID -eq 0 && $# -ge 3 && $# -le 4 ]] || { usage; exit 2; }
SOURCE=$1; DEST=$2; CASE_ID=$3; DESCRIPTION=${4:-"Physical acquisition"}
for tool in ewfacquire ewfverify sha256sum blockdev lsblk findmnt df; do command -v "$tool" >/dev/null || die "Missing $tool"; done
[[ -b "$SOURCE" ]] || die "$SOURCE is not a block device."
SOURCE_TYPE=$(lsblk -dnro TYPE "$SOURCE")
if [[ "$SOURCE_TYPE" != disk ]]; then
  [[ "$SOURCE_TYPE" == loop && "${ACQUIRE_ALLOW_LOOP_DEMO:-0}" == 1 ]] || die "Source must be a whole disk; loop devices require ACQUIRE_ALLOW_LOOP_DEMO=1 for the demo only."
fi
mkdir -p "$DEST"; [[ -w "$DEST" ]] || die "Destination is not writable."
SOURCE_NAME=$(lsblk -dnro NAME "$SOURCE")
DEST_BACKING=$(findmnt -n -o SOURCE --target "$DEST" 2>/dev/null || true)
if [[ -n "$DEST_BACKING" && -b "$DEST_BACKING" ]] && lsblk -s -n -o NAME "$DEST_BACKING" | awk '{print $1}' | grep -Fxq "$SOURCE_NAME"; then die "Destination is on the source device."; fi

SAFE_CASE=$(printf '%s' "$CASE_ID" | tr -cs 'A-Za-z0-9._-' '_')
STAMP=$(date -u +'%Y%m%dT%H%M%SZ'); BASE="${SAFE_CASE}_${STAMP}"; TARGET="$DEST/$BASE"; LOG="$DEST/${BASE}_acquisition.log"
SOURCE_BYTES=$(blockdev --getsize64 "$SOURCE"); FREE_BYTES=$(df -PB1 "$DEST" | awk 'NR==2 {print $4}')
[[ $FREE_BYTES -ge $((SOURCE_BYTES / 20)) ]] || die "Destination has less than 5% of the source capacity free."
{ note "Source: $SOURCE"; note "Source capacity: $SOURCE_BYTES bytes"; note "Case: $CASE_ID"; note "Description: $DESCRIPTION"; note "Compression: deflate:best, E01 2 GiB segments"; lsblk -o NAME,SIZE,MODEL,SERIAL,RO,TYPE,MOUNTPOINTS "$SOURCE"; } | tee "$LOG"
read -r -p "Confirm hardware write blocking and type ACQUIRE to start: " CONFIRM
[[ "$CONFIRM" == ACQUIRE ]] || die "Acquisition cancelled."
ewfacquire -u -f encase6 -c deflate:best -S 2G -C "$CASE_ID" -d "$DESCRIPTION" -e "$(id -un)" -N "$BASE" -t "$TARGET" "$SOURCE" 2>&1 | tee -a "$LOG"
ewfverify "${TARGET}.E01" 2>&1 | tee -a "$LOG"
find "$DEST" -maxdepth 1 -type f -iname "${BASE}.E*" -print0 | sort -z | xargs -0 sha256sum | tee "$DEST/${BASE}_segments.sha256" | tee -a "$LOG"
note "Complete. Preserve E01 segments, verification output, SHA-256 file, and log together." | tee -a "$LOG"
