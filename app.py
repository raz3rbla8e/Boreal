#!/usr/bin/env python3
"""
CanadaFinance - Personal Finance Dashboard for Canadians

Entry point: python app.py
Or install with: pip install .
Then run: canada-finance
"""

from canada_finance import create_app

app = create_app()

if __name__ == "__main__":
    print("\n🍁 CanadaFinance")
    print("   Open: http://localhost:5000")
    print("   Stop: Ctrl+C\n")
    app.run(debug=True, port=5000)
