#!/bin/bash
#
# Case Manager - List Available Backups
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/data/backups"

echo "Available backups in $BACKUP_DIR:"
echo "=================================="
echo ""

if [ -d "$BACKUP_DIR" ] && [ "$(ls -A "$BACKUP_DIR"/*.tar.gz 2>/dev/null)" ]; then
    for backup in "$BACKUP_DIR"/*.tar.gz; do
        filename=$(basename "$backup")
        size=$(du -h "$backup" | cut -f1)
        date=$(stat -c %y "$backup" 2>/dev/null || stat -f %Sm "$backup" 2>/dev/null)

        # Check for checksum
        checksum_file="${backup%.tar.gz}.sha256"
        if [ -f "$checksum_file" ]; then
            verified="[checksum available]"
        else
            verified=""
        fi

        echo "  $filename"
        echo "    Size: $size"
        echo "    Date: $date"
        echo "    $verified"
        echo ""
    done
else
    echo "  No backups found"
fi
