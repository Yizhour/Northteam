$env:ENABLE_SCHEDULER = "0"
Set-Location (Resolve-Path "$PSScriptRoot\..")
& "..\.venv\Scripts\python.exe" -c "from wsgi import app; app.run(host='127.0.0.1', port=8000, debug=False)"
