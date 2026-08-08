# System Architecture & Technical Flow

## 1. Clean Architecture Layer Dependency Diagram

Sơ đồ mô tả quy tắc phụ thuộc 1 chiều (Dependency Rule) giữa các tầng trong ứng dụng Backend:

```mermaid
graph TD
    subgraph Presentation Layer - app/presentation
        API[FastAPI Routers /api/v1]
        SCHEMAS[Pydantic v2 Schemas]
    end

    subgraph Application Layer - app/application
        UC_BOOKING[Booking Use Cases]
        UC_CATALOG[Catalog & Ops Use Cases]
        UC_HOTEL[Hotel & Tour Use Cases]
    end

    subgraph Domain Layer - app/domain
        ERRORS[Domain Exceptions & Rules]
    end

    subgraph Infrastructure Layer - app/infrastructure
        ORM[SQLAlchemy ORM Models]
        DB_SESS[Database Session Manager]
        SEPAY[SePay Webhook Client]
        MAIL_SMTP[Gmail SMTP Engine]
        STORAGE[Staging Storage Handler]
    end

    API -->|Calls| UC_BOOKING
    API -->|Calls| UC_CATALOG
    API -->|Calls| UC_HOTEL
    API -->|Uses| SCHEMAS

    UC_BOOKING -->|Enforces| ERRORS
    UC_CATALOG -->|Enforces| ERRORS
    UC_HOTEL -->|Enforces| ERRORS

    ORM -.->|Implements| ERRORS
    DB_SESS -->|Persists| ORM
    UC_BOOKING -->|Uses| ORM
    UC_BOOKING -->|Calls| SEPAY
    UC_BOOKING -->|Enqueues| MAIL_SMTP
```

---

## 2. Entity Relationship Diagram (Core Database Schema)

```mermaid
erDiagram
    PROVINCES ||--o{ PICKUP_DROPOFF_POINTS : "has many"
    PROVINCES ||--o{ ROUTES : "origin / destination"
    ROUTES ||--o{ TRIPS : "scheduled as"
    BUSES ||--o{ TRIPS : "assigned to"
    SEAT_LAYOUTS ||--o{ BUSES : "configured with"
    
    TRIPS ||--o{ BOOKINGS : "contains"
    BOOKINGS ||--o{ BOOKING_SEATS : "reserves"
    
    USERS ||--o{ BOOKINGS : "places (optional)"
    
    HOTELS ||--o{ HOTEL_ROOM_TYPES : "offers"
    HOTEL_ROOM_TYPES ||--o{ HOTEL_BOOKINGS : "booked in"
    
    TOURS ||--o{ TOUR_BOOKINGS : "booked for"

    BOOKINGS ||--o{ MAIL_JOBS : "triggers email"
```

---

## 3. Asynchronous Mail Processing Architecture

Hệ thống hỗ trợ cơ chế gửi mail bất đồng bộ (Durable Mail Queue) ngăn ngừa nghẽn request:

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Khách hàng
    participant API as FastAPI Router
    participant DB as Mail Queue (mail_jobs table)
    participant Worker as Mail Worker Process (scripts/mail_worker.py)
    participant SMTP as Gmail SMTP Server

    Customer->>API: POST /api/v1/client/bookings (Tạo đơn vé thành công)
    API->>DB: INSERT INTO mail_jobs (status='PENDING', template='booking_confirmation', payload=...)
    API-->>Customer: Trả về HTTP 201 Created (Kèm Mã đơn vé)
    
    Note over Worker,DB: Worker chạy độc lập ở background quét DB mỗi 5-10s
    Worker->>DB: SELECT * FROM mail_jobs WHERE status='PENDING' FOR UPDATE
    Worker->>SMTP: Render Jinja2 Template & Gửi Email qua SMTP
    alt Gửi thành công
        SMTP-->>Worker: 250 OK (Email Delivered)
        Worker->>DB: UPDATE mail_jobs SET status='SENT', sent_at=NOW()
    else Gửi thất bại (Lỗi mạng / SMTP Timeout)
        SMTP-->>Worker: Error / Connection Refused
        Worker->>DB: UPDATE mail_jobs SET status='RETRY', attempts=attempts+1
        Note over Worker,DB: Nếu attempts > MAIL_MAX_ATTEMPTS -> Chuyển sang failed_mail_jobs
    end
```

---

## 4. SePay Payment Webhook Reconciliation

1. Khách hàng thực hiện chuyển khoản bằng mã QR VietQR chứa cú pháp `KINGEXPRESS <MÃ_VÉ>`.
2. SePay Gateway phát hiện giao dịch thành công trên biến động số dư ngân hàng.
3. SePay phát webhook `POST /api/v1/payments/sepay-webhook` tới Backend FastAPI.
4. Handler trích xuất nội dung giao dịch, tìm bản ghi `Booking` tương ứng theo `booking_code`.
5. Kiểm tra số tiền chuyển khớp với `total_amount` của đơn vé.
6. Cập nhật `payment_status = 'PAID'`, tự động enqueue mail xác nhận vé đã thanh toán vào `mail_jobs`.
