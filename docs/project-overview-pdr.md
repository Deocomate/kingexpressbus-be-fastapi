# Project Overview & Backend Requirements (PDR)

## 1. Executive Summary

**King Express Bus Backend** (`kingexpressbus-be-fastapi`) là hệ thống RESTful API trung tâm xây dựng trên **FastAPI**, **SQLAlchemy 2.0** và **PostgreSQL/MySQL**, chịu trách nhiệm quản lý toàn bộ logic nghiệp vụ, giao dịch thanh toán, lập lịch xe, quản lý khách sạn/tour và xử lý hàng chờ gửi email cho dự án **King Express Bus**.

Hệ thống tuân thủ nghiêm ngặt nguyên lý **Clean Architecture**, phân tách rõ ràng giữa Domain errors, Use cases, Infrastructure services và Presentation routers.

---

## 2. Core Backend Modules & Business Capabilities

### 2.1. Quản lý Xe, Tuyến đường & Chuyến chạy (Fleet & Route Ops)
- **Tuyến đường & Điểm dừng**: Quản lý danh mục Tỉnh/Thành phố (`Province`), Địa điểm đón/trả (`PickupDropoffPoint`) và các Tuyến đường (`Route`).
- **Sơ đồ Xe & Ghế (`Bus` & `SeatLayout`)**: Cấu hình các dòng xe (Giường nằm 34-38 chỗ, Limousine VIP 22 cabin), lưu trữ sơ đồ ghế dưới dạng cấu trúc JSON linh hoạt (Tầng dưới / Tầng trên).
- **Lập lịch Chuyến xe (`Trip`)**: Thiết lập các chuyến chạy theo ngày/giờ, giá vé cơ bản, điểm đi/đến và gán xe điều hành.

### 2.2. Đặt vé & Xử lý Giao dịch (Booking & Transaction Engine)
- **Giữ chỗ & Đặt vé (`Booking`)**: Tiếp nhận yêu cầu đặt vé từ khách hàng, kiểm tra trùng lặp vị trí ghế theo thời gian thực (Concurrency / Unique constraints).
- **Phụ phí (`Surcharge`)**: Tự động tính toán phụ phí ngày lễ/Tết, phụ phí đón/trả tận nơi theo địa điểm.
- **Xác thực Đơn hàng**: Sinh mã vé duy nhất (`booking_code`), lưu vết trạng thái (`UNPAID`, `PAID`, `CANCELLED`).

### 2.3. Cổng Thanh toán SePay VietQR (Payment Reconciliation)
- **Tích hợp SePay Webhook**: Tiếp nhận notification chuyển khoản ngân hàng từ SePay qua API endpoint `/api/v1/payments/sepay-webhook`.
- **Khớp đơn tự động**: Phân tích nội dung chuyển khoản (`KINGEXPRESS <MÃ_VÉ>`), tìm kiếm đơn hàng tương ứng, xác minh số tiền khớp khớp và cập nhật vé sang trạng thái `PAID`.

### 2.4. Khách sạn & Tour Du lịch (Hotels & Tours Catalog)
- **API Khách sạn (`Hotel`, `HotelRoomType`, `HotelBooking`)**: Tìm kiếm danh mục khách sạn, chi tiết hạng phòng, đặt phòng và quản lý đơn qua Admin.
- **API Tour Du lịch (`Tour`, `TourBooking`)**: Quản lý các gói tour du lịch, bảng giá người lớn/trẻ em, lịch trình và nhận đơn đăng ký.

### 2.5. Hàng chờ Email Bền vững (Durable Mail Queue)
- Khai báo bảng `mail_jobs` trong cơ sở dữ liệu để lưu trữ hàng chờ gửi mail.
- Khi người dùng hoàn tất đặt vé hoặc gửi yêu cầu quên mật khẩu, hệ thống enqueues mail job vào DB thay vì gửi SMTP đồng bộ gây nghẽn request.
- Hỗ trợ 2 chế độ:
  - **Inline Mode (`MAIL_QUEUE_INLINE=true`)**: Xử lý gửi mail trong FastAPI `BackgroundTask` (phù hợp Dev/Local).
  - **Worker Mode (`MAIL_QUEUE_INLINE=false`)**: Tiến trình độc lập `scripts/mail_worker.py` liên tục quét DB và gửi mail qua Gmail SMTP với chính sách tự động retry khi thất bại.

### 2.6. Delete Guards & Bảo vệ Ràng buộc Dữ liệu (`app/application/catalog/delete_guards.py`)
- Ngăn chặn xóa dữ liệu có chứa quan hệ ràng buộc (ví dụ: Không cho xóa Tuyến đường/Tỉnh thành khi đang có Vé xe hoặc Chuyến xe hoạt động).
- Trả về mã lỗi HTTP 400 kèm thông báo cấu trúc chi tiết `{ detail: { message, booking_count } }` giúp Admin hiển thị thông báo rõ ràng cho người dùng.

---

## 3. Security & Admin Authentication

- **Mật khẩu**: Mã hóa an toàn bằng thuật toán `bcrypt`.
- **Admin Authentication**: Sử dụng OAuth2 Password Flow kết hợp JSON Web Tokens (JWT) hoặc HttpOnly Session Cookies.
- **Rate Limiting**: Giới hạn số lượng request đối với các endpoint nhạy cảm (Đăng nhập, Quên mật khẩu, Tạo đặt vé) để chống tấn công Brute-force/DDoS.
