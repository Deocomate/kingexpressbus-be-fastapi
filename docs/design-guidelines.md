# API & Database Design Guidelines

Tài liệu này định nghĩa các tiêu chuẩn thiết kế RESTful API contract, chuẩn phân trang (Pagination), định dạng lỗi và quy tắc đánh chỉ mục Database áp dụng cho dự án **kingexpressbus-be-fastapi**.

---

## 1. RESTful API Naming & URL Conventions

### 1.1. Chuẩn hóa URL Routes
- Đặt tên danh từ số nhiều cho các tài nguyên (Resources): `/api/v1/routes`, `/api/v1/trips`, `/api/v1/bookings`, `/api/v1/hotels`.
- Phân biệt rõ ràng giữa Client API (`/api/v1/...`) và Admin API (`/api/v1/admin/...`).
- Sử dụng **kebab-case** cho tất cả đường dẫn URL (VD: `/api/v1/admin/hotel-bookings`, `/api/v1/payments/sepay-webhook`).

### 1.2. Động từ HTTP (HTTP Methods)
- `GET`: Tra cứu, lấy danh sách hoặc thông tin chi tiết (không làm thay đổi trạng thái hệ thống).
- `POST`: Tạo mới tài nguyên (Tạo đơn vé, nạp bài viết mới, gửi yêu cầu thanh toán).
- `PUT`: Cập nhật toàn bộ hoặc thông tin chính của tài nguyên.
- `PATCH`: Cập nhật một phần thuộc tính (Cập nhật trạng thái vé, đổi mật khẩu).
- `DELETE`: Xóa tài nguyên (Bảo vệ bởi Delete Guards).

---

## 2. Pagination & Unified Response Contract

Tất cả các API danh sách phía Admin tuân thủ chuẩn phân trang chung của FastAPI backend (`app/presentation/schemas/admin_common.py`):

### 2.1. Request Query Parameters
- `page`: Số trang hiện tại (Mặc định: `1`).
- `page_size`: Số bản ghi trên mỗi trang (Mặc định: `10` hoặc `20`).
- `q`: Từ khóa tìm kiếm (Optional search string).

### 2.2. Response Payload Structure
```json
{
  "items": [
    {
      "id": 101,
      "code": "KING123456",
      "customer_name": "Nguyen Van A",
      "total_amount": 350000,
      "status": "PAID"
    }
  ],
  "total": 145,
  "page": 1,
  "page_size": 10
}
```

---

## 3. Standardized Error Responses

Hệ thống quy chuẩn các phản hồi lỗi theo 2 định dạng:

### 3.1. Phản hồi Lỗi Chuỗi Đơn (`detail: string`)
Áp dụng cho các lỗi xác thực hoặc không tìm thấy dữ liệu (401 Unauthorized, 404 Not Found):
```json
{
  "detail": "Mật khẩu không chính xác hoặc tài khoản không tồn tại"
}
```

### 3.2. Phản hồi Lỗi Ràng buộc Delete Guard (`detail: object`)
Áp dụng khi không thể xóa đối tượng do có ràng buộc dữ liệu liên quan (400 Bad Request):
```json
{
  "detail": {
    "message": "Không thể xóa tuyến đường này vì đang có 12 chuyến xe và 45 đơn đặt vé tham chiếu.",
    "booking_count": 45
  }
}
```

---

## 4. Database Indexing & Performance Guidelines

Để tối ưu hóa tốc độ truy vấn cơ sở dữ liệu khi số lượng đơn hàng lên hàng trăm nghìn bản ghi:

1. **Khóa Chính & Foreign Keys**: Tất cả các trường Foreign Key (`trip_id`, `route_id`, `user_id`, `bus_id`) bắt buộc tạo **Index**.
2. **Unique Constraints**:
   - `bookings.code`: Unique Index hỗ trợ tra cứu mã vé siêu tốc.
   - `(trip_id, seat_number)` trong `booking_seats`: Unique Composite Index chống đặt trùng ghế.
3. **Compound Indexes cho Tìm kiếm**:
   - Index hợp phần `(route_id, departure_time)` trên bảng `trips` tối ưu hóa câu truy vấn tìm kiếm chuyến xe theo lộ trình và ngày đi của khách hàng.
