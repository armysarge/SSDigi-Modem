param (
    [string]$platform = "windows",
    [string]$version = "0.1.0",
    [switch]$noBinaries = $false
)

Write-Host "Running SS Ham Modem packaging script with:"
Write-Host "  Platform: $platform"
Write-Host "  Version: $version"
Write-Host "  No Binaries: $noBinaries"

# Build the package
$packageArgs = @("tools\package.py", "--platform", $platform, "--version", $version)
if ($noBinaries) {
    $packageArgs += "--no-binaries"
}

# Run the build
Write-Host "Running PyInstaller build..."
& python $packageArgs

# Check if PyInstaller succeeded
if ($LASTEXITCODE -eq 0) {
    Write-Host "PyInstaller build completed successfully"

    # Create the ZIP archive directly
    $distDir = "dist"
    $appName = "SS_Ham_Modem_${version}"
    $appDir = Join-Path $distDir $appName

    if (Test-Path $appDir) {
        Write-Host "Found application directory: $appDir"

        # Create ZIP archive
        $zipName = "${appName}-${platform}.zip"
        $zipPath = Join-Path $distDir $zipName

        Write-Host "Creating ZIP package: $zipPath"

        if (Test-Path $zipPath) {
            Write-Host "Removing existing ZIP package"
            Remove-Item $zipPath -Force
        }

        # Use .NET's built-in ZIP functionality
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($appDir, $zipPath)

        Write-Host "Package created successfully: $zipPath"
        exit 0
    } else {
        Write-Host "ERROR: Application directory not found: $appDir"
        # List all folders in the dist directory
        Write-Host "Available directories in $distDir"
        Get-ChildItem $distDir -Directory | ForEach-Object { Write-Host "  - $($_.Name)" }
        exit 1
    }
} else {
    Write-Host "ERROR: PyInstaller build failed"
    exit $LASTEXITCODE
}
