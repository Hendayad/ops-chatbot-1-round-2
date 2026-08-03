# One-shot smoke test for the new Ops-gated progress ingestion endpoint
# (POST /api/v1/progress/batch). Registers a throwaway user, flips it to
# Ops via set_user_ops.py, then submits a batch of two LearnerProgress
# snapshots (one healthy, one at-risk) and prints what came back.
# Safe to run repeatedly -- each run uses a fresh disposable account and
# fresh synthetic learner_ids, so it never collides with real data.
# Local-only dev/verification script -- do not point $base at a deployed environment.

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "progress-test-$stamp@example.com"
$password = $env:OPS_CHATBOT_TEST_PASSWORD
if (-not $password) {
    Write-Error "Set `$env:OPS_CHATBOT_TEST_PASSWORD before running this script (no default -- avoids a real credential living in git history)."
    exit 1
}
$learnerAtRisk = "test-atrisk-$stamp"
$learnerHealthy = "test-healthy-$stamp"

function Show-ErrorBody($err) {
    if ($err.ErrorDetails -and $err.ErrorDetails.Message) {
        Write-Host $err.ErrorDetails.Message -ForegroundColor Red
    } else {
        Write-Host $err.Exception.Message -ForegroundColor Red
    }
}

Write-Host "1. Registering throwaway Ops user $email ..." -ForegroundColor Cyan
try {
    $registerBody = @{ email = $email; password = $password; username = "progress-test" } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "$base/api/v1/auth/register" -Method Post -ContentType "application/json" -Body $registerBody
    Write-Host "   registered OK" -ForegroundColor Green
} catch {
    Write-Host "   FAILED at register:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}

Write-Host "2. Logging in ..." -ForegroundColor Cyan
try {
    $loginBody = "email=$([uri]::EscapeDataString($email))&password=$([uri]::EscapeDataString($password))&grant_type=password"
    $loginResp = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post -ContentType "application/x-www-form-urlencoded" -Body $loginBody
    $loginToken = $loginResp.access_token
    Write-Host "   login OK" -ForegroundColor Green
} catch {
    Write-Host "   FAILED at login:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}

Write-Host "3. Granting Ops access via set_user_ops.py ..." -ForegroundColor Cyan
try {
    uv run python set_user_ops.py --email $email
    Write-Host "   is_ops flip OK" -ForegroundColor Green
} catch {
    Write-Host "   FAILED at set_user_ops.py -- run it manually: uv run python set_user_ops.py --email $email" -ForegroundColor Red
    exit 1
}

Write-Host "4. Submitting progress batch (2 snapshots: 1 at-risk, 1 healthy) ..." -ForegroundColor Cyan
try {
    $nowUtc = (Get-Date).ToUniversalTime().ToString("o")
    $longAgoUtc = (Get-Date).ToUniversalTime().AddDays(-20).ToString("o")

    $batchBody = @{
        snapshots = @(
            @{
                learner_id = $learnerAtRisk
                cohort_id = "test-cohort"
                total_tasks = 10
                completed_tasks = 2
                missed_deadlines = 3
                last_active_at = $longAgoUtc
                recent_feedback = @()
            },
            @{
                learner_id = $learnerHealthy
                cohort_id = "test-cohort"
                total_tasks = 10
                completed_tasks = 9
                missed_deadlines = 0
                last_active_at = $nowUtc
                recent_feedback = @()
            }
        )
    } | ConvertTo-Json -Depth 6

    $batchResp = Invoke-RestMethod -Uri "$base/api/v1/progress/batch" -Method Post -ContentType "application/json" -Headers @{ Authorization = "Bearer $loginToken" } -Body $batchBody
    Write-Host "   batch ingest succeeded!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Response ===" -ForegroundColor Yellow
    Write-Host "upserted_count: $($batchResp.upserted_count)"
    Write-Host "learner_ids: $($batchResp.learner_ids -join ', ')"
} catch {
    Write-Host "   FAILED at batch ingest:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}

Write-Host ""
Write-Host "5. Confirming non-Ops accounts are rejected (403) ..." -ForegroundColor Cyan
try {
    $plainEmail = "progress-noaccess-$stamp@example.com"
    $regBody2 = @{ email = $plainEmail; password = $password; username = "no-access" } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "$base/api/v1/auth/register" -Method Post -ContentType "application/json" -Body $regBody2
    $loginBody2 = "email=$([uri]::EscapeDataString($plainEmail))&password=$([uri]::EscapeDataString($password))&grant_type=password"
    $loginResp2 = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post -ContentType "application/x-www-form-urlencoded" -Body $loginBody2
    $plainToken = $loginResp2.access_token

    try {
        $null = Invoke-RestMethod -Uri "$base/api/v1/progress/batch" -Method Post -ContentType "application/json" -Headers @{ Authorization = "Bearer $plainToken" } -Body $batchBody
        Write-Host "   UNEXPECTED: non-Ops user was allowed through!" -ForegroundColor Red
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 403) {
            Write-Host "   correctly rejected with 403" -ForegroundColor Green
        } else {
            Write-Host "   rejected, but with unexpected status $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "   setup for the 403 check itself failed:" -ForegroundColor Red
    Show-ErrorBody $_
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
