$ProgressFile = "progress.txt"
$MaxIterations = 15
$Iteration = 1

while ($Iteration -le $MaxIterations) {
    $NextTask = (Get-Content $ProgressFile) | Where-Object { $_ -match '^- \[ \] ' } | Select-Object -First 1
    if (-not $NextTask) {
        Write-Host "[+] All tasks completed!" -ForegroundColor Green
        break
    }
    Write-Host "[*] Iteration $Iteration | Next Objective: $NextTask" -ForegroundColor Cyan
    if (Test-Path ".git") {
        if (git status --porcelain) {
            git add -A
            $CleanMsg = $NextTask -replace '^- \[ \] ', ''
            git commit -m "ralph: $CleanMsg"
        }
    }
    $Iteration++
}
