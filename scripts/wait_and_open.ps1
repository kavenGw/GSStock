<#
轮询 URL 直到可访问，成功后用默认浏览器打开。由 tunnel.bat 后台调用。
退出码：0 = 已打开；1 = 超时未探到。
#>
param(
    [string]$Url = 'http://127.0.0.1:5000/',
    [int]$TimeoutSeconds = 60,
    [int]$IntervalMs = 500
)

# 全局代理（Clash/v2ray 等）可能截走 127.0.0.1 请求，显式禁用
[System.Net.WebRequest]::DefaultWebProxy = $null

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    $reachable = $false
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        $reachable = $true
    } catch {
        # 拿到 HTTP 响应（含 4xx/5xx）即说明转发链路已建立；连接被拒时 Response 为 null
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
