from codrut.modules.communications.html_sanitizer import sanitize_email_html


def test_email_html_sanitizer_removes_active_content_and_unsafe_urls() -> None:
    sanitized = sanitize_email_html(
        '<script>alert(1)</script><p onclick="alert(2)">Salut '
        '<a href="javascript:alert(3)">aici</a></p>'
    )

    assert "script" not in sanitized
    assert "alert" not in sanitized
    assert "onclick" not in sanitized
    assert "javascript:" not in sanitized
    assert "Salut" in sanitized


def test_email_html_sanitizer_preserves_email_layout_and_tracking_hooks() -> None:
    sanitized = sanitize_email_html(
        '<table role="presentation" cellpadding="0" style="border-collapse:collapse">'
        '<tr><td style="padding:12px;color:#890505">'
        '<a data-codrut-cta="1" href="https://codrut.example/demo">Deschide</a>'
        "</td></tr></table>"
    )

    assert '<table role="presentation" cellpadding="0"' in sanitized
    assert "border-collapse:collapse" in sanitized
    assert "padding:12px" in sanitized
    assert "color:#890505" in sanitized
    assert 'data-codrut-cta="1"' in sanitized
    assert 'href="https://codrut.example/demo"' in sanitized
