param(
    [string]$TrainPath = "",
    [string]$TestPath = "",
    [string]$OutputDir = ".\results",
    [int]$Seed = 20260607
)

$ErrorActionPreference = "Stop"
$Culture = [System.Globalization.CultureInfo]::InvariantCulture

if ([string]::IsNullOrWhiteSpace($TrainPath)) {
    $TrainPath = Join-Path "." (([string][char]0x8BAD) + [char]0x7EC3 + [char]0x96C6 + ".xlsx")
}
if ([string]::IsNullOrWhiteSpace($TestPath)) {
    $TestPath = Join-Path "." (([string][char]0x6D4B) + [char]0x8BD5 + [char]0x96C6 + ".xlsx")
}

$TermNames = @(
    "Sn", "Br", "Cl", "Cs",
    "Sn^2", "Br^2", "Cl^2", "Cs^2",
    "Sn*Br", "Sn*Cl", "Br*Cl",
    "Cs*Sn", "Cs*Br", "Cs*Cl"
)

function Get-BitCount {
    param([int]$Value)
    $count = 0
    while ($Value -ne 0) {
        $count += ($Value -band 1)
        $Value = $Value -shr 1
    }
    return $count
}

function Read-WorkbookRows {
    param(
        [object]$Excel,
        [string]$Path
    )

    $resolved = (Resolve-Path $Path).Path
    $workbook = $null
    $sheet = $null
    $used = $null
    try {
        $workbook = $Excel.Workbooks.Open($resolved, 0, $true)
        $sheet = $workbook.Worksheets.Item(1)
        $used = $sheet.UsedRange
        $values = $used.Value2
        $rowCount = $used.Rows.Count
        $columnCount = $used.Columns.Count

        $headers = @{}
        for ($column = 1; $column -le $columnCount; $column++) {
            $header = ([string]$values[1,$column]).Trim()
            $headers[$header.ToLowerInvariant()] = $column
        }

        $required = @("id", "fa", "ma", "cs", "pb", "sn", "br", "cl", "i")
        foreach ($name in $required) {
            if (-not $headers.ContainsKey($name)) {
                throw "Missing required column '$name' in $Path."
            }
        }
        $targetName = if ($headers.ContainsKey("bg")) { "bg" } else { $null }
        if ($null -eq $targetName) {
            throw "Missing target column 'Bg/bg' in $Path."
        }

        $rows = [System.Collections.Generic.List[object]]::new()
        for ($row = 2; $row -le $rowCount; $row++) {
            $idValue = $values[$row,$headers["id"]]
            if ($null -eq $idValue -or ([string]$idValue).Trim() -eq "") {
                continue
            }
            $record = [ordered]@{}
            foreach ($name in @("id", "fa", "ma", "cs", "pb", "sn", "br", "cl", "i", "bg")) {
                $value = $values[$row,$headers[$name]]
                if ($null -eq $value -or ([string]$value).Trim() -eq "") {
                    throw "Blank value in row $row, column '$name' of $Path."
                }
                $record[$name] = [double]$value
            }
            $rows.Add([pscustomobject]$record)
        }
        return ,$rows.ToArray()
    }
    finally {
        if ($null -ne $workbook) {
            $workbook.Close($false)
        }
        foreach ($comObject in @($used, $sheet, $workbook)) {
            if ($null -ne $comObject) {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($comObject)
            }
        }
    }
}

function Convert-ToFeatureMatrix {
    param([object[]]$Rows)

    $matrix = [object[]]::new($Rows.Count)
    $targets = [double[]]::new($Rows.Count)
    for ($i = 0; $i -lt $Rows.Count; $i++) {
        $sn = $Rows[$i].sn
        $br = $Rows[$i].br
        $cl = $Rows[$i].cl
        $cs = $Rows[$i].cs
        $matrix[$i] = [double[]]@(
            1.0,
            $sn, $br, $cl, $cs,
            ($sn * $sn), ($br * $br), ($cl * $cl), ($cs * $cs),
            ($sn * $br), ($sn * $cl), ($br * $cl),
            ($cs * $sn), ($cs * $br), ($cs * $cl)
        )
        $targets[$i] = $Rows[$i].bg
    }
    return [pscustomobject]@{ X = $matrix; Y = $targets }
}

