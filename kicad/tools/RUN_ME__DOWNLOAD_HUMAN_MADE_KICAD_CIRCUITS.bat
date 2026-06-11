@echo off
setlocal EnableExtensions
title KiCad Human-Made Circuit Downloader

echo.
echo ============================================================
echo   KiCad Human-Made Circuit / Project Downloader
echo ============================================================
echo.
echo This is NOT the library/source archive downloader.
echo It downloads human-made KiCad example/test/demo circuit projects
echo from KiCad GitHub repos so they can be studied and compared.
echo.
echo Output is saved next to this BAT file in:
echo   KiCad_Human_Circuit_Downloads_YYYYMMDD_HHMMSS
echo.
echo GitHub token is optional but recommended.
echo The token is used only in this window and is NOT saved.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$batDir = Split-Path -Parent '%~f0';" ^
  "$stamp = Get-Date -Format 'yyyyMMdd_HHmmss';" ^
  "$out = Join-Path $batDir ('KiCad_Human_Circuit_Downloads_' + $stamp);" ^
  "New-Item -ItemType Directory -Force -Path $out | Out-Null;" ^
  "$log = Join-Path $out 'download_log.txt';" ^
  "function Log($m){ $line='['+(Get-Date -Format 'HH:mm:ss')+'] '+$m; Write-Host $line; Add-Content -Path $log -Value $line };" ^
  "function SafePath($p){ return ($p -replace '[<>:\"|?*]', '_') };" ^
  "Log 'Starting human-made KiCad circuit downloader';" ^
  "Log ('Output folder: ' + $out);" ^
  "$token = Read-Host 'Paste GitHub token, or press Enter without token';" ^
  "$headers = @{ 'Accept'='application/vnd.github+json'; 'User-Agent'='progen-kicad-human-circuit-downloader' };" ^
  "if($token.Trim().Length -gt 0){ $headers['Authorization']='Bearer '+$token.Trim(); Log 'Authenticated GitHub API mode enabled.' } else { Log 'Public unauthenticated mode enabled.' };" ^
  "$repos = @('kicad-source-mirror','kicad-templates','kicad-doc','kicad-symbols','kicad-footprints','kicad-packages3D','kicad-library-utils','kicad-docker');" ^
  "$seedExts = @('.kicad_pro','.kicad_sch','.kicad_pcb','.pro','.sch');" ^
  "$companionExts = @('.kicad_pro','.kicad_sch','.kicad_pcb','.pro','.sch','.net','.cir','.spice','.lib','.sub','.mod','.txt','.md');" ^
  "$exactNames = @('sym-lib-table','fp-lib-table','README','README.md','readme.md');" ^
  "$excludePathRegex = '(?i)(^|/)(symbols|footprints|packages3d|3dmodels|doc/images|resources/bitmaps|thirdparty|qa/data/pcbnew/plugins/legacy_demos)(/|$)';" ^
  "$circuitHintRegex = '(?i)(qa/data|test|tests|spice|netlist|simulation|sim|demo|demos|template|templates|example|examples|schematic|eeschema|project)';" ^
  "$allInventory = @(); $downloaded = @();" ^
  "foreach($repo in $repos){" ^
  "  try {" ^
  "    Log ('Scanning KiCad/' + $repo);" ^
  "    $meta = Invoke-RestMethod -Headers $headers -Uri ('https://api.github.com/repos/KiCad/' + $repo);" ^
  "    $branch = $meta.default_branch; if([string]::IsNullOrWhiteSpace($branch)){ $branch='master' };" ^
  "    $treeUrl = 'https://api.github.com/repos/KiCad/' + $repo + '/git/trees/' + $branch + '?recursive=1';" ^
  "    $tree = Invoke-RestMethod -Headers $headers -Uri $treeUrl;" ^
  "    $blobs = @($tree.tree | Where-Object { $_.type -eq 'blob' });" ^
  "    $seedDirs = @{};" ^
  "    foreach($item in $blobs){" ^
  "      $path = $item.path; $leaf = Split-Path $path -Leaf; $ext = [IO.Path]::GetExtension($path);" ^
  "      if(($seedExts -contains $ext) -and ($path -match $circuitHintRegex) -and -not ($path -match $excludePathRegex)){" ^
  "        $dir = Split-Path $path -Parent; if($null -eq $dir){ $dir='' }; $seedDirs[$dir] = $true;" ^
  "      }" ^
  "    }" ^
  "    Log ('  Circuit/project directories found: ' + $seedDirs.Count);" ^
  "    $repoMatches = @();" ^
  "    foreach($item in $blobs){" ^
  "      $path = $item.path; $dir = Split-Path $path -Parent; if($null -eq $dir){ $dir='' };" ^
  "      if(-not $seedDirs.ContainsKey($dir)){ continue };" ^
  "      $leaf = Split-Path $path -Leaf; $ext = [IO.Path]::GetExtension($path);" ^
  "      if(($companionExts -contains $ext) -or ($exactNames -contains $leaf)){" ^
  "        $repoMatches += [pscustomobject]@{ repo=$repo; branch=$branch; path=$path; size=$item.size; sha=$item.sha; download_url=('https://raw.githubusercontent.com/KiCad/' + $repo + '/' + $branch + '/' + $path) };" ^
  "      }" ^
  "    }" ^
  "    $invDir = Join-Path $out 'inventories'; New-Item -ItemType Directory -Force -Path $invDir | Out-Null;" ^
  "    $repoMatches | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $invDir ($repo + '_human_circuit_files.csv'));" ^
  "    $repoMatches | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $invDir ($repo + '_human_circuit_files.json'));" ^
  "    $allInventory += $repoMatches;" ^
  "    Log ('  Files selected for download: ' + $repoMatches.Count);" ^
  "    foreach($f in $repoMatches){" ^
  "      try {" ^
  "        $dest = Join-Path $out ('circuits/' + $repo + '/' + $f.path);" ^
  "        $destDir = Split-Path $dest -Parent; New-Item -ItemType Directory -Force -Path $destDir | Out-Null;" ^
  "        Invoke-WebRequest -Headers $headers -Uri $f.download_url -OutFile $dest;" ^
  "        $downloaded += [pscustomobject]@{ repo=$repo; path=$f.path; local_path=$dest; bytes=(Get-Item $dest).Length };" ^
  "      } catch { Log ('    Download failed: ' + $f.path + ' :: ' + $_.Exception.Message) }" ^
  "    }" ^
  "  } catch { Log ('ERROR scanning KiCad/' + $repo + ': ' + $_.Exception.Message) }" ^
  "}" ^
  "$allInventory | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out 'ALL_SELECTED_HUMAN_CIRCUIT_FILES.csv');" ^
  "$allInventory | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $out 'ALL_SELECTED_HUMAN_CIRCUIT_FILES.json');" ^
  "$downloaded | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out 'DOWNLOADED_FILES.csv');" ^
  "$readme = @();" ^
  "$readme += '# KiCad Human-Made Circuit Downloads';" ^
  "$readme += '';" ^
  "$readme += 'This folder contains KiCad human-made example/test/demo/template project files downloaded from KiCad GitHub repositories.';" ^
  "$readme += '';" ^
  "$readme += 'Important folders:';" ^
  "$readme += '- circuits/: downloaded files preserving repo paths';" ^
  "$readme += '- inventories/: per-repo CSV/JSON inventories';" ^
  "$readme += '';" ^
  "$readme += 'Important files:';" ^
  "$readme += '- ALL_SELECTED_HUMAN_CIRCUIT_FILES.csv';" ^
  "$readme += '- DOWNLOADED_FILES.csv';" ^
  "$readme += '- download_log.txt';" ^
  "$readme += '';" ^
  "$readme += 'Give this whole folder or ZIP to ChatGPT for analysis.';" ^
  "$readme -join [Environment]::NewLine | Set-Content -Encoding UTF8 (Join-Path $out 'README_AFTER_DOWNLOAD.md');" ^
  "Log ('Total selected files: ' + $allInventory.Count);" ^
  "Log ('Total downloaded files: ' + $downloaded.Count);" ^
  "Log 'DONE. Opening output folder.';" ^
  "Start-Process explorer.exe $out;"

echo.
echo Done. Check the created KiCad_Human_Circuit_Downloads_* folder.
echo If something failed, open download_log.txt inside that folder.
echo.
pause
