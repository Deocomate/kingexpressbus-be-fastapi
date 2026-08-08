# Codebase Summary & Clean Architecture Layers

Tài liệu này tổng hợp cấu trúc mã nguồn backend và chi tiết phân tầng Clean Architecture áp dụng trong dự án **kingexpressbus-be-fastapi**.

---

## 1. Clean Architecture Layer Breakdown (`app/`)

```text
app/
├── domain/                  # Tầng Domain (Core Errors & Business Rules)
│   └── errors.py            # Ngoại lệ nghiệp vụ (DomainException, NotFoundError, BookingError)
│
├── application/             # Tầng Application (Use Cases & Business Workflows)
│   ├── auth/                # Đăng nhập, đăng ký, khôi phục mật khẩu admin/client
│   ├── booking/             # Tạo vé, giữ chỗ, kiểm tra trùng ghế, tính tiền phụ phí
│   ├── catalog/             # Quản lý danh mục xe, tuyến đường, điểm đón trả
│   ├── hotel/               # Logic quản lý & đặt phòng khách sạn
│   ├── tour/                # Logic quản lý & đặt tour du lịch
│   └── website/             # Quản lý cài đặt bài viết CMS, banner, hotline
│
├── infrastructure/          # Tầng Infrastructure (Database, External APIs & Storage)
│   ├── persistence/
│   │   ├── base.py          # SQLAlchemy Declarative Base
│   │   ├── session.py       # Async/Sync Database Engine & Sessionmaker
│   │   ├── models/          # ORM Models (user, booking, fleet, location, ops, hotel, tour, website, mail_queue)
│   │   └── seed_data/       # Dữ liệu JSON khởi tạo cho bảng danh mục
│   ├── mail/                # Jinja2 rendering & Gmail SMTP client
│   ├── payments/            # Modul xử lý webhook SePay VietQR
│   ├── security/            # Bcrypt password hashing & JWT encoding/decoding
│   └── storage/             # Quản lý file uploads & staging directory
│
├── presentation/            # Tầng Presentation (FastAPI Routers & Pydantic Schemas)
│   ├── api/v1/
│   │   ├── admin/           # Routers dành riêng cho Admin Portal (trips, routes, fleet, bookings, hotels, tours, website)
│   │   ├── auth/            # Auth endpoints (login, logout, refresh)
│   │   ├── bookings/        # Client booking & payment endpoints
│   │   ├── public.py        # Endpoints công khai (tìm chuyến xe, trang chủ, địa điểm)
│   │   ├── hotels.py        # Endpoints public khách sạn
│   │   └── tours.py         # Endpoints public tour
│   └── schemas/             # Pydantic v2 validation models (Request/Response DTOs)
│
├── core/                    # Core Config & Dependencies Injection
│   ├── config.py            # pydantic-settings BaseSettings (Database URL, SMTP, Secret Key)
│   ├── deps.py              # FastAPI Depends helpers (get_db, get_current_user, require_admin)
│   ├── rate_limit.py        # Slowapi / Rate limiter integration
│   └── security.py          # Token creation helpers
│
└── templates/               # Jinja2 Email Templates
    ├── booking_confirmation.html  # Email xác nhận đặt vé xe khách
    └── reset_password.html        # Email hướng dẫn khôi phục mật khẩu
```

---

## 2. Key Database Models Summary (`app/infrastructure/persistence/models/`)

| File Model | Tên Bảng (Tables) | Mô tả |
|---|---|---|
| `user.py` | `users` | Tài khoản Admin & Khách hàng, lưu hash bcrypt & thông tin cá nhân. |
| `booking.py` | `bookings`, `booking_seats` | Thông tin đơn đặt vé, mã vé, họ tên hành khách, danh sách ghế đã chọn, trạng thái thanh toán. |
| `fleet.py` | `buses`, `seat_layouts` | Quản lý phương tiện xe khách, biển số, loại xe và sơ đồ ghế JSON. |
| `location.py` | `provinces`, `pickup_dropoff_points` | Danh mục tỉnh thành và các điểm đón/trả khách cố định. |
| `ops.py` | `routes`, `trips`, `trip_stops` | Tuyến đường di chuyển, lịch trình chuyến xe chạy theo ngày/giờ và các điểm dừng giữa chặng. |
| `surcharge.py` | `surcharges`, `trip_surcharges` | Phụ phí đón trả, phụ phí lễ tết áp dụng theo tuyến/chuyến. |
| `hotel.py` | `hotels`, `hotel_room_types`, `hotel_bookings` | Danh mục khách sạn, loại phòng và đơn đặt phòng. |
| `tour.py` | `tours`, `tour_bookings` | Danh mục tour du lịch và đơn đặt tour. |
| `website.py` | `website_settings`, `cms_pages` | Cấu hình thông tin nhà xe, bài viết chính sách, trang CMS động. |
| `mail_queue.py`| `mail_jobs`, `failed_mail_jobs` | Hàng chờ lưu trữ các email cần gửi, lịch sử retry và trạng thái gửi. |

---

## 3. Database Migration Engine (Alembic)

Toàn bộ thay đổi cấu trúc bảng được theo dõi thông qua **Alembic**:
- File cấu hình: `alembic.ini`.
- Các file script chuyển đổi schema lưu tại `alembic/versions/`.
- Chạy lệnh cập nhật schema: `alembic upgrade head`.

---

## 4. Additive Seed Infrastructure (`scripts/seeds/`)

Nạp dữ liệu mồi (Seeding) hỗ trợ 2 cơ chế độc lập:
1. **Full Reseed (`scripts/seed.py`)**: Sử dụng ở môi trường Dev, thực hiện xóa sạch dữ liệu (Truncate) và nạp lại từ các file JSON trong `app/infrastructure/persistence/seed_data/`.
2. **Additive Seeds (`scripts/seeds/apply.py`)**: Sử dụng cho Production/Staging. Hệ thống quét theo `slug`/`key` và chỉ `INSERT` thêm các bản ghi danh mục mới chưa tồn tại, **tuyệt đối không xóa dữ liệu đơn hàng hay tài khoản người dùng**.
