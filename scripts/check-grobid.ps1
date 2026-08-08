[CmdletBinding()]
param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$ContainerName = "review-workflow-grobid"
$ImageName = "grobid/grobid:0.9.0-full"
$HealthUrl = "http://127.0.0.1:8070/api/isalive"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL is not installed or wsl.exe is unavailable. Use windows-lite or install WSL2 first."
}

$WslStatus = & wsl.exe --status 2>&1
Write-Output ($WslStatus | Out-String).Trim()

& wsl.exe -e sh -lc "command -v docker >/dev/null 2>&1"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is not available inside the default WSL distribution."
}

$DockerVersion = & wsl.exe -e sh -lc "docker version --format '{{.Server.Version}}' 2>/dev/null"
if ($LASTEXITCODE -ne 0 -or -not $DockerVersion) {
    if ($Start) {
        Write-Output "Docker Engine is installed but stopped; starting its WSL service."
        & wsl.exe -u root -e sh -lc "service docker start"
        if ($LASTEXITCODE -ne 0) { throw "Docker Engine service failed to start inside WSL." }
        $DockerVersion = & wsl.exe -e sh -lc "docker version --format '{{.Server.Version}}' 2>/dev/null"
    } else {
        throw "Docker Engine is installed but its daemon is not reachable inside WSL. Rerun with -Start to start it."
    }
}
if ($LASTEXITCODE -ne 0 -or -not $DockerVersion) {
    throw "Docker Engine service started, but its daemon is still unreachable inside WSL."
}
Write-Output "WSL Docker Engine server: $DockerVersion"

$ExistingContainer = & wsl.exe -e sh -lc "docker inspect -f '{{.State.Status}}' $ContainerName 2>/dev/null || true"
if ($ExistingContainer) {
    Write-Output "GROBID container state: $ExistingContainer"
} else {
    Write-Output "GROBID container does not exist."
}

if ($Start) {
    if ($ExistingContainer -eq "running") {
        Write-Output "GROBID container is already running."
    } elseif ($ExistingContainer) {
        & wsl.exe -e sh -lc "docker start $ContainerName"
        if ($LASTEXITCODE -ne 0) { throw "docker start failed" }
    } else {
        # docker run is intentionally reachable only through the explicit -Start switch.
        & wsl.exe -e sh -lc "docker run -d --name $ContainerName -p 8070:8070 $ImageName"
        if ($LASTEXITCODE -ne 0) { throw "docker run failed" }
    }
}

try {
    $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 5
    $Body = $Response.Content.Trim()
    if ($Body -notin @("true", "ok", "1")) {
        throw "Unexpected GROBID health response: $Body"
    }
    Write-Output "GROBID healthy at $HealthUrl"
} catch {
    if ($Start) {
        throw "GROBID was started but is not healthy yet. Wait for model loading, then rerun this script without -Start."
    }
    Write-Output "GROBID is not currently healthy. This is acceptable for windows-lite."
    exit 2
}
