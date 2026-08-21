[CmdletBinding()]
param(
    [string]$Source = "gdrive:3- Projects & Learning/private beach/library",
    [Parameter(Mandatory = $true)]
    [string]$Destination,
    [ValidateRange(1, 64)]
    [int]$Transfers = 16,
    [ValidateRange(1, 128)]
    [int]$Checkers = 32,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
    throw "Không tìm thấy rclone. Cài từ https://rclone.org/downloads/ rồi mở PowerShell mới."
}
if ($Destination -match "YOUR_|TEN_BUCKET") {
    throw "Hãy thay Destination bằng remote và bucket thật, ví dụ r2:yoru-manga/library"
}

$arguments = @(
    "copy",
    $Source,
    $Destination,
    "--fast-list",
    "--transfers", $Transfers,
    "--checkers", $Checkers,
    "--retries", "8",
    "--low-level-retries", "20",
    "--stats", "5s",
    "--stats-one-line",
    "--progress",
    "--exclude", "Thumbs.db",
    "--exclude", ".DS_Store"
)

if (-not $Execute) {
    $arguments += "--dry-run"
    Write-Host "DRY RUN: chưa upload file nào."
    Write-Host "Nếu danh sách đúng, chạy lại cùng lệnh với -Execute."
} else {
    Write-Host "Đang copy từ Google Drive API sang Cloudflare R2..."
    Write-Host "rclone copy không xóa file đang có trên R2."
}

& rclone @arguments
if ($LASTEXITCODE -ne 0) {
    throw "rclone kết thúc với mã lỗi $LASTEXITCODE"
}

if ($Execute) {
    Write-Host "Upload hoàn tất. Chạy scripts/generate_library.py rồi commit library-data.js."
}
