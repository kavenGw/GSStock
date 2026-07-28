<#
Poll a URL until it responds, then open it in the default browser.
Called in the background by tunnel.bat.
Exit code: 0 = opened; 1 = timed out without a response.
#>
param(
    [string]$Url = 'http://127.0.0.1:5000/',
    [int]$TimeoutSeconds = 60,
    [int]$IntervalMs = 500
)

# A global proxy (Clash/v2ray etc.) can hijack requests to 127.0.0.1; disable it explicitly.
[System.Net.WebRequest]::DefaultWebProxy = $null

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    $reachable = $false
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        $reachable = $true
    } catch {
        # Getting any HTTP response (including 4xx/5xx) proves the forwarding chain is up;
        # Response is null when the connection itself was refused.
        if ($_.Exception.Response) { $reachable = $true }
    }

    if ($reachable) {
        Write-Host "Tunnel is up, opening $Url"
        Start-Process $Url
        exit 0
    }

    Start-Sleep -Milliseconds $IntervalMs
}

Write-Host "Timed out after $TimeoutSeconds s, $Url never responded"
exit 1
