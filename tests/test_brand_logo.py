from hashlib import sha256
from pathlib import Path


EXPECTED_SARE_LOGO_SHA256 = "98f9704b25bc2e80fc92190ece7347fa48753f8dfef1769c0dff05d9171d2e04"


def test_official_sare_logo_is_the_exact_uploaded_png():
    logo = Path("app/static/icons/sare-logo-original.png")
    assert logo.exists()
    assert logo.stat().st_size == 153_763
    assert sha256(logo.read_bytes()).hexdigest() == EXPECTED_SARE_LOGO_SHA256


def test_visible_branding_uses_official_png_not_recreated_svg():
    for template in [
        Path("app/templates/base.html"),
        Path("app/templates/auth/login.html"),
        Path("app/templates/applicator/dashboard.html"),
    ]:
        content = template.read_text(encoding="utf-8")
        assert "icons/sare-logo-original.png" in content
        assert "icons/sare-brand.svg" not in content

    assert not Path("app/static/icons/sare-brand.svg").exists()
