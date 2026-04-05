$ErrorActionPreference = "Stop"
$destDir = "c:\Users\Lenovo\Desktop\mysql"
$zipPath = "$destDir\mariadb.zip"
$extractPath = "$destDir\temp_extract"
# Use a reliable mirror or archive link
$url = "https://archive.mariadb.org/mariadb-10.6.16/winx64-packages/mariadb-10.6.16-winx64.zip"

Write-Host "Setting up Database Environment (MariaDB)..."

if (Test-Path "$destDir\bin\mysqld.exe") {
    Write-Host "Database directory already exists. Skipping download."
    exit 0
}

New-Item -ItemType Directory -Force -Path $destDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractPath | Out-Null

try {
    Write-Host "Downloading MariaDB from $url..."
    # Timeout increased for large file
    Invoke-WebRequest -Uri $url -OutFile $zipPath -TimeoutSec 600
}
catch {
    Write-Host "Download failed. Please check internet connection or URL."
    exit 1
}

Write-Host "Extracting MariaDB..."
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

# Move files from subfolder to $destDir
$subFolder = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
Move-Item -Path "$($subFolder.FullName)\*" -Destination $destDir -Force

# Cleanup
Remove-Item $extractPath -Recurse -Force
Remove-Item $zipPath -Force

# Create minimal my.ini in bin
$myIni = @"
[mysqld]
datadir=C:/Users/Lenovo/Desktop/mysql/data
port=3306
bind-address=127.0.0.1
skip-networking=0
default_storage_engine=InnoDB
innodb_file_per_table=1
performance_schema=0
"@
Set-Content -Path "$destDir\bin\my.ini" -Value $myIni

# Initialize Database
Write-Host "Initializing Database Data..."
$installDb = "$destDir\bin\mysql_install_db.exe"
$datadir = "$destDir\data"
& $installDb --datadir=$datadir

# Start Temporary Server to Import Schema
Write-Host "Starting Database for Import..."
$mysqld = "$destDir\bin\mysqld.exe"
$proc = Start-Process -FilePath $mysqld -ArgumentList "--defaults-file=$destDir\bin\my.ini", "--console" -PassThru -NoNewWindow
Start-Sleep -Seconds 10

# Import Schema
$schema = "c:\Users\Lenovo\Desktop\HealthPro\schema.sql"
$mysql = "$destDir\bin\mysql.exe"
if (Test-Path $schema) {
    Write-Host "Importing Schema from $schema..."
    # Default root has no password
    Get-Content $schema | & $mysql -u root
    Write-Host "Schema Imported."
}
else {
    Write-Host "Schema file not found at $schema"
}

# Stop Server
Stop-Process -Id $proc.Id -Force
Write-Host "Database Setup Complete."
