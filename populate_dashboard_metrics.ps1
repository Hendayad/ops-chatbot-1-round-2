# Hits GET /api/v1/dashboards/metrics once as a throwaway user -- that
# endpoint is what actually computes real numbers from the DB and pushes
# them into the Prometheus gauges Grafana's Ops dashboard reads
# (update_support_metrics / update_open_issues_metrics / update_alert_metrics
# in app/metrics/kpis.py). Nothing reads it until someone calls it, so
# Grafana shows "No data" until this runs at least once. Any authenticated
# user works -- no ops privileges required, so the throwaway test account
# is fine here.

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "metrics-poke-$stamp@example.com"
$password = "TestPass123!"

function Show-ErrorBody($err) {
    if ($err.ErrorDetails -and $err.ErrorDetails.Message) {
        Write-Host $err.ErrorDetails.Message -ForegroundColor Red
    } else {
        Write-Host $err.Exception.Message -ForegroundColor Red
    }
}

try {
    $registerBody = @{ email = $email; password = $password; username = "metrics-poke" } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "$base/api/v1/auth/register" -Method Post -ContentType "application/json" -Body $registerBody

    $loginBody = "email=$([uri]::EscapeDataString($email))&password=$([uri]::EscapeDataString($password))&grant_type=password"
    $loginResp = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post -ContentType "application/x-www-form-urlencoded" -Body $loginBody
    $token = $loginResp.access_token

    Write-Host "Calling GET /api/v1/dashboards/metrics ..." -ForegroundColor Cyan
    $metrics = Invoke-RestMethod -Uri "$base/api/v1/dashboards/metrics" -Method Get -Headers @{ Authorization = "Bearer $token" }
    Write-Host "Done -- Prometheus gauges updated. Response:" -ForegroundColor Green
    $metrics | ConvertTo-Json -Depth 6
} catch {
    Write-Host "FAILED:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}
