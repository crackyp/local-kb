param(
    [string]$Model = "phi4-mini"
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[local-kb] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[local-kb] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[local-kb] $msg" -ForegroundColor Yellow }

function Have-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    if (Have-Command "py") { return "py" }
    if (Have-Command "python") { return "python" }
    throw "Python not found. Install Python 3.10+ and rerun."
}

function Ensure-Ollama {
    if (Have-Command "ollama") { return }

    Write-Warn "Ollama not found. Trying winget install..."
    if (Have-Command "winget") {
        try {
            winget install --id Ollama.Ollama -e --source winget --accept-package-agreements --accept-source-agreements
        }
        catch {
            throw "Failed to install Ollama via winget. Install manually from https://ollama.com/download/windows"
        }
    }
    else {
        throw "winget not found. Install Ollama manually from https://ollama.com/download/windows"
    }

    if (-not (Have-Command "ollama")) {
        throw "Ollama still not available in PATH. Restart terminal and rerun this script."
    }
}

function Start-Ollama {
    # Preferred: Windows service
    try {
        $svc = Get-Service -Name "ollama" -ErrorAction Stop
        if ($svc.Status -ne "Running") {
            Start-Service -Name "ollama"
        }
        Write-Info "Ollama service is running."
        return
    }
    catch {
        # fallback below
    }

    Write-Warn "Ollama service not found. Starting 'ollama serve' in background..."
    $null = Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve"
    Start-Sleep -Seconds 2
}

Write-Info "Setting up Local KB for Windows"
$py = Get-PythonCommand
Write-Info "Using Python command: $py"

Ensure-Ollama
Start-Ollama

Write-Info "Installing Python dependencies"
if ($py -eq "py") {
    py -m pip install -r requirements.txt
} else {
    python -m pip install -r requirements.txt
}

Write-Info "Pulling model: $Model"
ollama pull $Model

Write-Ok "Setup complete"
Write-Host ""
Write-Host "Next commands:" -ForegroundColor White
Write-Host "  python start-ui.py" -ForegroundColor White
Write-Host "  Then open http://localhost:3000" -ForegroundColor White
