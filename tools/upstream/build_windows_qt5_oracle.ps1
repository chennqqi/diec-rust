[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDir,

    [Parameter(Mandatory = $true)]
    [string]$QtDir,

    [Parameter(Mandatory = $true)]
    [string]$VsDevCmd,

    [Parameter(Mandatory = $true)]
    [string]$BuildDir,

    [Parameter(Mandatory = $true)]
    [string]$JomPath,

    [ValidateRange(1, 64)]
    [int]$Jobs = 4,

    [string]$OutputJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedCommit = "74eaf505c250ab47e709024e9dc41657cd8f2254"
$ExpectedRulesCommit = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
$ExpectedSubmoduleCount = 58
$ExpectedQtVersion = "5.15.2"
$ExpectedQmakeSha256 =
    "e873ad3a689a0628c3037a6440221dcd2e426395edf14ffa6379612dede26d36"
$ExpectedQtCoreSha256 =
    "8d2ff4ce9096ddccc4f4cd62c2e41fc854cfd1b0d6e8d296645a7f5fd4ae565a"
$ExpectedQtScriptSha256 =
    "0b58e5e79df13110a8258f14d7b3658d1dd0c8dddc337a164b89d4ac12a0638f"

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description does not exist: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).
        Hash.ToLowerInvariant()
}

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Actual,

        [Parameter(Mandatory = $true)]
        [string]$Expected,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if ($Actual -cne $Expected) {
        throw "$Description mismatch: expected $Expected, got $Actual"
    }
}

if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
        [System.Runtime.InteropServices.OSPlatform]::Windows
    )) {
    throw "This oracle builder only supports Windows."
}

$SourceDir = Resolve-ExistingPath $SourceDir "source directory"
$QtDir = Resolve-ExistingPath $QtDir "Qt directory"
$VsDevCmd = Resolve-ExistingPath $VsDevCmd "Visual Studio developer command"
$JomPath = Resolve-ExistingPath $JomPath "jom executable"

if (-not (Test-Path -LiteralPath $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir | Out-Null
}
$BuildDir = (Resolve-Path -LiteralPath $BuildDir).Path

$QmakePath = Resolve-ExistingPath(
    (Join-Path $QtDir "bin\qmake.exe")
) "qmake executable"
$QtCorePath = Resolve-ExistingPath(
    (Join-Path $QtDir "bin\Qt5Core.dll")
) "Qt5Core runtime"
$QtScriptPath = Resolve-ExistingPath(
    (Join-Path $QtDir "bin\Qt5Script.dll")
) "Qt5Script runtime"

$RootCommit = (& git -C $SourceDir rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read DIE-engine HEAD."
}
Assert-Equal $RootCommit $ExpectedCommit "DIE-engine commit"

$RootStatus = @(
    & git -C $SourceDir status --porcelain=v1 --untracked-files=no `
        --ignore-submodules=dirty
)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect DIE-engine status."
}
if ($RootStatus.Count -ne 0) {
    throw "DIE-engine has tracked changes: $($RootStatus -join '; ')"
}

$SubmoduleStatus = @(& git -C $SourceDir submodule status --recursive)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect recursive submodule status."
}
if ($SubmoduleStatus.Count -ne $ExpectedSubmoduleCount) {
    throw (
        "Expected $ExpectedSubmoduleCount recursive submodules, got " +
        "$($SubmoduleStatus.Count)."
    )
}
$InvalidSubmodules = @(
    $SubmoduleStatus | Where-Object {
        $_.Length -eq 0 -or $_[0] -ne " "
    }
)
if ($InvalidSubmodules.Count -ne 0) {
    throw "Submodule identity is not clean: $($InvalidSubmodules -join '; ')"
}

$SubmoduleTrackedStatus = @(
    & git -C $SourceDir submodule foreach --quiet --recursive `
        "git status --porcelain=v1 --untracked-files=no"
)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect tracked changes inside submodules."
}
if ($SubmoduleTrackedStatus.Count -ne 0) {
    throw (
        "Submodules have tracked changes: " +
        "$($SubmoduleTrackedStatus -join '; ')"
    )
}

$RulesDir = Resolve-ExistingPath(
    (Join-Path $SourceDir "Detect-It-Easy")
) "Detect-It-Easy submodule"
$RulesCommit = (& git -C $RulesDir rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read Detect-It-Easy HEAD."
}
Assert-Equal $RulesCommit $ExpectedRulesCommit "Detect-It-Easy commit"

