param([switch]$InstructionsOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($InstructionsOnly) { Write-Host 'Optional per-PC folders: ZZZ ZenlessZoneZero_Data, PRAGMATA executable and PAKs, Cyberpunk archives, Wuthering Waves Client, Witcher 3 content, NTE Client. Cancel keeps existing settings.'; return }
$python = Join-Path $env:LOCALAPPDATA 'Programs\Proxy Transcript\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run Install.cmd first.' }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Game immersion toolkit - local game folders'
$form.Size = New-Object System.Drawing.Size(740, 625)
$form.MinimumSize = New-Object System.Drawing.Size(640, 430)
$form.StartPosition = 'CenterScreen'
$form.AutoScaleMode = 'Font'
$form.AutoScroll = $true
$table = New-Object System.Windows.Forms.TableLayoutPanel
$table.Dock = 'Top'; $table.AutoSize = $true; $table.Padding = New-Object System.Windows.Forms.Padding(16)
$table.ColumnCount = 3; $table.RowCount = 10
$table.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Absolute', 135))) | Out-Null
$table.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Percent', 100))) | Out-Null
$table.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Absolute', 90))) | Out-Null
$intro = New-Object System.Windows.Forms.Label
$intro.Text = "Optional: choose each installed game folder, or leave it blank for automatic detection. Game archives stay in place and are never uploaded.`r`nZZZ: ZenlessZoneZero_Data. NTE: folder containing Client. Other games: installation roots."
$intro.Dock = 'Fill'; $intro.AutoSize = $true
$table.Controls.Add($intro, 0, 0); $table.SetColumnSpan($intro, 3)
$table.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('AutoSize'))) | Out-Null
$fields = @{}
$oldLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    $existing = (& $python -m scripts.configure_game_paths --list | ConvertFrom-Json)
    # Windows PowerShell 5.1 emits a JSON array as one object; unroll it so
    # each game gets its own row (PowerShell 7 already enumerates it).
    $games = @(& $python -m scripts.configure_game_paths --catalog | ConvertFrom-Json | ForEach-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the supported game catalog.' }
    for ($index = 0; $index -lt $games.Count; $index++) {
        $game = $games[$index].id; $name = $games[$index].name; $row = $index + 1
        $table.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', 55))) | Out-Null
        $label = New-Object System.Windows.Forms.Label; $label.Text = $name; $label.AutoSize = $true; $label.Anchor = 'Left'
        $pathBox = New-Object System.Windows.Forms.TextBox; $pathBox.Dock = 'Fill'; $pathBox.Anchor = 'Left,Right'; $pathBox.Text = [string]$existing.$game
        $browse = New-Object System.Windows.Forms.Button; $browse.Text = 'Browse...'; $browse.Dock = 'Fill'; $browse.Tag = $pathBox
        $browse.Add_Click({
            $picker = New-Object System.Windows.Forms.FolderBrowserDialog
            $picker.Description = 'Select the installed game folder (not a ZIP or an extracted asset cache)'
            $picker.ShowNewFolderButton = $false
            if ($this.Tag.Text -and (Test-Path -LiteralPath $this.Tag.Text)) { $picker.SelectedPath = $this.Tag.Text }
            if ($picker.ShowDialog($form) -eq 'OK') { $this.Tag.Text = $picker.SelectedPath }
            $picker.Dispose()
        })
        $fields[$game] = $pathBox
        $table.Controls.Add($label, 0, $row); $table.Controls.Add($pathBox, 1, $row); $table.Controls.Add($browse, 2, $row)
    }
    $table.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', 55))) | Out-Null
    $buttons = New-Object System.Windows.Forms.FlowLayoutPanel; $buttons.Dock = 'Fill'; $buttons.FlowDirection = 'RightToLeft'
    $save = New-Object System.Windows.Forms.Button; $save.Text = 'Save folders'; $save.AutoSize = $true
    $cancel = New-Object System.Windows.Forms.Button; $cancel.Text = 'Skip / Cancel'; $cancel.AutoSize = $true; $cancel.DialogResult = 'Cancel'
    $save.Add_Click({
        foreach ($game in $fields.Keys) {
            $path = $fields[$game].Text.Trim()
            if (-not $path) { continue }
            $result = & $python -m scripts.configure_game_paths --game $game --path $path --check 2>&1
            if ($LASTEXITCODE -ne 0) { [System.Windows.Forms.MessageBox]::Show(($result -join "`r`n"), 'Invalid game folder', 'OK', 'Warning') | Out-Null; return }
        }
        foreach ($game in $fields.Keys) {
            $path = $fields[$game].Text.Trim()
            if (-not $path) { continue }
            & $python -m scripts.configure_game_paths --game $game --path $path
            if ($LASTEXITCODE -ne 0) { [System.Windows.Forms.MessageBox]::Show('Could not save the folder. Existing settings remain intact.', 'Save failed') | Out-Null; return }
        }
        [System.Windows.Forms.MessageBox]::Show('Folders saved only on this PC. Open Setup in the toolkit to prepare missing tools and refresh game data. Existing capture preferences and credentials were preserved.', 'Game folders saved') | Out-Null
        $form.DialogResult = 'OK'; $form.Close()
    })
    $buttons.Controls.Add($save); $buttons.Controls.Add($cancel)
    $table.Controls.Add($buttons, 0, ($games.Count + 1)); $table.SetColumnSpan($buttons, 3)
    $form.Controls.Add($table); $form.CancelButton = $cancel
    $form.ShowDialog() | Out-Null
} finally { Set-Location -LiteralPath $oldLocation.Path; $form.Dispose() }
