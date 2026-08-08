# Production & Infrastructure Deployment Guide

Tài liệu này hướng dẫn chi tiết cách triển khai dự án **King Express Bus Backend** trên các môi trường Docker, Linux Server và quản lý các background workers.

---

## 1. Local & Production Docker Setup

Dự án cung cấp 2 file Docker Compose phù hợp cho 2 mục đích triển khai:

### 1.1. Local / Dev Environment (`docker-compose.local.yml`)

Môi trường phát triển tích hợp sẵn PostgreSQL database và FastAPI app tự động reload code:

```bash
docker-compose -f docker-compose.local.yml up --build -d
```
- App container: `http://localhost:8000`
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Redoc Documentation: `http://localhost:8000/redoc`

### 1.2. Production Environment (`docker-compose.production.yml`)

Môi trường Production khởi chạy container backend kết nối trực tiếp cơ sở dữ liệu sản xuất:

```bash
docker-compose -f docker-compose.production.yml up --build -d
```

### Quy trình Entrypoint (`scripts/docker-entrypoint.sh`):
Mỗi khi Container khởi chạy, entrypoint script sẽ tự động:
1. Chờ kết nối Cơ sở dữ liệu khả dụng.
2. Thực thi lệnh `alembic upgrade head` để đảm bảo Schema DB luôn ở phiên bản mới nhất.
3. Khởi chạy Gunicorn / Uvicorn workers lắng nghe ứng dụng.

---

## 2. Setting Up Background Services (Daemons & Cron)

### 2.1. Mail Queue Worker Service (Systemd Daemon)

Trên máy chủ Production Linux, thiết lập Mail Worker dưới dạng một Systemd Service để đảm bảo tự động chạy ngầm và tự khởi động lại khi sự cố:

Tạo file `/etc/systemd/system/kingexpress-mailworker.service`:

```ini
[Unit]
Description=King Express Bus Mail Queue Worker
After=network.target postgresql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/var/www/kingexpressbus-be-fastapi
ExecStart=/var/www/kingexpressbus-be-fastapi/.venv/bin/python -m scripts.mail_worker
Restart=always
RestartSec=10
EnvironmentFile=/var/www/kingexpressbus-be-fastapi/.env

[Install]
WantedBy=multi-user.target
```

Kích hoạt và khởi chạy service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kingexpress-mailworker
sudo systemctl start kingexpress-mailworker
sudo systemctl status kingexpress-mailworker
```

---

### 2.2. Upload Staging Garbage Collection (Cron Job)

Các file ảnh admin tải lên nhưng chưa bấm lưu sẽ nằm ở thư mục tạm `uploads/admin-tmp/`. Chạy script dọn dẹp hàng ngày thông qua Cron Job:

Mở bảng cấu hình cron:
```bash
crontab -e
```

Thêm dòng sau (chạy lúc 00:00 mỗi đêm, xóa file tạm cũ hơn 24 giờ):
```cron
0 0 * * * cd /var/www/kingexpressbus-be-fastapi && .venv/bin/python -m scripts.prune_upload_staging >> /var/log/kingexpressbus/prune-uploads.log 2>&1
```

---

## 3. Database Migration & Additive Seeding in Production

Khi phát hành một phiên bản tính năng mới có chứa thay đổi Database:

```bash
# 1. Cập nhật mã nguồn mới từ Git
git pull origin main

# 2. Cài đặt các gói phụ thuộc mới (nếu có)
.venv/bin/pip install -r requirements.txt

# 3. Chạy cập nhật DB Schema
.venv/bin/alembic upgrade head

# 4. Kiểm tra các bản ghi seed bổ sung (Additive Seeds)
.venv/bin/python -m scripts.seeds.apply --list

# 5. Nạp dữ liệu seed mới an toàn cho Production
.venv/bin/python -m scripts.seeds.apply --all

# 6. Restart backend service
sudo systemctl restart kingexpressbus-backend
```
