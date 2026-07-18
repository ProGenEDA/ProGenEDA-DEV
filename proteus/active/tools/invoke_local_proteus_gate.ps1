[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,
    [string]$GateCopy,
    [string]$ProteusExe = "C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\PDS.EXE",
    [ValidateRange(12, 120)]
    [int]$WaitSeconds = 12,
    [string]$ScreenshotDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProteusExe -PathType Leaf)) {
    throw "Proteus executable was not found: $ProteusExe"
}

$existing = @(Get-Process -Name PDS, ISIS -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
    throw "Refusing to run the loader gate while Proteus is already open: $($existing.Id -join ', ')."
}

$source = (Resolve-Path -LiteralPath $Project).Path
if ([string]::IsNullOrWhiteSpace($GateCopy)) {
    $GateCopy = Join-Path (Split-Path -Parent $source) ("{0}_GATE{1}" -f [IO.Path]::GetFileNameWithoutExtension($source), [IO.Path]::GetExtension($source))
}
$gate = [IO.Path]::GetFullPath($GateCopy)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $gate) | Out-Null
Copy-Item -LiteralPath $source -Destination $gate -Force

$screenshotRoot = $null
if (-not [string]::IsNullOrWhiteSpace($ScreenshotDirectory)) {
    $screenshotRoot = [IO.Path]::GetFullPath($ScreenshotDirectory)
    New-Item -ItemType Directory -Force -Path $screenshotRoot | Out-Null
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName Microsoft.VisualBasic
}

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class ProgenProteusWindowAudit
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll")]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    private static string Text(IntPtr hWnd)
    {
        var text = new StringBuilder(2048);
        GetWindowText(hWnd, text, text.Capacity);
        return text.ToString();
    }

    private static string Class(IntPtr hWnd)
    {
        var text = new StringBuilder(256);
        GetClassName(hWnd, text, text.Capacity);
        return text.ToString();
    }

    public static string[] Snapshot(int processId)
    {
        var rows = new List<string>();
        EnumWindows((hWnd, lParam) =>
        {
            uint owner;
            GetWindowThreadProcessId(hWnd, out owner);
            if (owner != (uint)processId)
            {
                return true;
            }

            rows.Add("TOP|" + Class(hWnd) + "|" + Text(hWnd));
            EnumChildWindows(hWnd, (child, childParam) =>
            {
                rows.Add("CHILD|" + Class(child) + "|" + Text(child));
                return true;
            }, IntPtr.Zero);
            return true;
        }, IntPtr.Zero);
        return rows.ToArray();
    }
}
'@

$beforeHash = (Get-FileHash -LiteralPath $gate -Algorithm SHA256).Hash
$projectStem = [IO.Path]::GetFileNameWithoutExtension($gate)
$errorPattern = "(?i)Bad Object Record|Fatal Error|LXLCORE|not in library|used but not in library"

function Save-ProgenScreenshot([Diagnostics.Process]$Process, [string]$Phase) {
    if ($null -eq $screenshotRoot) {
        return $null
    }

    try {
        [Microsoft.VisualBasic.Interaction]::AppActivate($Process.Id) | Out-Null
    }
    catch {
        # The window audit remains authoritative when foreground activation is unavailable.
    }
    Start-Sleep -Milliseconds 750

    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $path = Join-Path $screenshotRoot ("{0}_{1}.png" -f $projectStem, $Phase)
    try {
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
        $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
    return $path
}

function Invoke-ColdOpen([string]$Phase) {
    $process = if ($null -eq $screenshotRoot) {
        Start-Process -FilePath $ProteusExe -ArgumentList @($gate) -WindowStyle Hidden -PassThru
    }
    else {
        Start-Process -FilePath $ProteusExe -ArgumentList @($gate) -WindowStyle Normal -PassThru
    }
    try {
        Start-Sleep -Seconds $WaitSeconds
        $alive = -not $process.HasExited
        $windows = if ($alive) {
            [ProgenProteusWindowAudit]::Snapshot($process.Id)
        }
        else {
            @("PROCESS_EXITED")
        }
        $windowText = $windows -join "`n"
        $screenshot = if ($alive) { Save-ProgenScreenshot $process $Phase } else { $null }
        return [PSCustomObject]@{
            phase = $Phase
            process_id = $process.Id
            alive_after_wait = $alive
            schematic_title_seen = $windowText -match [regex]::Escape($projectStem)
            error_dialog_text_seen = $windowText -match $errorPattern
            screenshot = $screenshot
            matching_windows = @($windows | Where-Object { $_ -match [regex]::Escape($projectStem) })
            windows = $windows
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Start-Sleep -Seconds 2
        }
    }
}

$first = Invoke-ColdOpen "cold_open_1"
$second = Invoke-ColdOpen "cold_open_2"
$afterHash = (Get-FileHash -LiteralPath $gate -Algorithm SHA256).Hash
$passed = (
    $first.alive_after_wait -and
    $second.alive_after_wait -and
    $first.schematic_title_seen -and
    $second.schematic_title_seen -and
    -not $first.error_dialog_text_seen -and
    -not $second.error_dialog_text_seen -and
    $beforeHash -eq $afterHash
)

$result = [PSCustomObject]@{
    stage = "local_proteus_open_save_cold_reopen_gate"
    source_project = $source
    gate_copy = $gate
    wait_seconds = $WaitSeconds
    passed = $passed
    gate_copy_sha256_before = $beforeHash
    gate_copy_sha256_after = $afterHash
    gate_copy_hash_unchanged = $beforeHash -eq $afterHash
    first = $first
    second = $second
}

$result | ConvertTo-Json -Depth 6
if (-not $passed) {
    exit 2
}
