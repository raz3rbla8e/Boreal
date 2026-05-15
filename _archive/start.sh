#!/usr/bin/env bash
set -e

echo ""
echo "  =========================================="
echo "   Boreal - Personal Finance Dashboard"
echo "  =========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "  [ERROR] Python 3 is not installed."
    echo ""
    echo "  Install it with:"
    echo "    macOS:  brew install python3"
    echo "    Ubuntu: sudo apt install python3 python3-pip"
    echo ""
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".installed" ]; then
    echo "  Installing dependencies (first time only)..."
    pip3 install -r requirements.txt > /dev/null 2>&1
    touch .installed
    echo "  Done!"
    echo ""
fi

echo "  Starting Boreal..."
echo "  Open your browser to: http://localhost:5000"
echo "  Press Ctrl+C to stop."
echo ""

# Open browser (works on macOS and Linux)
if command -v open &> /dev/null; then
    open http://localhost:5000 &
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5000 &
fi

python3 app.py