function New-Gram {
    param(
        [object[]]$X,
        [double[]]$Y,
        [int[]]$Indices
    )

    $columnCount = $X[0].Count
    $xtx = [double[,]]::new($columnCount, $columnCount)
    $xty = [double[]]::new($columnCount)
    foreach ($rowIndex in $Indices) {
        $row = $X[$rowIndex]
        $target = $Y[$rowIndex]
        for ($j = 0; $j -lt $columnCount; $j++) {
            $xty[$j] += $row[$j] * $target
            for ($k = $j; $k -lt $columnCount; $k++) {
                $xtx[$j,$k] += $row[$j] * $row[$k]
            }
        }
    }
    for ($j = 0; $j -lt $columnCount; $j++) {
        for ($k = 0; $k -lt $j; $k++) {
            $xtx[$j,$k] = $xtx[$k,$j]
        }
    }
    return [pscustomobject]@{ XtX = $xtx; Xty = $xty }
}

function Subtract-Gram {
    param([object]$All, [object]$Part)
    $size = $All.Xty.Count
    $xtx = [double[,]]::new($size, $size)
    $xty = [double[]]::new($size)
    for ($j = 0; $j -lt $size; $j++) {
        $xty[$j] = $All.Xty[$j] - $Part.Xty[$j]
        for ($k = 0; $k -lt $size; $k++) {
            $xtx[$j,$k] = $All.XtX[$j,$k] - $Part.XtX[$j,$k]
        }
    }
    return [pscustomobject]@{ XtX = $xtx; Xty = $xty }
}

function Solve-LinearSystem {
    param(
        [double[,]]$InputA,
        [double[]]$InputB
    )

    $n = $InputB.Count
    $a = [double[,]]::new($n, $n)
    $b = [double[]]::new($n)
    for ($i = 0; $i -lt $n; $i++) {
        $b[$i] = $InputB[$i]
        for ($j = 0; $j -lt $n; $j++) {
            $a[$i,$j] = $InputA[$i,$j]
        }
    }

    for ($pivot = 0; $pivot -lt $n; $pivot++) {
        $maxRow = $pivot
        $maxValue = [Math]::Abs(($a[$pivot,$pivot]))
        for ($row = $pivot + 1; $row -lt $n; $row++) {
            $candidate = [Math]::Abs(($a[$row,$pivot]))
            if ($candidate -gt $maxValue) {
                $maxValue = $candidate
                $maxRow = $row
            }
        }
        if ($maxValue -lt 1e-12) {
            return $null
        }
        if ($maxRow -ne $pivot) {
            for ($column = $pivot; $column -lt $n; $column++) {
                $temp = $a[$pivot,$column]
                $a[$pivot,$column] = $a[$maxRow,$column]
                $a[$maxRow,$column] = $temp
            }
            $tempB = $b[$pivot]
            $b[$pivot] = $b[$maxRow]
            $b[$maxRow] = $tempB
        }

        for ($row = $pivot + 1; $row -lt $n; $row++) {
            $factor = $a[$row,$pivot] / $a[$pivot,$pivot]
            if ([Math]::Abs($factor) -lt 1e-20) {
                continue
            }
            $a[$row,$pivot] = 0.0
            for ($column = $pivot + 1; $column -lt $n; $column++) {
                $a[$row,$column] -= $factor * $a[$pivot,$column]
            }
            $b[$row] -= $factor * $b[$pivot]
        }
    }

    $solution = [double[]]::new($n)
    for ($row = $n - 1; $row -ge 0; $row--) {
        $sum = $b[$row]
        for ($column = $row + 1; $column -lt $n; $column++) {
            $sum -= $a[$row,$column] * $solution[$column]
        }
        $solution[$row] = $sum / $a[$row,$row]
    }
    return ,$solution
}

function Fit-FromGram {
    param(
        [object]$Gram,
        [int[]]$TermIds
    )

    $columns = [int[]](@(0) + @($TermIds | ForEach-Object { $_ + 1 }))
    $size = $columns.Count
    $a = [double[,]]::new($size, $size)
    $b = [double[]]::new($size)
    for ($j = 0; $j -lt $size; $j++) {
        $b[$j] = $Gram.Xty[$columns[$j]]
        for ($k = 0; $k -lt $size; $k++) {
            $a[$j,$k] = $Gram.XtX[$columns[$j],$columns[$k]]
        }
    }
    return Solve-LinearSystem -InputA $a -InputB $b
}

