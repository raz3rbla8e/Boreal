from canada_finance import create_app

app = create_app()
app.run(debug=False, port=5000)
