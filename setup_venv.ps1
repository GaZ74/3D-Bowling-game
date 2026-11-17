$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Environment ready. Start the game with: .\.venv\Scripts\python.exe main.py"
