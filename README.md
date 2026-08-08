# King Express Bus - Backend (FastAPI + SQLAlchemy)

Hệ thống xử lý nghiệp vụ trung tâm (Backend RESTful API Service) cho hệ thống **King Express Bus**, được phát triển dựa trên **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2** và kiến trúc sạch **Clean Architecture**.

---

## 🏗️ Kiến trúc Hệ thống (Clean Architecture)

Dự án áp dụng mô hình Clean Architecture phân tầng nghiêm ngặt trong thư mục `app/`:

```text
app/
├── domain/            # Định nghĩa lỗi nghiệp vụ (Domain Errors) & Core Rules
├── application/       # Use Cases xử lý logic nghiệp vụ (Booking, Auth, Catalog, Hotel, Tour, Website)
├── infrastructure/    # Cấu hình SQLAlchemy models, SePay Gateway, Mail SMTP, Storage uploads
├── presentation/      # FastAPI routers (/api/v1) & Pydantic v2 validation schemas
├── core/              # System settings, security (JWT/Bcrypt), dependencies injection
└── templates/         # Jinja2 HTML email templates (Booking confirmation, Password reset)
```

**Quy tắc phụ thuộc (Dependency Rule)**:  
`presentation` ➔ `application` ➔ `domain` ⬅️ `infrastructure`

---

## 🚀 Công nghệ & Thư viện Chính

- **Python**: `>= 3.11`
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) + Pydantic v2
- **ORM & DB Engine**: SQLAlchemy 2.0 + Alembic (Database Migrations)
- **Database**: PostgreSQL / MySQL
- **Authentication**: OAuth2 / Bearer Token & Cookie-based Admin Auth (Bcrypt, PyJWT)
- **Email Engine**: Durable MySQL/PostgreSQL Mail Queue (`mail_jobs`) + Jinja2 + Gmail SMTP
- **Thanh toán**: SePay VietQR Payment Gateway Webhook Integration

---

## 🛠️ Hướng dẫn Khởi chạy & Thiết lập Cơ sở Dữ liệu

### 1. Khởi tạo Môi trường Ảo & Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Cấu hình File Môi trường (`.env`)
Tạo file `.env` từ `.env.example`:
```env
APP_ENV=development
SECRET_KEY=your_super_secret_jwt_key
DATABASE_URL=postgresql://user:password@localhost:5432/kingexpressbus

# Email & Mail Queue Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
MAIL_QUEUE_INLINE=true
```

### 3. Migrations & Seed Dữ liệu

```bash
# 1. Chạy Alembic Upgrade Schema
alembic upgrade head

# 2. Seed dữ liệu mẫu (LOCAL / DEV ONLY - Xóa & nạp lại toàn bộ bảng)
python scripts/seed.py

# 3. Additive Seed updates (Production-safe - chỉ thêm dữ liệu thiếu, không truncate)
python -m scripts.seeds.apply --all
```

> **Tài khoản Admin mặc định sau khi Seed**: `admin@kingexpressbus.com` / `Admin@123`

---

## 🛠️ Scripts & Background Workers

| Script | Mục đích |
|---|---|
| `scripts/seed.py` | Truncate & Seed toàn bộ dữ liệu mẫu (Dev mode) |
| `scripts/seeds/apply.py` | Nạp dữ liệu sản phẩm/danh mục bổ sung an toàn cho Prod |
| `scripts/mail_worker.py` | Background worker xử lý hàng chờ gửi email (`mail_jobs`) |
| `scripts/prune_upload_staging.py` | Garbage Collection dọn dẹp file upload tạm chưa commit |

---

## 🧪 Chạy Kiểm thử (Pytest)

```bash
# Chạy toàn bộ test suite
pytest

# Chạy test chi tiết kèm output
pytest -v -s
```

---

## 📚 Tài liệu Chi tiết (`./docs`)

Thông tin chi tiết về thiết kế API và kiến trúc lưu trữ được lưu tại thư mục `./docs`:

- 📋 [Overview & PDR](./docs/project-overview-pdr.md): Yêu cầu nghiệp vụ, Delete-guards & SePay flow.
- 📦 [Codebase Summary](./docs/codebase-summary.md): Chi tiết các tầng Clean Architecture & Model schemas.
- 📏 [Code Standards](./docs/code-standards.md): Tiêu chuẩn lập trình Python, FastAPI, SQLAlchemy 2.0 & Pytest.
- 🏗️ [System Architecture](./docs/system-architecture.md): Sơ đồ kiến trúc Clean Architecture, ERD & Mail Pipeline.
- 🚀 [Deployment Guide](./docs/deployment-guide.md): Triển khai Docker Compose, Mail Worker Daemon & Cron jobs.
- 🎨 [API & Database Design](./docs/design-guidelines.md): Quy chuẩn RESTful API, Pagination contract & Indexing.
- 🗺️ [Project Roadmap](./docs/project-roadmap.md): Lộ trình phát triển & tính năng backend tương lai.
