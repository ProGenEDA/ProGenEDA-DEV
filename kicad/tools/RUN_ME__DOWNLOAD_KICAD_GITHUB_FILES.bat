@echo off
setlocal EnableExtensions
title KiCad GitHub Files Downloader

echo.
echo ============================================================
echo   KiCad GitHub Files Downloader
echo ============================================================
echo.
echo This downloads KiCad GitHub repo archives + inventories into
echo a new folder next to this BAT file.
echo.
echo Token is optional but recommended. It is NOT saved permanently.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$batDir = Split-Path -Parent '%~f0';" ^
  "$stamp = Get-Date -Format 'yyyyMMdd_HHmmss';" ^
  "$out = Join-Path $batDir ('KiCad_GitHub_Downloads_' + $stamp);" ^
  "New-Item -ItemType Directory -Force -Path $out | Out-Null;" ^
  "$log = Join-Path $out 'download_log.txt';" ^
  "function Log($m){ $line = '[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $m; Write-Host $line; Add-Content -Path $log -Value $line };" ^
  "Log 'Starting KiCad GitHub downloader';" ^
  "Log ('Output folder: ' + $out);" ^
  "$token = Read-Host 'Paste GitHub token here, or press Enter to continue without token';" ^
  "$headers = @{ 'Accept'='application/vnd.github+json'; 'User-Agent'='progen-kicad-github-downloader' };" ^
  "if($token.Trim().Length -gt 0){ $headers['Authorization'] = 'Bearer ' + $token.Trim(); Log 'Authenticated API mode enabled.' } else { Log 'No token; public unauthenticated API mode enabled.' };" ^
  "$needed = @('kicad-source-mirror','kicad-symbols','kicad-templates','kicad-doc','kicad-footprints','kicad-packages3D','kicad-library-utils','kicad-docker');" ^
  "$exts = @('.kicad_pro','.kicad_sch','.kicad_sym','.kicad_pcb','.kicad_mod','.net','.cir','.spice','.lib','.sub','.mod','.sch','.pro');" ^
  "$exact = @('sym-lib-table','fp-lib-table');" ^
  "$allRepos = @();" ^
  "for($page=1; $page -le 10; $page++){ $url='https://api.github.com/orgs/KiCad/repos?per_page=100&page=' + $page; Log ('Fetching repo list page ' + $page); $r = Invoke-RestMethod -Headers $headers -Uri $url; if($r.Count -eq 0){ break }; $allRepos += $r };" ^
  "$allRepos | Select-Object name,full_name,html_url,default_branch,archived,disabled,description | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $out 'kicad_org_repositories.json');" ^
  "$allRepos | Select-Object name,full_name,html_url,default_branch,archived,disabled,description | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out 'kicad_org_repositories.csv');" ^
  "Log ('Found ' + $allRepos.Count + ' KiCad org repositories.');" ^
  "$mode = Read-Host 'Type A to download ALL KiCad org repo archives, or press Enter for recommended generator repos only';" ^
  "if($mode.Trim().ToUpper() -eq 'A'){ $repos = $allRepos } else { $repos = @(); foreach($n in $needed){ $match = $allRepos | Where-Object { $_.name -eq $n } | Select-Object -First 1; if($match){ $repos += $match } else { $repos += [pscustomobject]@{ name=$n; full_name=('KiCad/' + $n); default_branch='master'; html_url=('https://github.com/KiCad/' + $n) } } } };" ^
  "$archiveDir = Join-Path $out 'repo_archives_zip'; New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null;" ^
  "$inventoryDir = Join-Path $out 'file_inventories'; New-Item -ItemType Directory -Force -Path $inventoryDir | Out-Null;" ^
  "$downloaded = @();" ^
  "foreach($repo in $repos){ try { $name=$repo.name; $branch=$repo.default_branch; if([string]::IsNullOrWhiteSpace($branch)){ $branch='master' }; Log ('Processing KiCad/' + $name + ' @ ' + $branch); $treeUrl='https://api.github.com/repos/KiCad/' + $name + '/git/trees/' + $branch + '?recursive=1'; try { $tree = Invoke-RestMethod -Headers $headers -Uri $treeUrl; $matches = @(); foreach($item in $tree.tree){ if($item.type -eq 'blob'){ $leaf = Split-Path $item.path -Leaf; $ext = [System.IO.Path]::GetExtension($item.path); if(($exts -contains $ext) -or ($exact -contains $leaf)){ $matches += [pscustomobject]@{ repo=$name; path=$item.path; size=$item.size; sha=$item.sha; url=$item.url } } } }; $matches | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $inventoryDir ($name + '_kicad_file_inventory.csv')); $matches | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $inventoryDir ($name + '_kicad_file_inventory.json')); Log ('  KiCad-file inventory matches: ' + $matches.Count); } catch { Log ('  Inventory failed for ' + $name + ': ' + $_.Exception.Message) }; $zipUrl='https://api.github.com/repos/KiCad/' + $name + '/zipball/' + $branch; $zipOut=Join-Path $archiveDir ($name + '_' + $branch + '.zip'); Log ('  Downloading archive: ' + $name); Invoke-WebRequest -Headers $headers -Uri $zipUrl -OutFile $zipOut; $downloaded += [pscustomobject]@{ repo=$name; branch=$branch; zip=$zipOut; bytes=(Get-Item $zipOut).Length }; Log ('  Saved ' + $zipOut); } catch { Log ('ERROR processing ' + $repo.name + ': ' + $_.Exception.Message) } };" ^
  "$downloaded | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $out 'downloaded_archives.csv');" ^
  "$readme = @(); $readme += '# KiCad GitHub Downloader Output'; $readme += ''; $readme += ('Created: ' + (Get-Date)); $readme += ''; $readme += 'Folders:'; $readme += '- repo_archives_zip: downloaded KiCad GitHub repo archives'; $readme += '- file_inventories: CSV/JSON list of KiCad-related files found in each repo'; $readme += ''; $readme += 'Important files:'; $readme += '- kicad_org_repositories.csv'; $readme += '- downloaded_archives.csv'; $readme += '- download_log.txt'; $readme += ''; $readme += 'Use these archives as source material for the KiCad generator.'; $readme -join [Environment]::NewLine | Set-Content -Encoding UTF8 (Join-Path $out 'README_AFTER_DOWNLOAD.md');" ^
  "Log 'DONE.';" ^
  "Log ('Open output folder: ' + $out);" ^
  "Start-Process explorer.exe $out;"

echo.
echo Finished. Check the created KiCad_GitHub_Downloads_* folder.
echo.
pause
