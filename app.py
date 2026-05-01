#!/usr/bin/env python3
"""
Boreal - Personal Finance Dashboard for Canadians

Entry point: python app.py
Or install with: pip install .
Then run: canada-finance
"""

import os

from canada_finance import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n� Boreal")
    print(f"   Open: http://localhost:{port}")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, host="0.0.0.0", port=port)
