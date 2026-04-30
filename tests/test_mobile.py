"""Tests for mobile / responsive support."""
import re


class TestMobileViewport:
    """Verify the HTML has the correct viewport meta tag for mobile."""

    def test_viewport_meta_present(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert 'name="viewport"' in html
        assert "width=device-width" in html
        assert "initial-scale=1" in html

    def test_no_user_scalable_no(self, client):
        """Users should be able to zoom on mobile (no user-scalable=no)."""
        res = client.get("/")
        html = res.data.decode()
        assert "user-scalable=no" not in html


class TestMobileNavigation:
    """Verify mobile navigation elements are present in the HTML."""

    def test_mobile_topbar_exists(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert 'class="mobile-topbar"' in html

    def test_hamburger_button_exists(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert 'class="mobile-menu-btn"' in html
        assert 'aria-label="Open menu"' in html

    def test_sidebar_overlay_exists(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert 'id="sidebar-overlay"' in html
        assert "sidebar-overlay" in html

    def test_hamburger_calls_toggle(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert "toggleMobileMenu()" in html

    def test_overlay_calls_close(self, client):
        res = client.get("/")
        html = res.data.decode()
        assert "closeMobileMenu()" in html


class TestMobileCSS:
    """Verify the CSS stylesheet contains mobile responsive rules."""

    def test_css_loads(self, client):
        res = client.get("/static/css/style.css")
        assert res.status_code == 200

    def test_768_breakpoint_exists(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert "max-width:768px" in css or "max-width: 768px" in css

    def test_480_breakpoint_exists(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert "max-width:480px" in css or "max-width: 480px" in css

    def test_mobile_topbar_hidden_by_default(self, client):
        css = client.get("/static/css/style.css").data.decode()
        # Topbar should be display:none by default
        assert re.search(r"\.mobile-topbar\s*\{[^}]*display:\s*none", css)

    def test_mobile_topbar_shown_on_mobile(self, client):
        css = client.get("/static/css/style.css").data.decode()
        # Inside 768px media query, topbar should be display:flex
        assert re.search(r"\.mobile-topbar\s*\{[^}]*display:\s*flex", css)

    def test_hamburger_hidden_by_default(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.mobile-menu-btn\s*\{[^}]*display:\s*none", css)

    def test_sidebar_fixed_on_mobile(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.sidebar\s*\{[^}]*position:\s*fixed", css)

    def test_sidebar_open_transform(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.sidebar\.open\s*\{[^}]*transform:\s*translateX\(0\)", css)

    def test_modal_full_width_on_mobile(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.modal\s*\{[^}]*width:\s*100%\s*!important", css)

    def test_filter_row_column_on_mobile(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.filter-row\s*\{[^}]*flex-direction:\s*column", css)

    def test_shell_column_on_mobile(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.shell\s*\{[^}]*flex-direction:\s*column", css)

    def test_cards_single_column_at_480(self, client):
        css = client.get("/static/css/style.css").data.decode()
        # In the 480px query, cards should be 1fr
        match_480 = re.search(
            r"@media\s*\(\s*max-width\s*:\s*480px\s*\)\s*\{(.*?)\}\s*$",
            css, re.DOTALL,
        )
        assert match_480
        block = match_480.group(1)
        assert "grid-template-columns:1fr" in block or "grid-template-columns: 1fr" in block

    def test_touch_target_minimum_height(self, client):
        css = client.get("/static/css/style.css").data.decode()
        # Buttons should have min-height:40px on mobile
        assert "min-height:40px" in css or "min-height: 40px" in css


class TestMobileJS:
    """Verify the JS file contains mobile menu functions."""

    def test_js_loads(self, client):
        res = client.get("/static/js/app.js")
        assert res.status_code == 200

    def test_toggle_mobile_menu_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function toggleMobileMenu" in js

    def test_close_mobile_menu_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function closeMobileMenu" in js

    def test_nav_closes_mobile_menu(self, client):
        """Navigating should close the mobile menu."""
        js = client.get("/static/js/app.js").data.decode()
        assert "closeMobileMenu()" in js
        # Specifically inside nav function
        nav_match = re.search(r"function nav\(.*?\{(.*?)^}", js, re.DOTALL | re.MULTILINE)
        assert nav_match
        assert "closeMobileMenu" in nav_match.group(1)

    def test_resize_handler_closes_menu(self, client):
        """Resizing to desktop should close the mobile menu."""
        js = client.get("/static/js/app.js").data.decode()
        assert "resize" in js
        assert "closeMobileMenu" in js

    def test_overflow_hidden_on_open(self, client):
        """Body should get overflow hidden when menu opens."""
        js = client.get("/static/js/app.js").data.decode()
        assert "overflow" in js
        assert "'hidden'" in js or '"hidden"' in js


class TestMobileAccessibility:
    """Verify mobile accessibility requirements."""

    def test_hamburger_has_aria_label(self, client):
        html = client.get("/").data.decode()
        assert 'aria-label=' in html
        # Specifically the menu button
        assert 'aria-label="Open menu"' in html

    def test_sidebar_has_landmark(self, client):
        """Sidebar should be an aside element for screen readers."""
        html = client.get("/").data.decode()
        assert "<aside" in html

    def test_main_has_landmark(self, client):
        """Main content should use <main> element."""
        html = client.get("/").data.decode()
        assert "<main" in html
