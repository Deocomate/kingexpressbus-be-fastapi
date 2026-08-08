# Code Standards & Python Engineering Practices

Tài liệu này định nghĩa các chuẩn mực lập trình Python, tiêu chuẩn FastAPI, SQLAlchemy 2.0 và quy tắc kiểm thử áp dụng cho dự án **kingexpressbus-be-fastapi**.

---

## 1. Python Code Formatting & Style Conventions

### 1.1. Tuân thủ PEP 8
- Mã nguồn Python tuân thủ chuẩn **PEP 8**.
- Độ dài dòng khuyến nghị: tối đa 88 - 100 ký tự.
- Đặt tên file, module, hàm, biến sử dụng **snake_case** (VD: `fetch_paginated`, `booking_service.py`).
- Đặt tên Class sử dụng **PascalCase** (VD: `BookingService`, `SeatLayout`, `ApiError`).
- Đặt tên Hằng số sử dụng **UPPER_SNAKE_CASE** (VD: `SECRET_KEY`, `MAX_RETRIES`).

### 1.2. Type Hinting (Gợi ý Kiểu dữ liệu)
Tất cả hàm trong Use Cases (`app/application/`), Services và FastAPI Router Handler phải sử dụng Type Annotations đầy đủ:

```python
from typing import Optional, List
from sqlalchemy.orm import Session
from app.infrastructure.persistence.models.booking import Booking

def get_booking_by_code(db: Session, booking_code: string) -> Optional[Booking]:
    return db.query(Booking).filter(Booking.code == booking_code).first()
```

---

## 2. FastAPI & Pydantic v2 Best Practices

### 2.1. Pydantic Schemas Validation (`app/presentation/schemas/`)
- Tách biệt rõ ràng giữa Schema Đọc (`Out` / `Response`) và Schema Ghi (`Create` / `Update`).
- Khai báo `model_config = ConfigDict(from_attributes=True)` để Pydantic v2 tự động chuyển đổi từ SQLAlchemy ORM object sang JSON payload.

### 2.2. Dependency Injection (`app/core/deps.py`)
- Mọi database session phải inject qua `db: Session = Depends(get_db)`.
- Mọi thông tin Admin Auth phải inject qua `current_admin: User = Depends(require_admin_user)`.
- Tự động đóng session DB (`db.close()`) sau khi kết thúc request handler.

---

## 3. SQLAlchemy 2.0 Query Guidelines

1. **Khóa Concurrency & Integrity Constraints**:
   - Khi thực hiện giữ ghế / đặt vé, bắt buộc sử dụng giao dịch (Transaction) có khóa hoặc ràng buộc unique trên cặp `(trip_id, seat_number)` để chống trùng ghế khi 2 người dùng bấm chọn cùng 1 miligiây.
2. **Explicit Relationships & Lazy Loading**:
   - Sử dụng `joinedload()` hoặc `selectinload()` khi cần nạp dữ liệu liên quan để tránh lỗi N+1 Query.
3. **Delete Guards Pattern (`app/services/delete_guards.py`)**:
   - Khi người dùng gọi lệnh DELETE một thực thể (Tuyển đường, Điểm dừng, Khách sạn), bắt buộc kiểm tra xem thực thể đó có dữ liệu vé xe / đơn hàng đang tham chiếu hay không.
   - Nếu có, raise `HTTPException(status_code=400)` kèm message và thống kê chi tiết thay vì để DB ném `ForeignKeyViolation` unhandled 500 error.

---

## 4. Pytest & Testing Guidelines

- Mã nguồn test lưu tại thư mục `tests/`.
- Đảm bảo fixtures trong `conftest.py` khởi tạo database SQLite in-memory hoặc Test Postgres DB riêng biệt.
- Lệnh chạy test:
  ```bash
  # Run all tests
  pytest

  # Run specific test file
  pytest tests/test_phase04_booking_sepay.py
  ```
- Tuyệt đối không viết test làm thay đổi hoặc làm bẩn dữ liệu thật trên DB Production.