function Get-Prediction {
    param(
        [double[]]$Row,
        [int[]]$TermIds,
        [double[]]$Coefficients
    )
    $prediction = $Coefficients[0]
    for ($j = 0; $j -lt $TermIds.Count; $j++) {
        $prediction += $Coefficients[$j + 1] * $Row[$TermIds[$j] + 1]
    }
    return $prediction
}

function Evaluate-Candidate {
    param(
        [string]$Stage,
        [int[]]$TermIds,
        [object[]]$X,
        [double[]]$Y,
        [object[]]$TrainGrams,
        [object[]]$ValidationIndices
    )

    $foldRmse = [double[]]::new($TrainGrams.Count)
    $allActual = [System.Collections.Generic.List[double]]::new()
    $allPredicted = [System.Collections.Generic.List[double]]::new()
    for ($fold = 0; $fold -lt $TrainGrams.Count; $fold++) {
        $coefficients = Fit-FromGram -Gram $TrainGrams[$fold] -TermIds $TermIds
        if ($null -eq $coefficients) {
            return $null
        }
        $squaredError = 0.0
        foreach ($rowIndex in $ValidationIndices[$fold]) {
            $prediction = Get-Prediction -Row $X[$rowIndex] -TermIds $TermIds -Coefficients $coefficients
            $error = $Y[$rowIndex] - $prediction
            $squaredError += $error * $error
            $allActual.Add($Y[$rowIndex])
            $allPredicted.Add($prediction)
        }
        $foldRmse[$fold] = [Math]::Sqrt($squaredError / $ValidationIndices[$fold].Count)
    }

    $meanRmse = ($foldRmse | Measure-Object -Average).Average
    $variance = 0.0
    foreach ($value in $foldRmse) {
        $variance += ($value - $meanRmse) * ($value - $meanRmse)
    }
    $stdRmse = [Math]::Sqrt($variance / ($foldRmse.Count - 1))

    $meanActual = ($allActual | Measure-Object -Average).Average
    $sse = 0.0
    $sst = 0.0
    for ($i = 0; $i -lt $allActual.Count; $i++) {
        $error = $allActual[$i] - $allPredicted[$i]
        $sse += $error * $error
        $deviation = $allActual[$i] - $meanActual
        $sst += $deviation * $deviation
    }
    $cvR2 = if ($sst -gt 0) { 1.0 - ($sse / $sst) } else { [double]::NaN }

    $names = @($TermIds | ForEach-Object { $TermNames[$_] })
    return [pscustomobject]@{
        Stage = $Stage
        TermCount = $TermIds.Count
        Terms = ($names -join " + ")
        TermIds = ($TermIds -join ";")
        CV_RMSE_Mean = [double]$meanRmse
        CV_RMSE_Std = [double]$stdRmse
        CV_R2 = [double]$cvR2
        Fold_RMSE = (($foldRmse | ForEach-Object { $_.ToString("F8", $Culture) }) -join ";")
    }
}

