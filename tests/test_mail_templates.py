"""Unit tests for Jinja2 booking mail templates and formatters."""

from __future__ import annotations

from datetime import date

import pytest

from app.infrastructure.mail.mail_formatters import (
    absolute_url,
    format_booking_date,
    format_pickup_info,
    format_vnd,
    payment_method_label,
)
from app.infrastructure.mail.mail_templates import render_booking_mail


def _details(**overrides):
    base = {
        "booking_id": 1,
        "booking_code": "BCIGHXHG2DOC5XS8",
        "customer_name": "Tran Hoang Manh",
        "customer_email": "guest@example.com",
        "customer_phone": "+84961864833",
        "customer_display": "Tran Hoang Manh +84961864833",
        "booking_date": "2026-08-07",
        "booking_date_display": "07/08/2026",
        "quantity": 2,
        "quantity_label": "2 vé / ticket(s)",
        "total_price": 1160000,
        "total_price_display": "1,160,000đ",
        "payment_method": "online_banking",
        "payment_method_label": "Chuyển khoản ngân hàng / Bank transfer",
        "route_name": "Hà Nội - Sapa",
        "start_time": "22:00",
        "ticket_type": "VIP Cabin Double 22",
        "pickup_info": "Đón tại khách sạn: Tòa T608",
        "web_title": "King Express Bus - Nhà xe chất lượng cao",
        "web_phone": "+84924300366",
        "logo_url": "https://kingexpressbus.com/assets/logo.jpg",
        "website_url": "https://kingexpressbus.com",
        "copyright_year": 2026,
        "payment_url": "https://kingexpressbus.com/dat-ve/chuyen-huong-sepay/BCIGHXHG2DOC5XS8",
        "cancel_reason": None,
    }
    base.update(overrides)
    return base


def test_format_vnd_and_date_and_payment() -> None:
    assert format_vnd(1160000) == "1,160,000đ"
    assert format_vnd(None) == "0đ"
    assert format_booking_date(date(2026, 8, 7)) == "07/08/2026"
    assert format_booking_date("2026-08-07") == "07/08/2026"
    assert (
        payment_method_label("online_banking")
        == "Chuyển khoản ngân hàng / Bank transfer"
    )
    assert "Cash on pickup" in payment_method_label("cash_on_pickup")


def test_absolute_url_and_hotel_pickup() -> None:
    assert (
        absolute_url("/assets/logo.jpg", "https://kingexpressbus.com")
        == "https://kingexpressbus.com/assets/logo.jpg"
    )
    assert (
        absolute_url("https://cdn.example/logo.jpg", "https://kingexpressbus.com")
        == "https://cdn.example/logo.jpg"
    )
    assert (
        format_pickup_info(
            pickup_stop_id=None,
            pickup_name=None,
            pickup_address=None,
            hotel_address="Tòa T608",
        )
        == "Đón tại khách sạn: Tòa T608"
    )


def test_confirmation_html_matches_sample_fields() -> None:
    subject, html = render_booking_mail("confirmation", _details())
    assert "Tiếp nhận yêu cầu đặt vé" in subject
    assert "#BCIGHXHG2DOC5XS8" in subject
    assert "Tiếp nhận yêu cầu đặt vé" in html
    assert "#BCIGHXHG2DOC5XS8" in html
    assert "Hà Nội - Sapa" in html
    assert "VIP Cabin Double 22" in html
    assert "07/08/2026" in html
    assert "22:00" in html
    assert "Đón tại khách sạn: Tòa T608" in html
    assert "guest@example.com" in html
    assert "2 vé / ticket(s)" in html
    assert "1,160,000đ" in html
    assert "Chuyển khoản ngân hàng / Bank transfer" in html
    assert "+84924300366" in html
    assert "https://kingexpressbus.com/assets/logo.jpg" in html


def test_payment_request_includes_pay_link() -> None:
    subject, html = render_booking_mail("payment_request", _details())
    assert "Payment Request" in subject
    assert "chuyen-huong-sepay/BCIGHXHG2DOC5XS8" in html
    assert "Thanh toán ngay" in html


def test_approval_and_cancellation() -> None:
    _, approval = render_booking_mail("approval", _details())
    assert "đã được xác nhận" in approval
    _, cancel = render_booking_mail(
        "cancellation", _details(cancel_reason="Customer request")
    )
    assert "đã bị hủy" in cancel
    assert "Customer request" in cancel


def test_autoescape_customer_fields() -> None:
    _, html = render_booking_mail(
        "confirmation",
        _details(customer_display='<script>alert(1)</script> Evil'),
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="Unknown mail kind"):
        render_booking_mail("nope", _details())
