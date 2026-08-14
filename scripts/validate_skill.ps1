[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$skillPath = Split-Path -Parent $PSScriptRoot
$skillFile = Join-Path $skillPath 'SKILL.md'
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
    throw 'SKILL.md is missing.'
}

$creatorValidator = Join-Path (Split-Path -Parent $skillPath) '.system\skill-creator\scripts\quick_validate.py'
if (Test-Path -LiteralPath $creatorValidator -PathType Leaf) {
    & python $creatorValidator $skillPath
    if ($LASTEXITCODE -ne 0) { throw 'skill-creator quick validation failed.' }
}
else {
    $content = Get-Content -LiteralPath $skillFile -Raw -Encoding UTF8
    if ($content -notmatch '(?s)^---\s*\r?\nname:\s*soil-third-survey-report\s*\r?\ndescription:\s*.+?\r?\n---') {
        throw 'SKILL.md frontmatter is invalid.'
    }
}

$missingLinks = [System.Collections.Generic.List[string]]::new()
Get-ChildItem -LiteralPath $skillPath -Recurse -File -Filter '*.md' | ForEach-Object {
    $markdown = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
    foreach ($match in [regex]::Matches($markdown, '\[[^\]]+\]\((?<target>[^)]+)\)')) {
        $target = $match.Groups['target'].Value.Trim()
        if ($target -match '^(?:https?://|#|mailto:)') { continue }
        $target = ($target -split '#', 2)[0]
        if (-not $target) { continue }
        $resolved = Join-Path $_.DirectoryName ($target -replace '/', '\')
        if (-not (Test-Path -LiteralPath $resolved)) {
            $missingLinks.Add("$($_.FullName) -> $target")
        }
    }
}
if ($missingLinks.Count) {
    throw ("Missing relative references:`n" + ($missingLinks -join "`n"))
}

& python (Join-Path $PSScriptRoot 'test_scan_report_text.py')
if ($LASTEXITCODE -ne 0) { throw 'Scanner regression tests failed.' }

$tokens = $null
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot 'ensure_libreoffice.ps1'),
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count) {
    throw ("LibreOffice installer script has syntax errors:`n" + (($parseErrors | ForEach-Object Message) -join "`n"))
}

'SKILL_VALIDATION=PASS'

