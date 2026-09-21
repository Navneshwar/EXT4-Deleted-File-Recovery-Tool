#!/usr/bin/env bash
# Safe Kali demonstration: create a loop-backed EXT4 image, delete evidence,
# acquire compressed E01, then examine and extract it read-only.
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ACQUIRER="$SCRIPT_DIR/acquire_e01.sh"; WORKDIR=${1:-"$SCRIPT_DIR/ext4-e01-demo-output"}; IMAGE_SIZE=${IMAGE_SIZE:-1G}
die() { echo "ERROR: $*" >&2; exit 1; }; note() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
[[ $EUID -eq 0 ]] || die "Run with sudo."; [[ -x "$ACQUIRER" ]] || die "Run chmod +x *.sh first."
for tool in truncate losetup mkfs.ext4 mount umount ewfmount fsstat fls tsk_recover sha256sum; do command -v "$tool" >/dev/null || die "Missing $tool. On Kali install: apt install ewf-tools sleuthkit e2fsprogs"; done
mkdir -p "$WORKDIR"; WORKDIR=$(realpath "$WORKDIR"); LOOP_DEVICE=''; MOUNT_DIR="$WORKDIR/mounted-ext4"; EWF_MOUNT="$WORKDIR/ewf-mounted"
cleanup() { set +e; mountpoint -q "$MOUNT_DIR" && umount "$MOUNT_DIR"; mountpoint -q "$EWF_MOUNT" && umount "$EWF_MOUNT"; [[ -n "$LOOP_DEVICE" ]] && losetup -d "$LOOP_DEVICE"; }; trap cleanup EXIT
note "Creating disposable $IMAGE_SIZE EXT4 source inside $WORKDIR. No physical disk is written."
DEMO_RAW="$WORKDIR/demo-ext4-source.img"; truncate -s "$IMAGE_SIZE" "$DEMO_RAW"; LOOP_DEVICE=$(losetup --find --show "$DEMO_RAW"); [[ $(lsblk -dnro TYPE "$LOOP_DEVICE") == loop ]] || die "Expected a loop device."
mkfs.ext4 -F -q -L EXT4_DEMO "$LOOP_DEVICE"; mkdir -p "$MOUNT_DIR"; mount -o rw,nosuid,nodev "$LOOP_DEVICE" "$MOUNT_DIR"
mkdir -p "$MOUNT_DIR/Users/alice/Documents" "$MOUNT_DIR/Users/alice/.config"
printf 'Project: EXT4 recovery demonstration\nStatus: confidential draft\n' > "$MOUNT_DIR/Users/alice/Documents/case-notes.txt"
printf 'name,email,role\nAlice,alice@example.test,analyst\n' > "$MOUNT_DIR/Users/alice/Documents/contacts.csv"
printf '{"token":"DEMO-ONLY-NOT-A-REAL-SECRET"}\n' > "$MOUNT_DIR/Users/alice/.config/app-settings.json"
printf '%%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%%%EOF\n' > "$MOUNT_DIR/Users/alice/Documents/deleted-report.pdf"
dd if=/dev/urandom of="$MOUNT_DIR/Users/alice/Documents/evidence-payload.bin" bs=1M count=8 status=none
find "$MOUNT_DIR" -type f -print0 | sort -z | xargs -0 sha256sum > "$WORKDIR/original-file-hashes.sha256"; sync
rm -f "$MOUNT_DIR/Users/alice/Documents/case-notes.txt" "$MOUNT_DIR/Users/alice/Documents/contacts.csv" "$MOUNT_DIR/Users/alice/.config/app-settings.json" "$MOUNT_DIR/Users/alice/Documents/deleted-report.pdf" "$MOUNT_DIR/Users/alice/Documents/evidence-payload.bin"; sync; umount "$MOUNT_DIR"
printf 'ACQUIRE\n' | ACQUIRE_ALLOW_LOOP_DEMO=1 "$ACQUIRER" "$LOOP_DEVICE" "$WORKDIR/e01" "EXT4-DEMO" "Deleted-file recovery training image"
E01=$(find "$WORKDIR/e01" -maxdepth 1 -type f -iname '*.E01' -print -quit); [[ -n "$E01" ]] || die "No E01 produced."
mkdir -p "$EWF_MOUNT"; ewfmount "$E01" "$EWF_MOUNT"; RAW_STREAM="$EWF_MOUNT/ewf1"; [[ -e "$RAW_STREAM" ]] || die "ewfmount did not expose ewf1."
fsstat "$RAW_STREAM" | tee "$WORKDIR/fsstat.txt"; fls -r -d "$RAW_STREAM" | tee "$WORKDIR/deleted-file-listing.txt"
mkdir -p "$WORKDIR/recovered-unallocated"; tsk_recover -e "$RAW_STREAM" "$WORKDIR/recovered-unallocated" | tee "$WORKDIR/tsk-recover.log"
find "$WORKDIR/recovered-unallocated" -type f -print0 | sort -z | xargs -0 -r sha256sum > "$WORKDIR/recovered-file-hashes.sha256"
note "Complete. Compare original-file-hashes.sha256 and recovered-file-hashes.sha256."
