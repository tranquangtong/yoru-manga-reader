# Yoru hosted manga reader

Bản web tĩnh của Yoru dành cho mô hình:

- GitHub Pages: host HTML, CSS, JavaScript và manifest thư viện.
- Cloudflare R2: host ảnh manga.
- rclone: copy ảnh trực tiếp qua API từ Google Drive sang R2.

Repo này độc lập với folder cha `private beach`. Ảnh manga và thông tin đăng nhập
R2 không được đưa vào Git.

## Trước khi publish

1. Làm theo [SETUP.md](SETUP.md) để tạo bucket và cấu hình rclone.
2. Sửa `assetBaseUrl` trong `config.js` thành URL public của bucket, kết thúc bằng
   `/library/`.
3. Sau khi tải ảnh lên R2, chạy `python scripts/generate_library.py` để tạo `library-data.js`.
4. Mở local test bằng `python -m http.server 8080`, rồi truy cập
   `http://localhost:8080/`.

## Cập nhật chapter sau này

Cách nhanh nhất sau khi thêm, sửa hoặc xóa truyện/chapter là double-click
`Update UI - Windows.cmd`. Trên macOS, chạy `Update UI - macOS.command`.
Updater đọc danh sách ảnh dưới `library/` trong bucket R2 `yoru-manga` và chỉ
commit, push khi danh mục thay đổi.

Dùng thông tin xác thực R2 S3 có quyền đọc và liệt kê object. Updater đọc
`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` và hai biến tùy chọn
`R2_BUCKET`, `R2_PREFIX`. Trên macOS, updater có thể dùng chung cấu hình và
Keychain với uploader. Nếu thiếu thông tin, updater sẽ hỏi trong terminal.

Dùng `python scripts/update-site.py --generate-only` để chỉ tạo manifest. Thêm
`--source local` để đọc thư mục `library` cạnh repo. Để chọn thư mục khác, chạy
`python scripts/generate_library.py --source local --library-dir "/đường/dẫn/library"`.
`python scripts/prune_missing_series.py` vẫn có thể chạy riêng để xem trước các bộ
thiếu ảnh bìa. Thêm `--apply` để cập nhật manifest.

Nếu vừa thêm ảnh mới, upload R2 trước rồi mới chạy updater UI:

```powershell
.\scripts\upload-library-to-r2.ps1 `
  -Destination "r2:yoru-manga/library" `
  -Execute
python .\scripts\update-site.py
```

Script dùng `rclone copy`, không dùng `sync`, nên không xóa object đang có trên R2.