$QtVersion = (& $QmakePath -query QT_VERSION).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to query Qt version."
}
Assert-Equal $QtVersion $ExpectedQtVersion "Qt version"

$QmakeSpec = (& $QmakePath -query QMAKE_SPEC).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to query qmake spec."
}
Assert-Equal $QmakeSpec "win32-msvc" "qmake spec"

$QmakeSha256 = Get-Sha256 $QmakePath
$QtCoreSha256 = Get-Sha256 $QtCorePath
$QtScriptSha256 = Get-Sha256 $QtScriptPath
Assert-Equal $QmakeSha256 $ExpectedQmakeSha256 "qmake SHA-256"
Assert-Equal $QtCoreSha256 $ExpectedQtCoreSha256 "Qt5Core SHA-256"
Assert-Equal $QtScriptSha256 $ExpectedQtScriptSha256 "Qt5Script SHA-256"

$DieProject = Resolve-ExistingPath(
    (Join-Path $SourceDir "die_source.pro")
) "top-level qmake project"
$BuildCommand = @(
    "call `"$VsDevCmd`"",
    "cd /d `"$BuildDir`"",
    "`"$QmakePath`" `"$DieProject`" -spec win32-msvc `"CONFIG+=release`"",
    "`"$JomPath`" /J $Jobs sub-build_libs-release",
    "`"$JomPath`" /J $Jobs sub-console_source-release"
) -join " && "

$Timer = [System.Diagnostics.Stopwatch]::StartNew()
& $env:ComSpec /d /c $BuildCommand
$BuildExitCode = $LASTEXITCODE
$Timer.Stop()
if ($BuildExitCode -ne 0) {
    throw "Windows Qt5 oracle build failed with exit code $BuildExitCode."
}

$ArtifactPath = Resolve-ExistingPath(
    (Join-Path $SourceDir "build\release\diec.exe")
) "diec CLI artifact"
$RequiredSimdLibraries = @(
    "xsimd-win-x86_64.lib",
    "xsimd_sse2-win-x86_64.lib",
    "xsimd_avx2-win-x86_64.lib"
)
foreach ($LibraryName in $RequiredSimdLibraries) {
    Resolve-ExistingPath(
        (Join-Path $SourceDir "Formats\xsimd\libs\$LibraryName")
    ) "xsimd library" | Out-Null
}

$SavedPath = $env:Path
try {
    $env:Path = "$(Join-Path $QtDir 'bin');$SavedPath"
    $VersionOutput = @(& $ArtifactPath --version 2>&1)
    $VersionExitCode = $LASTEXITCODE
}
finally {
    $env:Path = $SavedPath
}
if ($VersionExitCode -ne 0) {
    throw "diec --version failed with exit code $VersionExitCode."
}
Assert-Equal (($VersionOutput -join "`n").Trim()) "die 4.0.0" `
    "diec version output"

$Result = [ordered]@{
    schema_version = 1
    baseline = [ordered]@{
        repository = "https://github.com/horsicq/DIE-engine"
        commit = $RootCommit
        recursive_submodule_count = $SubmoduleStatus.Count
        rules_commit = $RulesCommit
    }
    build = [ordered]@{
        system = "qmake"
        configuration = "release"
        generator = "jom"
        jobs = $Jobs
        elapsed_milliseconds = $Timer.ElapsedMilliseconds
        targets = @(
            "sub-build_libs-release",
            "sub-console_source-release"
        )
    }
    qt = [ordered]@{
        version = $QtVersion
        qmake_spec = $QmakeSpec
        qmake_sha256 = $QmakeSha256
        qt5core_sha256 = $QtCoreSha256
        qt5script_sha256 = $QtScriptSha256
    }
    artifact = [ordered]@{
        path = $ArtifactPath
        size = (Get-Item -LiteralPath $ArtifactPath).Length
        sha256 = Get-Sha256 $ArtifactPath
        version_stdout = ($VersionOutput -join "`n").Trim()
        version_exit_code = $VersionExitCode
    }
}

$Json = $Result | ConvertTo-Json -Depth 6
if ($OutputJson) {
    $OutputParent = Split-Path -Parent $OutputJson
    if ($OutputParent -and -not (Test-Path -LiteralPath $OutputParent)) {
        New-Item -ItemType Directory -Path $OutputParent | Out-Null
    }
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath($OutputJson),
        "$Json`n",
        [System.Text.UTF8Encoding]::new($false)
    )
}
$Json
