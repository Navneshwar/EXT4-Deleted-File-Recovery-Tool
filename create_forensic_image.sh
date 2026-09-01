#!/bin/bash
#
# Forensic EXT4 Disk Image Creator
# Creates a read-only image for analysis with ext4recover
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root (sudo)"
    exit 1
fi

# Check for required tools
for cmd in dd sha256sum; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 1
    fi
done

echo "========================================="
echo "  Forensic EXT4 Disk Image Creator"
echo "========================================="
echo ""

# List available EXT4 partitions
log_info "Available EXT4 partitions:"
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT | grep ext4
echo ""

# Get source device
read -p "Enter the source device (e.g., /dev/sda1): " SOURCE

# Verify device exists
if [ ! -b "$SOURCE" ]; then
    log_error "Device $SOURCE does not exist or is not a block device"
    exit 1
fi

# Check if mounted
MOUNT_POINT=$(findmnt -n -o TARGET "$SOURCE" 2>/dev/null || echo "")
if [ -n "$MOUNT_POINT" ]; then
    log_warn "Device $SOURCE is mounted at: $MOUNT_POINT"
    log_warn "For best results, unmount it first or use read-only mode"
    read -p "Continue anyway? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Aborted. Please unmount the device and try again."
        exit 0
    fi
fi

# Get output filename
DEFAULT_OUTPUT="evidence_$(basename "$SOURCE").img"
read -p "Enter output filename [$DEFAULT_OUTPUT]: " OUTPUT
OUTPUT="${OUTPUT:-$DEFAULT_OUTPUT}"

# Check if output file exists
if [ -f "$OUTPUT" ]; then
    log_error "Output file $OUTPUT already exists"
    exit 1
fi

echo ""
log_info "Creating forensic image..."
log_info "Source: $SOURCE"
log_info "Output: $OUTPUT"
echo ""

# Get device size
SIZE=$(blockdev --getsize64 "$SOURCE")
log_info "Device size: $((SIZE / 1024 / 1024)) MB"

# Create the image
log_warn "This may take a while depending on the device size..."
dd if="$SOURCE" of="$OUTPUT" bs=4M status=progress conv=noerror,sync

# Calculate hash
echo ""
log_info "Calculating SHA256 hash..."
sha256sum "$OUTPUT" > "${OUTPUT}.sha256"
HASH=$(cat "${OUTPUT}.sha256")

# Get image info
IMAGE_SIZE=$(stat -c%s "$OUTPUT")

echo ""
echo "========================================="
echo "  Image Creation Complete"
echo "========================================="
echo ""
log_info "Image file: $OUTPUT"
log_info "Image size: $((IMAGE_SIZE / 1024 / 1024)) MB"
log_info "SHA256: $HASH"
echo ""
log_info "Hash saved to: ${OUTPUT}.sha256"
echo ""
log_info "Next steps:"
echo "  1. Copy the image to your analysis machine"
echo "  2. Run: ext4recover inspect $OUTPUT --output case"
echo "  3. Run: ext4recover scan $OUTPUT --output case"
echo "  4. Run: ext4recover recover $OUTPUT <inode> --output case"
echo ""

exit 0