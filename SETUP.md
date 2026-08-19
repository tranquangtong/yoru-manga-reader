# Thiết lập GitHub Pages và Cloudflare R2

## 1. Tạo Cloudflare R2 bucket

1. Mở Cloudflare Dashboard > **R2 Object Storage** > **Create bucket**.
2. Đặt tên, ví dụ `yoru-manga`.
3. Vào **Manage R2 API Tokens** và tạo token **Object Read & Write** chỉ cho
   bucket này. Lưu `Access Key ID` và `Secret Access Key`; secret chỉ hiện một lần.
4. Ghi lại Cloudflare **Account ID**.

Không đặt key/secret trong `config.js`, Git hoặc file nằm trong Google Drive.

## 2. Cài và cấu hình rclone

Tải rclone tại https://rclone.org/downloads/ và đảm bảo lệnh sau chạy được:

```powershell
rclone version
rclone config
```

Trong `rclone config`, tạo hai remote:

### Remote Google Drive: `gdrive`

- Storage: `Google Drive`.
- Scope: `Read-only access` là đủ.
- Đăng nhập đúng Google account chứa `private beach`.

Kiểm tra:

```powershell
rclone lsf "gdrive:3- Projects & Learning/private beach/library" `
  --max-depth 1 --dirs-only
```

### Remote Cloudflare R2: `r2`

- Storage: `Amazon S3 Compliant Storage Providers`.
- Provider: `Cloudflare`.
- Access key/secret: token R2 vừa tạo.
- Endpoint: `https://ACCOUNT_ID.r2.cloudflarestorage.com`.
- ACL: `private` hoặc để trống theo hướng dẫn wizard.

Kiểm tra:

```powershell
rclone lsd r2:
```

## 3. Upload nhanh từ Drive sang R2

Chạy dry-run trước; lệnh này chỉ liệt kê, chưa upload:

```powershell
.\scripts\upload-library-to-r2.ps1 `
  -Destination "r2:yoru-manga/library"
```

Nếu source/destination đúng, chạy thật:

```powershell
.\scripts\upload-library-to-r2.ps1 `
  -Destination "r2:yoru-manga/library" `
  -Execute
```

Mặc định script dùng 16 lượt transfer và 32 checker. Dữ liệu đi từ Google Drive
API qua máy này rồi lên R2, nhưng không đi qua Google DriveFS mount/Explorer; cách
này phù hợp hơn với thư viện có hàng nghìn ảnh nhỏ. Có thể chạy lại cùng lệnh để
tiếp tục sau khi gián đoạn.

## 4. Cho browser đọc ảnh R2

Trong bucket > **Settings**:

- Dùng **Public Development URL** (`r2.dev`) để thử nhanh; hoặc
- Kết nối **Custom Domain** để dùng ổn định lâu dài.

Sau đó sửa `config.js`, ví dụ:

```js
assetBaseUrl: "https://pub-xxxxxxxx.r2.dev/library/",
```

Bucket public nghĩa là người có URL ảnh có thể mở ảnh. Không commit API token;
reader chỉ cần public URL, không cần secret.

## 5. Cập nhật manifest

Manifest chỉ chứa tên truyện/chapter và đường dẫn ảnh, không copy ảnh vào repo:

```powershell
python .\scripts\generate_library.py
```

## 6. Tạo GitHub repo chỉ từ `ui (hosting)`

Project này đã có `.git` riêng. Trên GitHub, chọn **New repository**:

- Tên gợi ý: `yoru-manga-reader`.
- Không chọn tạo README, `.gitignore` hoặc license vì local đã có sẵn.
- Repo public là cách đơn giản nhất để dùng GitHub Pages.

Trong folder `ui (hosting)`, đặt danh tính commit, tạo commit đầu tiên, rồi nối repo
và push. Có thể dùng email `noreply` trong GitHub > Settings > Emails:

```powershell
Set-Location -LiteralPath "D:\Google Drive Stream\My Drive\3- Projects & Learning\private beach\ui (hosting)"
git config user.name "TEN_GITHUB_CUA_BAN"
git config user.email "EMAIL_GITHUB_HOAC_NOREPLY"
git commit -m "Initial hosted manga reader"
git remote add origin "https://github.com/USERNAME/yoru-manga-reader.git"
git push -u origin main
```

Do `.git` nằm ngay trong `ui (hosting)`, Git chỉ thấy nội dung folder này; folder
`library`, `ui`, `tools` và phần còn lại của `private beach` không nằm trong repo.

## 7. Bật GitHub Pages

Trong GitHub repo:

1. **Settings** > **Pages**.
2. **Build and deployment** > Source: **Deploy from a branch**.
3. Branch: `main`, folder: `/(root)` > **Save**.
4. URL sẽ có dạng `https://USERNAME.github.io/yoru-manga-reader/`.

## 8. Luồng cập nhật hằng ngày

1. Tải chapter mới vào `private beach/library`.
2. Chạy script upload R2 với `-Execute`.
3. Chạy `python scripts/generate_library.py`.
4. Commit và push `library-data.js`.

Không dùng `rclone sync` trừ khi thật sự muốn xóa trên R2 mọi file đã bị xóa ở
Google Drive.
