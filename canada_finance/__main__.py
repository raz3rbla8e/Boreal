import os

from canada_finance import create_app

app = create_app()
port = int(os.environ.get("PORT", 5000))
app.run(debug=False, host="0.0.0.0", port=port)
