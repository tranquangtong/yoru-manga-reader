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
3. Chạy `python scripts/generate_library.py` để cập nhật `library-data.js`.
4. Mở local test bằng `python -m http.server 8080`, rồi truy cập
   `http://localhost:8080/`.

## Cập nhật chapter sau này

```powershell
.\scripts\upload-library-to-r2.ps1 `
  -Destination "r2:yoru-manga/library" `
  -Execute
python .\scripts\generate_library.py
git add library-data.js
git commit -m "Update manga library"
git push
```

Script dùng `rclone copy`, không dùng `sync`, nên không xóa object đang có trên R2.
