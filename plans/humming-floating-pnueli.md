# Proposal: Verify browser output from Claude Code

## Context
`Start-Process` returns PID but that only proves the process launched, not that the URL actually loaded in the browser. Claude Code needs a way to visually confirm browser-side results.

## Recommended approach: Screenshot capture + Read tool

PowerShell screenshot capture is already confirmed working on this environment.

### Flow
1. Open URLs via `Start-Process`
2. `Start-Sleep -Seconds 3` (wait for pages to load)
3. Capture screenshot via PowerShell (`System.Drawing` + `System.Windows.Forms`)
4. Save to `$env:TEMP\screenshot.png`
5. Use Claude Code's `Read` tool on the PNG — it renders images natively

### Helper script to add
`open_urls.ps1` に verification function を追加:

```powershell
function Capture-Screen($path) {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($s.Width, $s.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size)
    $bmp.Save($path)
    $g.Dispose(); $bmp.Dispose()
}
```

### Usage in verification
After opening URLs, Claude Code runs:
```
powershell -ExecutionPolicy Bypass -Command "Start-Sleep 3; <screenshot code>; Write-Host 'saved'"
```
Then: `Read $env:TEMP\screenshot.png` to visually confirm the browser state.

## Alternatives considered (less practical)
- **Window title check**: `Get-Process Arc | Select MainWindowTitle` — Arc didn't expose titles in testing
- **Chrome DevTools Protocol**: Requires `--remote-debugging-port` flag at Arc launch — intrusive
- **curl localhost**: Same CDP dependency

## File to modify
- `C:\Users\0000250059\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\startup\open_urls.ps1` — add optional `Capture-Screen` function for debug use

## Verification
1. Run `open_urls.ps1`
2. Wait 3 seconds
3. Take screenshot
4. `Read` the screenshot PNG to visually confirm pages opened in Arc
