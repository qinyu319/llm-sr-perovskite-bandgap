param(
    [int]$StartRun = 9,
    [int]$EndRun = 30,
    [int]$Parallelism = 6,
    [string]$Model = "gpt-5.5"
)

$ErrorActionPreference = "Stop"

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
if ($null -eq $codexCommand) {
    throw "Could not locate the Codex CLI on PATH."
}
$codex = $codexCommand.Source
$workspace = (Resolve-Path ".").Path
$promptTemplate = Get-Content -Raw -Encoding UTF8 ".\prompts\M4.txt"
$outputDir = Join-Path $workspace "raw_outputs\codex_runs"
$tempDir = Join-Path $outputDir "_work"

New-Item -ItemType Directory -Force $outputDir, $tempDir | Out-Null

function Start-CodexRun {
    param([int]$RunId)

    $runLabel = $RunId.ToString("00")
    $resultPath = Join-Path $outputDir "run_$runLabel.txt"
    if (Test-Path $resultPath) {
        return $null
    }

    $promptPath = Join-Path $tempDir "prompt_$runLabel.txt"
    $stdoutPath = Join-Path $tempDir "stdout_$runLabel.log"
    $stderrPath = Join-Path $tempDir "stderr_$runLabel.log"
    $prompt = "Independent run $runLabel. Follow the prompt exactly. Return exactly one line and no explanation.`r`n`r`n$promptTemplate"
    [System.IO.File]::WriteAllText($promptPath, $prompt, [System.Text.UTF8Encoding]::new($false))

    $arguments = @(
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox", "read-only",
        "--model", $Model,
        "-c", 'model_reasoning_effort="low"',
        "--cd", $workspace,
        "--output-last-message", $resultPath,
        "-"
    )

    $process = Start-Process `
        -FilePath $codex `
        -ArgumentList $arguments `
        -RedirectStandardInput $promptPath `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    return [pscustomobject]@{
        RunId = $RunId
        Process = $process
        ResultPath = $resultPath
        StdoutPath = $stdoutPath
        StderrPath = $stderrPath
    }
}

$pending = [System.Collections.Generic.Queue[int]]::new()
for ($runId = $StartRun; $runId -le $EndRun; $runId++) {
    $resultPath = Join-Path $outputDir ("run_{0}.txt" -f $runId.ToString("00"))
    if (-not (Test-Path $resultPath)) {
        $pending.Enqueue($runId)
    }
}

$active = [System.Collections.Generic.List[object]]::new()
$failed = [System.Collections.Generic.List[int]]::new()

while ($pending.Count -gt 0 -or $active.Count -gt 0) {
    while ($pending.Count -gt 0 -and $active.Count -lt $Parallelism) {
        $run = Start-CodexRun -RunId $pending.Dequeue()
        if ($null -ne $run) {
            $active.Add($run)
            Write-Host ("Started run {0:00} (PID {1})" -f $run.RunId, $run.Process.Id)
        }
    }

    Start-Sleep -Seconds 2
    for ($index = $active.Count - 1; $index -ge 0; $index--) {
        $run = $active[$index]
        if (-not $run.Process.HasExited) {
            continue
        }

        $run.Process.Refresh()
        $hasResult = (Test-Path $run.ResultPath) -and ((Get-Item $run.ResultPath).Length -gt 0)
        if ($hasResult) {
            $raw = (Get-Content -Raw -Encoding UTF8 $run.ResultPath).Trim()
            Write-Host ("Completed run {0:00}: {1}" -f $run.RunId, $raw)
        }
        else {
            $failed.Add($run.RunId)
            Write-Warning ("Run {0:00} did not produce a result. See {1}" -f $run.RunId, $run.StderrPath)
        }
        $active.RemoveAt($index)
    }
}

if ($failed.Count -gt 0) {
    throw "Failed run IDs: $($failed -join ', ')"
}

Write-Host "All requested Codex runs completed."