function Get-StageCandidates {
    $stages = [ordered]@{}

    $m0 = [System.Collections.Generic.List[int[]]]::new()
    for ($mask = 1; $mask -lt 8; $mask++) {
        $terms = [System.Collections.Generic.List[int]]::new()
        for ($bit = 0; $bit -lt 3; $bit++) {
            if (($mask -band (1 -shl $bit)) -ne 0) {
                $terms.Add($bit)
            }
        }
        $m0.Add($terms.ToArray())
    }
    $stages["M0"] = $m0.ToArray()

    $m1 = [System.Collections.Generic.List[int[]]]::new()
    for ($state = 1; $state -lt 27; $state++) {
        $remaining = $state
        $terms = [System.Collections.Generic.List[int]]::new()
        for ($variable = 0; $variable -lt 3; $variable++) {
            $level = $remaining % 3
            $remaining = [Math]::Floor($remaining / 3)
            if ($level -ge 1) {
                $terms.Add($variable)
            }
            if ($level -eq 2) {
                $terms.Add(4 + $variable)
            }
        }
        $m1.Add([int[]]($terms.ToArray() | Sort-Object))
    }
    $stages["M1"] = $m1.ToArray()

    $m2 = [System.Collections.Generic.List[int[]]]::new()
    for ($squareMask = 0; $squareMask -lt 8; $squareMask++) {
        for ($interactionMask = 0; $interactionMask -lt 8; $interactionMask++) {
            $terms = [System.Collections.Generic.List[int]]::new()
            $terms.AddRange([int[]]@(0, 1, 2))
            for ($bit = 0; $bit -lt 3; $bit++) {
                if (($squareMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(4 + $bit)
                }
                if (($interactionMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(8 + $bit)
                }
            }
            if ($terms.Count -le 10) {
                $m2.Add([int[]]($terms.ToArray() | Sort-Object))
            }
        }
    }
    $stages["M2"] = $m2.ToArray()

    $m3 = [System.Collections.Generic.List[int[]]]::new()
    for ($squareMask = 0; $squareMask -lt 16; $squareMask++) {
        for ($interactionMask = 0; $interactionMask -lt 64; $interactionMask++) {
            $interactionCount = Get-BitCount $interactionMask
            $squareCount = Get-BitCount $squareMask
            if ($interactionCount -gt 4 -or (4 + $squareCount + $interactionCount) -gt 12) {
                continue
            }
            $terms = [System.Collections.Generic.List[int]]::new()
            $terms.AddRange([int[]]@(0, 1, 2, 3))
            for ($bit = 0; $bit -lt 4; $bit++) {
                if (($squareMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(4 + $bit)
                }
            }
            for ($bit = 0; $bit -lt 6; $bit++) {
                if (($interactionMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(8 + $bit)
                }
            }
            $m3.Add([int[]]($terms.ToArray() | Sort-Object))
        }
    }
    $stages["M3"] = $m3.ToArray()

    $m4 = [System.Collections.Generic.List[int[]]]::new()
    for ($squareMask = 0; $squareMask -lt 16; $squareMask++) {
        for ($interactionMask = 0; $interactionMask -lt 64; $interactionMask++) {
            $interactionCount = Get-BitCount $interactionMask
            $termCount = 4 + (Get-BitCount $squareMask) + $interactionCount
            if ($interactionCount -gt 4 -or $termCount -lt 8 -or $termCount -gt 11) {
                continue
            }
            $terms = [System.Collections.Generic.List[int]]::new()
            $terms.AddRange([int[]]@(0, 1, 2, 3))
            for ($bit = 0; $bit -lt 4; $bit++) {
                if (($squareMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(4 + $bit)
                }
            }
            for ($bit = 0; $bit -lt 6; $bit++) {
                if (($interactionMask -band (1 -shl $bit)) -ne 0) {
                    $terms.Add(8 + $bit)
                }
            }
            $m4.Add([int[]]($terms.ToArray() | Sort-Object))
        }
    }
    $stages["M4"] = $m4.ToArray()

    return $stages
}

function Get-Metrics {
    param(
        [object[]]$X,
        [double[]]$Y,
        [int[]]$TermIds,
        [double[]]$Coefficients
    )
    $sse = 0.0
    $sae = 0.0
    $mean = ($Y | Measure-Object -Average).Average
    $sst = 0.0
    for ($i = 0; $i -lt $Y.Count; $i++) {
        $prediction = Get-Prediction -Row $X[$i] -TermIds $TermIds -Coefficients $Coefficients
        $error = $Y[$i] - $prediction
        $sse += $error * $error
        $sae += [Math]::Abs($error)
        $deviation = $Y[$i] - $mean
        $sst += $deviation * $deviation
    }
    return [pscustomobject]@{
        RMSE = [Math]::Sqrt($sse / $Y.Count)
        MAE = $sae / $Y.Count
        R2 = if ($sst -gt 0) { 1.0 - ($sse / $sst) } else { [double]::NaN }
    }
}

function Format-NumericExpression {
    param(
        [int[]]$TermIds,
        [double[]]$Coefficients
    )
    $expression = "Eg = " + $Coefficients[0].ToString("0.00000000", $Culture)
    for ($i = 0; $i -lt $TermIds.Count; $i++) {
        $coefficient = $Coefficients[$i + 1]
        $operator = if ($coefficient -ge 0) { " + " } else { " - " }
        $expression += $operator + [Math]::Abs($coefficient).ToString("0.00000000", $Culture) + "*" + $TermNames[$TermIds[$i]]
    }
    return $expression
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
    $trainRows = Read-WorkbookRows -Excel $excel -Path $TrainPath
    $testRows = Read-WorkbookRows -Excel $excel -Path $TestPath
}
finally {
    $excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$train = Convert-ToFeatureMatrix -Rows $trainRows
$test = Convert-ToFeatureMatrix -Rows $testRows

$validationNotes = [System.Collections.Generic.List[string]]::new()
$validationNotes.Add("Training rows: $($trainRows.Count)")
$validationNotes.Add("Test rows: $($testRows.Count)")
$validationNotes.Add("Total rows: $($trainRows.Count + $testRows.Count)")

$trainIds = @($trainRows | ForEach-Object { [int]$_.id } | Sort-Object)
$testIds = @($testRows | ForEach-Object { [int]$_.id } | Sort-Object)
$validationNotes.Add("Training ID range: $($trainIds[0])..$($trainIds[-1]); unique IDs: $(@($trainIds | Select-Object -Unique).Count)")
$validationNotes.Add("Test ID range: $($testIds[0])..$($testIds[-1]); unique IDs: $(@($testIds | Select-Object -Unique).Count)")

$trainDuplicateCount = $trainRows.Count - @(
    $trainRows |
        ForEach-Object {
            [string]::Join("|", @(
                @($_.fa, $_.ma, $_.cs, $_.pb, $_.sn, $_.br, $_.cl, $_.i, $_.bg) |
                    ForEach-Object { $_.ToString("R", $Culture) }
            ))
        } |
        Select-Object -Unique
).Count
$testDuplicateCount = $testRows.Count - @(
    $testRows |
        ForEach-Object {
            [string]::Join("|", @(
                @($_.fa, $_.ma, $_.cs, $_.pb, $_.sn, $_.br, $_.cl, $_.i, $_.bg) |
                    ForEach-Object { $_.ToString("R", $Culture) }
            ))
        } |
        Select-Object -Unique
).Count
$validationNotes.Add("Exact duplicate rows excluding ID - training: $trainDuplicateCount; test: $testDuplicateCount")

$trainModelKeys = @(
    $trainRows | ForEach-Object {
        [string]::Join("|", @(
            @($_.sn, $_.br, $_.cl, $_.cs) |
                ForEach-Object { $_.ToString("R", $Culture) }
        ))
    }
)
$testModelKeys = @(
    $testRows | ForEach-Object {
        [string]::Join("|", @(
            @($_.sn, $_.br, $_.cl, $_.cs) |
                ForEach-Object { $_.ToString("R", $Culture) }
        ))
    }
)
$uniqueTrainModelKeys = @($trainModelKeys | Select-Object -Unique)
$uniqueTestModelKeys = @($testModelKeys | Select-Object -Unique)
$sharedModelKeys = @($uniqueTestModelKeys | Where-Object { $uniqueTrainModelKeys -contains $_ })
$validationNotes.Add("Duplicate Sn/Br/Cl/Cs feature rows - training: $($trainRows.Count - $uniqueTrainModelKeys.Count); test: $($testRows.Count - $uniqueTestModelKeys.Count)")
$validationNotes.Add("Unique Sn/Br/Cl/Cs feature combinations shared by train and test: $($sharedModelKeys.Count)")

$maxAError = ($trainRows + $testRows | ForEach-Object { [Math]::Abs(($_.fa + $_.ma + $_.cs) - 1.0) } | Measure-Object -Maximum).Maximum
$maxBError = ($trainRows + $testRows | ForEach-Object { [Math]::Abs(($_.pb + $_.sn) - 1.0) } | Measure-Object -Maximum).Maximum
$maxXError = ($trainRows + $testRows | ForEach-Object { [Math]::Abs(($_.br + $_.cl + $_.i) - 1.0) } | Measure-Object -Maximum).Maximum
$validationNotes.Add("Maximum composition closure error - A site: $($maxAError.ToString("G6", $Culture)); B site: $($maxBError.ToString("G6", $Culture)); X site: $($maxXError.ToString("G6", $Culture))")

$indices = [int[]](0..($trainRows.Count - 1))
$random = [System.Random]::new($Seed)
for ($i = $indices.Count - 1; $i -gt 0; $i--) {
    $j = $random.Next($i + 1)
    $temp = $indices[$i]
    $indices[$i] = $indices[$j]
    $indices[$j] = $temp
}

$validationIndices = [object[]]::new(5)
for ($fold = 0; $fold -lt 5; $fold++) {
    $validationIndices[$fold] = [System.Collections.Generic.List[int]]::new()
}
for ($position = 0; $position -lt $indices.Count; $position++) {
    $validationIndices[$position % 5].Add($indices[$position])
}

$allGram = New-Gram -X $train.X -Y $train.Y -Indices ([int[]](0..($trainRows.Count - 1)))
$trainGrams = [object[]]::new(5)
for ($fold = 0; $fold -lt 5; $fold++) {
    $validationGram = New-Gram -X $train.X -Y $train.Y -Indices $validationIndices[$fold].ToArray()
    $trainGrams[$fold] = Subtract-Gram -All $allGram -Part $validationGram
}

$stageCandidates = Get-StageCandidates
$allResults = [System.Collections.Generic.List[object]]::new()
$stageSelections = [System.Collections.Generic.List[object]]::new()

foreach ($stage in $stageCandidates.Keys) {
    Write-Host "Evaluating $stage ($($stageCandidates[$stage].Count) candidates)..."
    $stageResults = [System.Collections.Generic.List[object]]::new()
    foreach ($termIds in $stageCandidates[$stage]) {
        $result = Evaluate-Candidate -Stage $stage -TermIds $termIds -X $train.X -Y $train.Y -TrainGrams $trainGrams -ValidationIndices $validationIndices
        if ($null -ne $result) {
            $stageResults.Add($result)
            $allResults.Add($result)
        }
    }
    $bestRmse = ($stageResults | Measure-Object -Property CV_RMSE_Mean -Minimum).Minimum
    $threshold = $bestRmse * 1.05
    $selected = $stageResults |
        Where-Object { $_.CV_RMSE_Mean -le ($threshold + 1e-12) } |
        Sort-Object TermCount, CV_RMSE_Mean |
        Select-Object -First 1
    $stageSelections.Add([pscustomobject]@{
        Stage = $stage
        CandidateCount = $stageResults.Count
        Best_CV_RMSE = [double]$bestRmse
        FivePercentThreshold = [double]$threshold
        SelectedTermCount = $selected.TermCount
        SelectedTerms = $selected.Terms
        SelectedTermIds = $selected.TermIds
        Selected_CV_RMSE_Mean = $selected.CV_RMSE_Mean
        Selected_CV_RMSE_Std = $selected.CV_RMSE_Std
        Selected_CV_R2 = $selected.CV_R2
        CV_Qualified_Under_0_06 = ($selected.CV_RMSE_Mean -lt 0.06)
    })
}

$qualified = @($stageSelections | Where-Object { $_.CV_Qualified_Under_0_06 })
if ($qualified.Count -eq 0) {
    throw "No stage-selected expression met the CV RMSE < 0.06 eV threshold."
}
$finalSelection = $qualified |
    Sort-Object SelectedTermCount, Selected_CV_RMSE_Mean |
    Select-Object -First 1

$finalTermIds = [int[]]@($finalSelection.SelectedTermIds -split ";" | ForEach-Object { [int]$_ })
$finalCoefficients = Fit-FromGram -Gram $allGram -TermIds $finalTermIds
$trainMetrics = Get-Metrics -X $train.X -Y $train.Y -TermIds $finalTermIds -Coefficients $finalCoefficients
$testMetrics = Get-Metrics -X $test.X -Y $test.Y -TermIds $finalTermIds -Coefficients $finalCoefficients

$coefficientRows = [System.Collections.Generic.List[object]]::new()
$coefficientRows.Add([pscustomobject]@{ Term = "Intercept"; Coefficient = $finalCoefficients[0] })
for ($i = 0; $i -lt $finalTermIds.Count; $i++) {
    $coefficientRows.Add([pscustomobject]@{
        Term = $TermNames[$finalTermIds[$i]]
        Coefficient = $finalCoefficients[$i + 1]
    })
}

$allResults |
    Select-Object Stage, TermCount, Terms, CV_RMSE_Mean, CV_RMSE_Std, CV_R2, Fold_RMSE |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "all_candidate_cv_results.csv")
$stageSelections |
    Select-Object Stage, CandidateCount, Best_CV_RMSE, FivePercentThreshold, SelectedTermCount, SelectedTerms, Selected_CV_RMSE_Mean, Selected_CV_RMSE_Std, Selected_CV_R2, CV_Qualified_Under_0_06 |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "stage_selection_summary.csv")
$coefficientRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "final_coefficients.csv")

$symbolicTerms = @($finalTermIds | ForEach-Object { $TermNames[$_] })
$symbolicExpression = "Eg = a0"
for ($i = 0; $i -lt $symbolicTerms.Count; $i++) {
    $symbolicExpression += " + a$($i + 1)*$($symbolicTerms[$i])"
}
$numericExpression = Format-NumericExpression -TermIds $finalTermIds -Coefficients $finalCoefficients

$report = @(
    "Selected expression report",
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    "",
    "Selection policy:",
    "- OLS coefficients fitted only on the training set.",
    "- Five-fold CV seed: $Seed.",
    "- Within each stage: candidates within 5% of the best mean CV RMSE are accuracy-equivalent; the fewest-term expression wins, then lower CV RMSE.",
    "- Across stages: only stage selections with mean CV RMSE < 0.06 eV qualify; the fewest-term qualified expression wins, then lower CV RMSE.",
    "- The test set was evaluated only after the final structure was selected.",
    "",
    "Candidate-pool construction:",
    "- No saved LLM candidate outputs were present in the project, so this run used deterministic exhaustive legal structures rather than 30 repeated LLM calls.",
    "- M0 enumerated non-empty subsets of Sn/Br/Cl.",
    "- M1 enforced polynomial hierarchy: a squared term could appear only with its main effect.",
    "- M2 retained Sn/Br/Cl main effects and enumerated allowed squares/interactions.",
    "- M3 and M4 retained all four main effects and enumerated allowed second-order terms under each prompt's interaction and term-count limits.",
    "",
    "Data validation:",
    $validationNotes,
    "",
    "Final selected stage: $($finalSelection.Stage)",
    "Non-constant term count: $($finalSelection.SelectedTermCount)",
    "Mean five-fold CV RMSE: $($finalSelection.Selected_CV_RMSE_Mean.ToString('F8', $Culture)) eV",
    "Five-fold CV RMSE SD: $($finalSelection.Selected_CV_RMSE_Std.ToString('F8', $Culture)) eV",
    "Five-fold out-of-fold R2: $($finalSelection.Selected_CV_R2.ToString('F8', $Culture))",
    "",
    "Symbolic structure:",
    $symbolicExpression,
    "",
    "OLS fitted expression:",
    $numericExpression,
    "",
    "Post-selection metrics:",
    "Train RMSE: $($trainMetrics.RMSE.ToString('F8', $Culture)) eV",
    "Train MAE: $($trainMetrics.MAE.ToString('F8', $Culture)) eV",
    "Train R2: $($trainMetrics.R2.ToString('F8', $Culture))",
    "Test RMSE: $($testMetrics.RMSE.ToString('F8', $Culture)) eV",
    "Test MAE: $($testMetrics.MAE.ToString('F8', $Culture)) eV",
    "Test R2: $($testMetrics.R2.ToString('F8', $Culture))"
)
$report | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDir "selected_expression.txt")

Write-Host ""
Write-Host $numericExpression
Write-Host ("CV RMSE: {0:F8}; Test RMSE: {1:F8}; Test MAE: {2:F8}; Test R2: {3:F8}" -f $finalSelection.Selected_CV_RMSE_Mean, $testMetrics.RMSE, $testMetrics.MAE, $testMetrics.R2)
