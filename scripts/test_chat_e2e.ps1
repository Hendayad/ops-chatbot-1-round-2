# One-shot end-to-end smoke test: register a throwaway user, log in, open a
# session, send a chat message, print the AI's reply -- no manual copy-paste
# of tokens through /docs required. Safe to run repeatedly; each run creates
# a brand-new disposable test account so it never collides with a real one.
# Local-only dev/verification script -- do not point $base at a deployed environment.

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "e2e-test-$stamp@example.com"
$password = $env:OPS_CHATBOT_TEST_PASSWORD
if (-not $password) {
    Write-Error "Set `$env:OPS_CHATBOT_TEST_PASSWORD before running this script (no default -- avoids a real credential living in git history)."
    exit 1
}

function Show-ErrorBody($err) {
    if ($err.ErrorDetails -and $err.ErrorDetails.Message) {
        Write-Host $err.ErrorDetails.Message -ForegroundColor Red
    } else {
        Write-Host $err.Exception.Message -ForegroundColor Red
    }
}

Write-Host "1. Registering throwaway user $email ..." -ForegroundColor Cyan
try {
    $registerBody = @{ email = $email; password = $password; username = "e2e-test" } | ConvertTo-Json
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

Write-Host "3. Creating chat session ..." -ForegroundColor Cyan
try {
    $sessionResp = Invoke-RestMethod -Uri "$base/api/v1/auth/session" -Method Post -Headers @{ Authorization = "Bearer $loginToken" }
    $sessionToken = $sessionResp.token.access_token
    Write-Host "   session OK: $($sessionResp.session_id)" -ForegroundColor Green
} catch {
    Write-Host "   FAILED at session creation:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}

Write-Host "4. Sending chat message ..." -ForegroundColor Cyan
try {
    $chatBody = @{ messages = @(@{ role = "user"; content = "Hi, can you hear me? Just testing the new API key." }) } | ConvertTo-Json -Depth 5
    $chatResp = Invoke-RestMethod -Uri "$base/api/v1/chatbot/chat" -Method Post -ContentType "application/json" -Headers @{ Authorization = "Bearer $sessionToken" } -Body $chatBody
    Write-Host "   chat call succeeded!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Full conversation returned ===" -ForegroundColor Yellow
    $chatResp.messages | ForEach-Object { Write-Host "[$($_.role)] $($_.content)" }
} catch {
    Write-Host "   FAILED at chat:" -ForegroundColor Red
    Show-ErrorBody $_
    exit 1
}
