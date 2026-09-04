# Kill existing backend and frontend
Stop-Process -Id 648 -Force -ErrorAction SilentlyContinue
Stop-Process -Id 38132 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start the site
Set-Location 'H:\programz\knowledge\GSA-kb'
& '.\start-ui.bat'
