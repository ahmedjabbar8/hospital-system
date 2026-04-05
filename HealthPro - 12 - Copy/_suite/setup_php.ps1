$ErrorActionPreference = "Stop"
$destDir = "c:\Users\Lenovo\Desktop\php"
$zipPath = "$destDir\php.zip"
$url = "https://windows.php.net/downloads/releases/php-8.2.27-Win32-vs16-x64.zip"

Write-Host "Setting up PHP Environment..."

if (Test-Path $destDir) {
    Write-Host "PHP directory already exists. Skipping download."
    exit 0
}

New-Item -ItemType Directory -Force -Path $destDir | Out-Null

# Try downloading 8.2.27, if fails try 8.2.30 or fallback
try {
    Write-Host "Downloading PHP from $url..."
    Invoke-WebRequest -Uri $url -OutFile $zipPath
} catch {
    Write-Host "Version 8.2.27 not found, trying 8.2.30..."
    $url = "https://windows.php.net/downloads/releases/php-8.2.30-Win32-vs16-x64.zip"
    Invoke-WebRequest -Uri $url -OutFile $zipPath
}

Write-Host "Extracting PHP..."
Expand-Archive -Path $zipPath -DestinationPath $destDir -Force
Remove-Item $zipPath

# Setup php.ini
$iniProduction = "$destDir\php.ini-production"
$iniFile = "$destDir\php.ini"
if (Test-Path $iniProduction) {
    Copy-Item $iniProduction $iniFile
    
    $content = Get-Content $iniFile
    $content = $content -replace ';extension_dir = "ext"', 'extension_dir = "ext"'
    $content = $content -replace ';extension=mbstring', 'extension=mbstring'
    $content = $content -replace ';extension=mysqli', 'extension=mysqli'
    $content = $content -replace ';extension=openssl', 'extension=openssl'
    $content = $content -replace ';extension=curl', 'extension=curl'
    
    Set-Content -Path $iniFile -Value $content
    Write-Host "Configured php.ini with mysqli, mbstring, curl."
}

Write-Host "PHP Setup Complete."
Write-Host "You can now run the server_dashboard.py or HealthProServer.exe."
