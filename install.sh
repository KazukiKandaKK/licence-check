#!/bin/bash

# License Check Tool Installer
# This script installs the check-license command globally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/bin"
SCRIPT_NAME="check-license"

echo "🔧 Installing License Check Tool..."

# Check if we have write permissions to /usr/local/bin
if [ ! -w "$INSTALL_DIR" ]; then
    echo "⚠️  Need sudo permissions to install to $INSTALL_DIR"
    echo "Please enter your password:"
    sudo cp "$SCRIPT_DIR/$SCRIPT_NAME" "$INSTALL_DIR/"
    sudo chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
else
    cp "$SCRIPT_DIR/$SCRIPT_NAME" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
fi

# Verify installation
if command -v "$SCRIPT_NAME" >/dev/null 2>&1; then
    echo "✅ Successfully installed $SCRIPT_NAME!"
    echo "📍 Installed to: $INSTALL_DIR/$SCRIPT_NAME"
    echo ""
    echo "Usage examples:"
    echo "  check-license                    # Scan current directory"
    echo "  check-license --summary-only     # Show only summary"
    echo "  check-license --verbose          # Show detailed issues"
    echo "  check-license --help             # Show all options"
    echo ""
    echo "🎉 You can now use 'check-license' from any directory!"
else
    echo "❌ Installation failed. Please check permissions and try again."
    exit 1
fi