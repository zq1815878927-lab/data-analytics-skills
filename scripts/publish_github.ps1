param(
    [ValidateSet('Private', 'Public')]
    [string]$Visibility = 'Private',
    [switch]$Login
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

function Find-Tool([string]$Name, [string]$PortablePath) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    $Candidate = Join-Path $RepoRoot $PortablePath
    if (Test-Path -LiteralPath $Candidate) { return $Candidate }
    throw "$Name is not installed. Install the official Git/GitHub CLI, or restore the ignored portable tools."
}

$Git = Find-Tool 'git' '.tools\git\cmd\git.exe'
$Gh = Find-Tool 'gh' '.tools\gh\bin\gh.exe'
$env:PATH = (Split-Path -Parent $Git) + ';' + (Split-Path -Parent $Gh) + ';' + $env:PATH

# Match the user's configured Windows proxy, without disabling TLS verification.
if (-not $env:HTTPS_PROXY) {
    $Target = [uri]'https://github.com'
    $Proxy = [System.Net.WebRequest]::DefaultWebProxy
    if ($Proxy -and -not $Proxy.IsBypassed($Target)) {
        $env:HTTPS_PROXY = $Proxy.GetProxy($Target).AbsoluteUri
    }
}

& $Gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) {
    if (-not $Login) { throw 'GitHub is not logged in. Run this script with -Login to authorize in your browser.' }
    & $Gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key --scopes workflow
    if ($LASTEXITCODE -ne 0) { throw 'GitHub authorization did not complete. No repository was created or pushed.' }
}

$UserJson = & $Gh api user
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the authenticated GitHub account.' }
$User = $UserJson | ConvertFrom-Json
$Repository = $User.login + '/data-analytics-skills'

$Branch = & $Git -C $RepoRoot branch --show-current
if ($LASTEXITCODE -ne 0 -or $Branch -ne 'main') { throw 'Expected the prepared local main branch. No branch will be replaced automatically.' }
$Head = & $Git -C $RepoRoot rev-parse --verify HEAD
if ($LASTEXITCODE -ne 0) { throw 'Create a local Git commit before publishing.' }
$Changes = & $Git -C $RepoRoot status --porcelain
if ($LASTEXITCODE -ne 0 -or $Changes) { throw 'Commit or intentionally exclude local changes before publishing. This helper never stages files automatically.' }

$Remotes = @(& $Git -C $RepoRoot remote)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local Git remotes.' }
if ($Remotes -contains 'origin') {
    $Origin = & $Git -C $RepoRoot remote get-url origin
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the existing origin URL.' }
    $AllowedOrigins = @(
        ('https://github.com/' + $Repository),
        ('https://github.com/' + $Repository + '.git'),
        ('git@github.com:' + $Repository + '.git')
    )
    if ($Origin -notin $AllowedOrigins) { throw 'Existing origin does not match the authenticated personal account and project name. No remote was changed.' }
} else {
    # If a same-name remote repository already exists, gh returns an error.
    # Do not overwrite, force-push, or guess how to merge unrelated work.
    $VisibilityFlag = '--' + $Visibility.ToLowerInvariant()
    & $Gh repo create $Repository $VisibilityFlag --source $RepoRoot --remote origin --description 'Reproducible e-commerce analytics showcase: five synthetic-data projects with executed notebooks and tests'
    if ($LASTEXITCODE -ne 0) { throw 'Repository creation failed; check account access or a same-name repository. No force push was attempted.' }
}

# Credential helper is scoped to these commands, not the global Git config.
& $Git -C $RepoRoot -c 'credential.helper=' -c 'credential.helper=!gh auth git-credential' push --set-upstream origin main
if ($LASTEXITCODE -ne 0) { throw 'Push failed. The local commit remains intact; retry after fixing network or permissions.' }
$RemoteLine = & $Git -C $RepoRoot -c 'credential.helper=' -c 'credential.helper=!gh auth git-credential' ls-remote origin refs/heads/main
if ($LASTEXITCODE -ne 0 -or -not $RemoteLine) { throw 'Cannot verify the remote main branch.' }
$RemoteHead = ($RemoteLine -split '\s+')[0]
if ($RemoteHead -ne $Head) { throw 'Remote main does not match local HEAD; investigate before reporting success.' }

$RepoJson = & $Gh repo view $Repository --json url,visibility
if ($LASTEXITCODE -ne 0) { throw 'Push succeeded, but repository metadata lookup failed.' }
$RemoteRepo = $RepoJson | ConvertFrom-Json
Write-Output ('Published: ' + $RemoteRepo.url)
Write-Output ('Visibility: ' + $RemoteRepo.visibility)
Write-Output ('Verified commit: ' + $Head)
