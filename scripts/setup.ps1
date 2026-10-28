$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

# Check prerequisites before installing large dependency sets.
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 24 with npm from https://nodejs.org/en/download, then retry Install.cmd.'
}
$nodeVersion = [version]((& node --version).Trim().TrimStart('v'))
if ($nodeVersion.Major -lt 24) { throw 'Node.js 24 or newer is required by this installer. Install it from https://nodejs.org/en/download.' }
$npmMajor = [int]((& npm --version).Split('.')[0])
if ($npmMajor -lt 10) { throw 'npm 10 or newer is required. Install Node.js 24 with its bundled npm.' }
$snippingTool = Get-AppxPackage -Name Microsoft.ScreenSketch | Select-Object -First 1
if (-not $snippingTool) { throw 'Install or update Windows Snipping Tool through Microsoft Store, then retry Install.cmd.' }

$installDir = Join-Path $env:LOCALAPPDATA 'Programs\Proxy Transcript'
$venvDir = Join-Path $installDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
New-Item -ItemType Directory -Path $installDir -Force | Out-Null

$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    'C:\Python312\python.exe',
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$basePython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $basePython -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $candidate = & py -3.12 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $candidate)) { $basePython = $candidate }
}
if (-not $basePython) { throw 'Python 3.12 was not found. Install Python 3.12 with the Windows py launcher, then retry.' }
# Windows PowerShell 5.1 strips embedded double quotes from native arguments,
# so inline Python passed with -c must not contain any.
$pythonVersion = & $basePython -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.12') { throw 'Python 3.12 is required for the locked OCR dependencies. Install it with the Windows py launcher.' }

$wasRunning = $false
try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8766/api/health' -UseBasicParsing -TimeoutSec 2
    $wasRunning = $response.StatusCode -eq 200
} catch { }
if ($wasRunning) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'data\processes.json'))) {
        throw 'Run update-companion.ps1 with -Root pointing to the current companion folder and -SourceRoot pointing to this release.'
    }
    & (Join-Path $PSScriptRoot 'update-companion.ps1') -SourceRoot $projectRoot -Root $projectRoot
    Write-Host 'The prepared update is active; capture stayed available during installation.'
    return
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $basePython -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
$environmentVersion = & $venvPython -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
if ($LASTEXITCODE -ne 0 -or $environmentVersion -ne '3.12') { throw 'The existing toolkit environment must use Python 3.12. See INSTALL.md for environment repair instructions.' }

& $venvPython -m pip install --disable-pip-version-check --timeout 120 --retries 8 -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

# The Python oneocr package expects the native OCR files from Windows Snipping
# Tool in the current user's profile. Without them capture starts but fails as
# soon as a game window appears, so verify them during setup.
$ocrSource = Join-Path $snippingTool.InstallLocation 'SnippingTool'
$ocrTarget = Join-Path $env:USERPROFILE '.config\oneocr'
New-Item -ItemType Directory -Path $ocrTarget -Force | Out-Null
foreach ($name in @('oneocr.dll', 'oneocr.onemodel', 'onnxruntime.dll')) {
    $source = Join-Path $ocrSource $name
    if (-not (Test-Path -LiteralPath $source)) { throw "Windows Snipping Tool OCR file is missing: $name" }
    Copy-Item -LiteralPath $source -Destination (Join-Path $ocrTarget $name) -Force
}
& $venvPython -c 'from oneocr import OcrEngine; OcrEngine()'
if ($LASTEXITCODE -ne 0) { throw 'Native OCR initialization failed.' }


& npm ci
if ($LASTEXITCODE -ne 0) { throw 'Locked frontend dependency installation failed.' }

$prebuilt = $false
$provenancePath = Join-Path $projectRoot 'PROVENANCE.json'
if ((Test-Path -LiteralPath $provenancePath) -and (Test-Path -LiteralPath (Join-Path $projectRoot 'dist\server\wrangler.json'))) {
    $provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
    $package = Get-Content -LiteralPath (Join-Path $projectRoot 'package.json') -Raw | ConvertFrom-Json
    $prebuilt = $provenance.version -eq $package.version
}
if ($prebuilt) { Write-Host 'Using the prebuilt frontend from this verified release.' }
else {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}

& (Join-Path $PSScriptRoot 'install-shortcuts.ps1')
if ($wasRunning) { & (Join-Path $PSScriptRoot 'start-companion.ps1') -NoBrowser }
Write-Host 'Proxy Transcript is ready. Launch it from Start or the taskbar.'
