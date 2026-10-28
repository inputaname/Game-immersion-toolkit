param([switch]$VerifyBaseline)
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Installer fixtures require Windows; no Windows verification was performed.' }
$repository=Split-Path -Parent $PSScriptRoot
$clock=[Diagnostics.Stopwatch]::StartNew()
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('companion-setup-'+[guid]::NewGuid().ToString('N'))
$originalLocal=$env:LOCALAPPDATA
$originalProfile=$env:USERPROFILE
$originalLocation=Get-Location
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
try {
    # All native/dependency boundaries are local fakes. This exercises the real
    # installer control flow without installing OCR or touching a user profile.
    $env:LOCALAPPDATA=Join-Path $temporary 'profile\local'
    $env:USERPROFILE=Join-Path $temporary 'profile'
    $base=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    $venv=Join-Path $env:LOCALAPPDATA 'Programs\Proxy Transcript\venv\Scripts\python.exe'
    $snipping=Join-Path $temporary 'snipping\SnippingTool'
    New-Item -ItemType Directory -Path (Split-Path $base),(Split-Path $venv),$snipping -Force | Out-Null
    Add-Type -OutputAssembly $base -OutputType ConsoleApplication -TypeDefinition @'
using System;
public class SetupPythonFixture {
    public static int Main(string[] args) {
        // Windows PowerShell 5.1 would strip embedded quotes and break this code.
        if (args.Length == 2 && args[0] == "-c" && args[1].Contains("sys.version_info")) { if (args[1].IndexOf('"') >= 0) return 1; Console.WriteLine("3.12"); }
        return 0;
    }
}
'@
    Copy-Item $base $venv
    foreach($name in @('oneocr.dll','oneocr.onemodel','onnxruntime.dll')){[IO.File]::WriteAllText((Join-Path $snipping $name),'synthetic native boundary')}
    function Get-AppxPackage { param([string]$Name); return @{InstallLocation=(Split-Path $snipping)} }
    function Invoke-WebRequest { throw 'No existing companion in this controlled installer fixture.' }
    function node {
        if ($args.Count -eq 1 -and $args[0] -eq '--version') { $global:LASTEXITCODE=0; return 'v24.0.0' }
        throw 'DIRECT_VINEXT_BYPASSED_ASSET_PREPARATION'
    }
    # Functions called by setup.ps1 see that file's $script: scope. Mutate this
    # shared object so the fixture retains both its scenario and call count.
    $fixtureState=@{scenario='';buildCalls=0}
    function npm {
        if ($args[0] -eq '--version') { $global:LASTEXITCODE=0; return '10.0.0' }
        if ($args[0] -eq 'ci') { $global:LASTEXITCODE=0; return }
        if (($args -join ' ') -ne 'run build') { throw 'Unexpected npm command in installer fixture.' }
        $fixtureState.buildCalls++
        if ($fixtureState.scenario -eq 'asset-failure') { $global:LASTEXITCODE=42; return }
        New-Item -ItemType Directory -Path 'dist\server','public\mobile-capture' -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path (Get-Location) 'dist\server\wrangler.json'),'{}')
        [IO.File]::WriteAllText((Join-Path (Get-Location) 'public\mobile-capture\companion.js'),'generated fixture')
        $global:LASTEXITCODE=0
    }
    $scenarios=@('clean-source','prebuilt','mismatched-provenance','asset-failure')
    if($VerifyBaseline){$scenarios=@('baseline')+$scenarios}
    foreach($scenario in $scenarios){
        $fixtureState.scenario=$scenario
        $fixtureState.buildCalls=0
        $root=Join-Path $temporary $scenario
        $scripts=Join-Path $root 'scripts'
        New-Item -ItemType Directory -Path $scripts -Force | Out-Null
        if($scenario -eq 'baseline'){
            $source=& git -C $repository show '7ae7e6991a6cc848334109720fb9ef608bca6999:scripts/setup.ps1'
            if($LASTEXITCODE -ne 0){throw 'Cannot read baseline setup script.'}
            [IO.File]::WriteAllText((Join-Path $scripts 'setup.ps1'),($source -join "`n"))
        }else{Copy-Item (Join-Path $repository 'scripts\setup.ps1') (Join-Path $scripts 'setup.ps1')}
        [IO.File]::WriteAllText((Join-Path $scripts 'install-shortcuts.ps1'),"[IO.File]::WriteAllText((Join-Path (Split-Path -Parent `$PSScriptRoot) 'shortcuts-created'),'fixture')")
        [IO.File]::WriteAllText((Join-Path $root 'package.json'),'{"name":"game-immersion-toolkit","version":"0.0.1"}')
        if($scenario -in @('prebuilt','mismatched-provenance')){
            New-Item -ItemType Directory -Path (Join-Path $root 'dist\server') -Force | Out-Null
            [IO.File]::WriteAllText((Join-Path $root 'dist\server\wrangler.json'),'preserved prebuilt fixture')
            $version=if($scenario -eq 'prebuilt'){'0.0.1'}else{'0.0.0'}
            @{version=$version}|ConvertTo-Json|Set-Content (Join-Path $root 'PROVENANCE.json')
        }
        $failed=$null;$output=''
        try{$output=& (Join-Path $scripts 'setup.ps1') 6>&1|Out-String}catch{$failed=$_}
        $diagnostic=(@{scenario=$fixtureState.scenario;buildCalls=$fixtureState.buildCalls;
            assetPresent=(Test-Path (Join-Path $root 'public\mobile-capture\companion.js'))}|ConvertTo-Json -Compress)
        if($scenario -eq 'baseline'){
            if(-not $failed -or $failed.Exception.Message -notmatch 'DIRECT_VINEXT_BYPASSED_ASSET_PREPARATION'){throw 'Baseline did not reproduce the canonical build regression.'}
            Write-Host 'Baseline regression reproduced: setup calls vinext directly and bypasses generated assets.'
            continue
        }
        if($scenario -eq 'asset-failure'){
            if(-not $failed -or $failed.Exception.Message -notmatch 'Frontend build failed' -or $fixtureState.buildCalls -ne 1){throw ('Asset preparation failure did not abort its canonical build. '+$diagnostic)}
            if((Test-Path (Join-Path $root 'shortcuts-created')) -or $output -match 'Proxy Transcript is ready'){throw 'Setup reported success after asset preparation failed.'}
        }else{
            if($failed){throw $failed}
            if($output -notmatch 'Proxy Transcript is ready' -or -not (Test-Path (Join-Path $root 'shortcuts-created'))){throw 'Successful installer did not finish.'}
            if($scenario -eq 'prebuilt'){
                if($fixtureState.buildCalls -ne 0 -or (Get-Content (Join-Path $root 'dist\server\wrangler.json')) -ne 'preserved prebuilt fixture'){throw ('Valid prebuilt release was rebuilt. '+$diagnostic)}
            }elseif($fixtureState.buildCalls -ne 1 -or -not (Test-Path (Join-Path $root 'public\mobile-capture\companion.js'))){throw ('Source or mismatched provenance did not use the canonical build. '+$diagnostic)}
        }
        Write-Host ('Windows installer fixture passed: '+$scenario)
    }
    Write-Host 'Native Snipping Tool OCR/capture remains OPEN: these fixtures mock native initialization and do not verify hardware capture.'
}finally{
    Set-Location $originalLocation
    $env:LOCALAPPDATA=$originalLocal
    $env:USERPROFILE=$originalProfile
    Remove-Item -LiteralPath $temporary -Recurse -Force
    $clock.Stop()
    $evidence=Join-Path $repository 'output\checks'
    New-Item -ItemType Directory -Path $evidence -Force | Out-Null
    @{check='windows-installer-boundaries';elapsedMs=$clock.ElapsedMilliseconds;nativeOcr='OPEN: mocked native initialization; hardware capture unverified'}|ConvertTo-Json|Set-Content (Join-Path $evidence 'windows-setup.json')
}
