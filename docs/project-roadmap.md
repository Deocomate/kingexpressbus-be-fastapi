# Project Roadmap & Development Phases

Tài liệu này ghi nhận quá trình phát triển, các cột mốc đã hoàn thành và định hướng lộ trình kỹ thuật cho dự án **King Express Bus Backend**.

---

## 1. Completed Phases & Key Milestones

### Phase 1: Database Architecture & Core Models
- [x] Thiết lập SQLAlchemy Declarative Base và khởi tạo hệ thống Alembic migration.
- [x] Xây dựng các Entity chính: `User`, `Booking`, `Bus`, `SeatLayout`, `Province`, `PickupDropoffPoint`, `Route`, `Trip`, `Surcharge`.
- [x] Xây dựng cơ chế Full Seed (`scripts/seed.py`) nạp dữ liệu mẫu ban đầu cho môi trường Dev.

### Phase 2: Booking Engine & Concurrency Control
- [x] API tìm kiếm chuyến xe theo lộ trình, ngày đi, số hành khách.
- [x] Logic đặt vé xe khách, giữ ghế thời gian thực, tính toán phụ phí đón trả.
- [x] Ràng buộc Unique constraint ngăn ngừa đặt trùng vị trí ghế trên cùng một chuyến chạy.

### Phase 3: SePay VietQR Payment Gateway Integration
- [x] Thiết lập webhook handler nhận thông tin biến động số dư từ SePay (`/api/v1/payments/sepay-webhook`).
- [x] Logic khớp mã vé `KINGEXPRESS <MÃ_VÉ>` và tự động gạch nợ trạng thái `PAID`.
- [x] API Polling kiểm tra trạng thái vé real-time cho Frontend.

### Phase 4: Durable Mail Queue System
- [x] Xây dựng cơ sở dữ liệu hàng chờ email `mail_jobs` & `failed_mail_jobs`.
- [x] Thiết lập Jinja2 Email Templates (Email xác nhận vé xe, Email khôi phục mật khẩu).
- [x] Xây dựng tiến trình độc lập `scripts/mail_worker.py` với chiến lược retry tự động và ghi log chi tiết.

### Phase 5: Additional Catalogs & Production Readiness
- [x] Bổ sung các module Khách sạn (`Hotel`) và Tour Du lịch (`Tour`) kèm đầy đủ RESTful CRUD APIs.
- [x] Xây dựng cơ chế **Additive Seeds (`scripts/seeds/apply.py`)** cho phép nạp bổ sung dữ liệu danh mục an toàn trên môi trường Production mà không gây mất dữ liệu vé.
- [x] Xây dựng **Delete Guards (`app/application/catalog/delete_guards.py`)** bảo vệ an toàn dữ liệu tham chiếu (cascade restriction).
- [x] Viết script Garbage Collection dọn dẹp file upload tạm (`scripts/prune_upload_staging.py`).

---

## 2. Future Backend Roadmap & Technical Initiatives

### Phase 6: Redis Caching & Performance Optimization (Q3/2026)
- [ ] Tích hợp Redis làm Cache Layer cho các endpoint đọc dữ liệu tần suất cao (Danh mục tuyến đường, danh sách địa điểm, thông tin xe).
- [ ] Áp dụng Redis Distributed Lock hỗ trợ khóa ghế ở cấp độ microsecond cho các khung giờ cao điểm mở bán vé Tết.

### Phase 7: Taskiq / Celery Task Queue Transition (Q4/2026)
- [ ] Chuyển đổi hệ thống Mail Worker từ Script Polling DB sang Task Queue chuyên dụng (Taskiq hoặc Celery + Redis Broker).
- [ ] Tự động hóa các công việc định kỳ: Tổng hợp báo cáo doanh thu ngày, gửi SMS/Zalo ZNS nhắc lịch khởi hành trước 2 giờ.

### Phase 8: System Observability & OpenTelemetry (Q1/2027)
- [ ] Tích hợp Prometheus metrics exporter theo dõi response time và error rates của FastAPI endpoints.
- [ ] Thiết lập OpenTelemetry Distributed Tracing kết nối theo dõi luồng request từ Next.js Frontend sang FastAPI Backend.
