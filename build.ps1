$ErrorActionPreference = "Stop"

$root     = $PSScriptRoot
$frontend = Join-Path $root "abandono-app"
$server   = Join-Path $root "abandono-server"
$static   = Join-Path $server "src\main\resources\static"

Write-Host "`n[1/4] Build do React (npm run build)..." -ForegroundColor Cyan
Push-Location $frontend
npm run build
Pop-Location

Write-Host "`n[2/4] Limpando pasta static do Spring Boot..." -ForegroundColor Cyan
Get-ChildItem $static -Exclude ".gitkeep" | Remove-Item -Recurse -Force

Write-Host "`n[3/4] Copiando dist/ -> static/..." -ForegroundColor Cyan
$dist = Join-Path $frontend "dist"
Copy-Item -Path "$dist\*" -Destination $static -Recurse -Force

Write-Host "`n[4/4] Empacotando .jar (mvnw package)..." -ForegroundColor Cyan
Push-Location $server
.\mvnw.cmd package -DskipTests
Pop-Location

$jar = Get-ChildItem (Join-Path $server "target") -Filter "abandono-server-*.jar" | Select-Object -First 1
Write-Host "`nBuild concluido!" -ForegroundColor Green
Write-Host "Para iniciar o servidor:" -ForegroundColor Yellow
Write-Host "  java -jar `"$($jar.FullName)`"" -ForegroundColor White
Write-Host "`nColegas acessam via: http://<seu-IP>:8080" -ForegroundColor Yellow
