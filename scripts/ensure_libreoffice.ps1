[CmdletBinding()]
param(
    [string]$PreferredPath = 'C:\Program Files\LibreOffice\program\soffice.exe',
    [switch]$NoInstall,
    [switch]$ResolveOfficialOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-LibreOfficeCandidates {
    param([string]$Preferred)
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($Preferred) { $candidates.Add($Preferred) }
    $command = Get-Command soffice.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates.Add($command.Source) }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'LibreOffice\program\soffice.exe'))
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if ($programFilesX86) {
        $candidates.Add((Join-Path $programFilesX86 'LibreOffice\program\soffice.exe'))
    }
    $registryRoots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($root in $registryRoots) {
        Get-ItemProperty -Path $root -ErrorAction SilentlyContinue |
            Where-Object {
                $_.PSObject.Properties['DisplayName'] -and
                $_.PSObject.Properties['InstallLocation'] -and
                $_.DisplayName -like 'LibreOffice*' -and $_.InstallLocation
            } |
            ForEach-Object {
                $candidates.Add((Join-Path $_.InstallLocation 'program\soffice.exe'))
            }
    }
    return $candidates | Where-Object { $_ } | Select-Object -Unique
}

function Find-LibreOffice {
    param([string]$Preferred)
    foreach ($candidate in Get-LibreOfficeCandidates -Preferred $Preferred) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $resolved = (Resolve-Path -LiteralPath $candidate).Path
            $version = (Get-Item -LiteralPath $resolved).VersionInfo.ProductVersion
            return [pscustomobject]@{ Path = $resolved; Version = $version }
        }
    }
    return $null
}

function Get-OfficialLatestInstaller {
    $page = Invoke-WebRequest -Uri 'https://www.libreoffice.org/download/' -UseBasicParsing -TimeoutSec 45
    $isArm = $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_IDENTIFIER -match 'ARM'
    $directoryArch = if ($isArm) { 'aarch64' } else { 'x86_64' }
    $fileArch = if ($isArm) { 'aarch64' } else { 'x86-64' }
    $pattern = 'https://download\.documentfoundation\.org/libreoffice/stable/' +
        '(?<version>[0-9]+(?:\.[0-9]+){2,3})/win/' + [regex]::Escape($directoryArch) +
        '/LibreOffice_(?<fileversion>[0-9]+(?:\.[0-9]+){2,3})_Win_' +
        [regex]::Escape($fileArch) + '\.msi'
    $matches = [regex]::Matches($page.Content, $pattern)
    if ($matches.Count -eq 0) {
        throw 'The official LibreOffice page did not expose a stable Windows MSI link.'
    }
    $items = foreach ($match in $matches) {
        $uri = [Uri]$match.Value
        if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'download.documentfoundation.org') {
            continue
        }
        [pscustomobject]@{
            Version = [version]$match.Groups['version'].Value
            Uri = $uri.AbsoluteUri
        }
    }
    $latest = $items | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $latest) { throw 'No trusted LibreOffice stable installer URL was found.' }
    return $latest
}

function Install-WithWinget {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }
    $arguments = @(
        'install', '--id', 'TheDocumentFoundation.LibreOffice', '--exact',
        '--source', 'winget', '--scope', 'machine', '--silent', '--disable-interactivity',
        '--accept-package-agreements', '--accept-source-agreements'
    )
    $process = Start-Process -FilePath $winget.Source -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
    return $process.ExitCode -eq 0
}

function Remove-VerifiedTempDirectory {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return }
    $resolved = [IO.Path]::GetFullPath($Path)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $leaf = Split-Path -Leaf $resolved
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not $leaf.StartsWith('soil-third-survey-libreoffice-', [StringComparison]::Ordinal)) {
        throw "Refusing to remove an unverified temporary directory: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Install-OfficialMsi {
    param([pscustomobject]$Installer)
    $tempDirectory = Join-Path ([IO.Path]::GetTempPath()) ('soil-third-survey-libreoffice-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDirectory | Out-Null
    try {
        $msiPath = Join-Path $tempDirectory 'LibreOffice.msi'
        $hashPath = Join-Path $tempDirectory 'LibreOffice.msi.sha256'
        Invoke-WebRequest -Uri $Installer.Uri -OutFile $msiPath -UseBasicParsing -TimeoutSec 1800
        Invoke-WebRequest -Uri ($Installer.Uri + '.sha256') -OutFile $hashPath -UseBasicParsing -TimeoutSec 60
        $expectedText = Get-Content -LiteralPath $hashPath -Raw
        $expectedMatch = [regex]::Match($expectedText, '(?i)\b[0-9a-f]{64}\b')
        if (-not $expectedMatch.Success) { throw 'The official SHA-256 file did not contain a valid digest.' }
        $actual = (Get-FileHash -LiteralPath $msiPath -Algorithm SHA256).Hash
        if ($actual -ne $expectedMatch.Value.ToUpperInvariant()) {
            throw 'LibreOffice MSI SHA-256 verification failed.'
        }
        $signature = Get-AuthenticodeSignature -FilePath $msiPath
        if ($signature.Status -ne 'Valid') {
            throw "LibreOffice MSI signature is not valid: $($signature.Status)"
        }
        $arguments = '/i "' + $msiPath + '" /qn /norestart'
        $process = Start-Process -FilePath 'msiexec.exe' -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -notin 0, 3010) {
            throw "LibreOffice MSI installation failed with exit code $($process.ExitCode)."
        }
    }
    finally {
        Remove-VerifiedTempDirectory -Path $tempDirectory
    }
}

function Write-Result {
    param([string]$Status, [pscustomobject]$Office, [string]$Method)
    $result = [ordered]@{
        status = $Status
        method = $Method
        path = $Office.Path
        version = $Office.Version
    }
    if ($Json) { $result | ConvertTo-Json -Compress } else { $Office.Path }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'This automatic installer currently supports Windows only.'
}

if ($ResolveOfficialOnly) {
    $official = Get-OfficialLatestInstaller
    $result = [ordered]@{ version = $official.Version.ToString(); uri = $official.Uri }
    if ($Json) { $result | ConvertTo-Json -Compress } else { $official.Uri }
    exit 0
}

$existing = Find-LibreOffice -Preferred $PreferredPath
if ($existing) {
    Write-Result -Status 'ready' -Office $existing -Method 'existing'
    exit 0
}
if ($NoInstall) {
    Write-Error 'LibreOffice was not found and -NoInstall was specified.'
    exit 2
}

$official = $null
try { $official = Get-OfficialLatestInstaller } catch { Write-Verbose $_.Exception.Message }
$wingetSucceeded = $false
try { $wingetSucceeded = Install-WithWinget } catch { Write-Verbose $_.Exception.Message }
$installed = Find-LibreOffice -Preferred $PreferredPath

if ($installed -and $official) {
    $installedVersion = $null
    try { $installedVersion = [version](($installed.Version -split '[^0-9.]')[0]) } catch { }
    if ($installedVersion -and $installedVersion -ge $official.Version) {
        Write-Result -Status 'installed' -Office $installed -Method 'winget'
        exit 0
    }
}
elseif ($installed) {
    Write-Result -Status 'installed' -Office $installed -Method 'winget'
    exit 0
}

if (-not $official) {
    throw 'LibreOffice is missing. WinGet did not produce a usable installation and the official stable installer could not be resolved.'
}
Install-OfficialMsi -Installer $official
$installed = Find-LibreOffice -Preferred $PreferredPath
if (-not $installed) { throw 'LibreOffice installation completed but soffice.exe was not found.' }
Write-Result -Status 'installed' -Office $installed -Method 'official-msi'

