"""Tests for progressive disclosure UI rework.

Validates: sidebar with collapsible toggle, direct action buttons,
unified export modal, quick actions popover, PDF modal, tabbed settings,
collapsible panels, auto-hide empty panels, contextual actions.
"""
import re


# ── SIDEBAR LAYOUT ───────────────────────────────────────────────────────────

class TestSidebarLayout:
    """Sidebar should have Views + Actions sections with direct buttons."""

    def test_sidebar_has_collapse_toggle(self, client):
        html = client.get("/").data.decode()
        assert "sidebar-toggle" in html
        assert "toggleSidebar()" in html

    def test_sidebar_has_views_label(self, client):
        html = client.get("/").data.decode()
        assert ">Views<" in html

    def test_sidebar_has_actions_label(self, client):
        html = client.get("/").data.decode()
        assert ">Actions<" in html

    def test_sidebar_has_add_transaction(self, client):
        html = client.get("/").data.decode()
        assert "openAddModal()" in html
        assert "Add Transaction" in html

    def test_sidebar_has_transfer(self, client):
        html = client.get("/").data.decode()
        assert "openTransferModal()" in html
        assert "Transfer" in html

    def test_sidebar_has_quick_actions(self, client):
        html = client.get("/").data.decode()
        assert "toggleQuickActions" in html
        assert "Quick Actions" in html
        assert 'id="quick-actions-popover"' in html

    def test_sidebar_has_unified_export(self, client):
        html = client.get("/").data.decode()
        assert "openExportModal()" in html
        assert ">Export<" in html

    def test_export_functions_available(self, client):
        html = client.get("/").data.decode()
        assert "exportCSV(false)" in html
        assert "exportCSV(true)" in html
        assert "openPdfModal()" in html

    def test_month_menu_has_export_options(self, client):
        html = client.get("/").data.decode()
        assert "Export Month" in html
        assert "Export All" in html
        assert "Export PDF" in html

    def test_views_still_present(self, client):
        html = client.get("/").data.decode()
        assert "Dashboard" in html
        assert "Transactions" in html
        assert "Year Review" in html
        assert "Import CSV" in html
        assert "Settings" in html

    def test_nav_icons_wrapped(self, client):
        html = client.get("/").data.decode()
        assert "nav-icon" in html
        assert "nav-label-text" in html

    def test_data_tips_for_collapsed_mode(self, client):
        html = client.get("/").data.decode()
        assert 'data-tip="Dashboard"' in html
        assert 'data-tip="Settings"' in html


class TestSidebarCSS:
    """CSS for collapsible sidebar."""

    def test_sidebar_toggle_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar-toggle" in css

    def test_collapsed_sidebar_width(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar.collapsed" in css
        assert "--sidebar-w-col" in css

    def test_collapsed_hides_labels(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar.collapsed .nav-label-text" in css

    def test_nav_icon_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".nav-icon" in css

    def test_sidebar_bottom_styles(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".sidebar-bottom-row" in css
        assert ".sidebar-bottom-label" in css


# ── PDF MODAL ────────────────────────────────────────────────────────────────

class TestPdfModal:
    """PDF export modal should work correctly."""

    def test_pdf_modal_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="pdf-modal"' in html

    def test_pdf_include_transactions_checkbox(self, client):
        html = client.get("/").data.decode()
        assert 'id="pdf-include-txns"' in html

    def test_export_pdf_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportPdf" in js

    def test_open_pdf_modal_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function openPdfModal" in js

    def test_csv_export_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function exportCSV" in js


# ── SETTINGS LAYOUT ─────────────────────────────────────────────────────────

class TestSettingsLayout:
    """Settings page should have tabbed layout with 4 tabs."""

    def test_settings_has_tab_bar(self, client):
        html = client.get("/").data.decode()
        assert "settings-tabs" in html
        assert "settings-tab" in html

    def test_settings_has_general_tab(self, client):
        html = client.get("/").data.decode()
        assert "switchSettingsTab('general')" in html
        assert 'data-tab-pane="general"' in html

    def test_settings_has_categories_tab(self, client):
        html = client.get("/").data.decode()
        assert "switchSettingsTab('categories')" in html
        assert 'data-tab-pane="categories"' in html

    def test_settings_has_accounts_tab(self, client):
        html = client.get("/").data.decode()
        assert "switchSettingsTab('accounts')" in html
        assert 'data-tab-pane="accounts"' in html

    def test_settings_has_import_tab(self, client):
        html = client.get("/").data.decode()
        assert "switchSettingsTab('import')" in html
        assert 'data-tab-pane="import"' in html

    def test_switch_settings_tab_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function switchSettingsTab")
        fn_section = js[fn_start:fn_start + 300]
        assert "settings-tab-pane" in fn_section

    def test_settings_tab_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".settings-tabs" in css
        assert ".settings-tab.active" in css
        assert ".settings-tab-pane" in css

    def test_dashboard_layout_section(self, client):
        html = client.get("/").data.decode()
        assert "Dashboard Layout" in html

    def test_categories_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-settings"' in html
        settings_start = html.index('id="sec-settings"')
        settings_section = html[settings_start:]
        assert "Categories" in settings_section

    def test_budgets_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="budget-panel"' in html
        assert "Monthly Budgets" in html

    def test_goals_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="goals-panel"' in html
        assert "Savings Goals" in html

    def test_accounts_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="accounts-panel"' in html

    def test_schedules_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="schedules-panel"' in html
        assert "Scheduled Transactions" in html

    def test_groups_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="groups-panel"' in html
        assert "Category Groups" in html

    def test_learned_merchants_section(self, client):
        html = client.get("/").data.decode()
        assert "Learned Merchants" in html

    def test_import_rules_section(self, client):
        html = client.get("/").data.decode()
        assert "Import Rules" in html

    def test_show_budget_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showBudgetPanel")
        fn_section = js[fn_start:fn_start + 300]
        assert "scrollIntoView" in fn_section
        assert "switchSettingsTab" in fn_section

    def test_show_goals_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showGoalsPanel")
        fn_section = js[fn_start:fn_start + 300]
        assert "scrollIntoView" in fn_section
        assert "switchSettingsTab" in fn_section

    def test_show_accounts_scrolls(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function showAccountsPanel")
        fn_section = js[fn_start:fn_start + 300]
        assert "scrollIntoView" in fn_section
        assert "switchSettingsTab" in fn_section


# ── COLLAPSIBLE PANELS + AUTO-HIDE ──────────────────────────────────────────

class TestCollapsiblePanels:
    """Dashboard panels should be collapsible by clicking the title."""

    def test_init_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function initCollapsiblePanels" in js

    def test_collapsed_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel.panel-collapsed" in css

    def test_chevron_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel-collapse-chevron" in css

    def test_collapsed_hides_content(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel\.panel-collapsed\s*>\s*:not\(\.panel-title\)\s*\{[^}]*display:\s*none", css)

    def test_state_persisted_in_localstorage(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "'panelCollapsed'" in js
        assert "localStorage.setItem" in js

    def test_init_called_after_layout(self, client):
        js = client.get("/static/js/app.js").data.decode()
        layout_pos = js.index("applyDashboardLayout();")
        init_pos = js.index("initCollapsiblePanels()", layout_pos)
        assert init_pos > layout_pos

    def test_title_clickable(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel-title\s*\{[^}]*cursor:\s*pointer", css)

    def test_button_clicks_not_collapsed(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "e.target.closest('button')" in js


class TestAutoHideEmptyPanels:
    """Panels with no data should auto-hide."""

    def test_auto_hide_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function autoHideEmptyPanels" in js

    def test_auto_hidden_class_in_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".panel-auto-hidden" in css

    def test_auto_hidden_hides_panel(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert re.search(r"\.panel-auto-hidden\s*\{[^}]*display:\s*none\s*!important", css)

    def test_called_after_render(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "await Promise.all(renderPromises)" in js
        promise_pos = js.index("await Promise.all(renderPromises)")
        auto_hide_pos = js.index("autoHideEmptyPanels()", promise_pos)
        assert auto_hide_pos > promise_pos

    def test_checks_all_panels(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function autoHideEmptyPanels")
        fn_section = js[fn_start:fn_start + 2000]
        assert "'spending-by-category'" in fn_section
        assert "'donut-chart'" in fn_section
        assert "'averages'" in fn_section
        assert "'recent-txns'" in fn_section
        assert "'recurring'" in fn_section
        assert "'spending-trends'" in fn_section
        assert "'savings-goals'" in fn_section
        assert "'net-worth'" in fn_section
        assert "'account-balances'" in fn_section

    def test_skips_user_hidden(self, client):
        js = client.get("/static/js/app.js").data.decode()
        fn_start = js.index("function autoHideEmptyPanels")
        fn_section = js[fn_start:fn_start + 500]
        assert "panel-hidden" in fn_section


# ── CONTEXTUAL ACTIONS ──────────────────────────────────────────────────────

class TestContextualActions:
    """Dashboard gear buttons should navigate to settings and scroll."""

    def test_settings_button_in_spending_by_category(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="spending-by-category"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showBudgetPanel()" in panel_section

    def test_settings_button_in_savings_goals(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="savings-goals"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showGoalsPanel()" in panel_section

    def test_settings_button_in_account_balances(self, client):
        html = client.get("/").data.decode()
        panel_start = html.index('data-panel-id="account-balances"')
        panel_section = html[panel_start:panel_start + 500]
        assert "showAccountsPanel()" in panel_section

    def test_customize_button_on_dashboard(self, client):
        html = client.get("/").data.decode()
        assert "openCustomizeModal()" in html
        assert "Customize dashboard layout" in html


# ── INTEGRATION: ALL VIEWS STILL WORK ───────────────────────────────────────

class TestViewsIntegrity:
    """All 5 main views should still be present and navigable."""

    def test_dashboard_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-dashboard"' in html

    def test_transactions_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-transactions"' in html

    def test_year_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-year"' in html

    def test_import_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-import"' in html

    def test_settings_section(self, client):
        html = client.get("/").data.decode()
        assert 'id="sec-settings"' in html

    def test_nav_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function nav(id)" in js

    def test_dark_mode_toggle_still_present(self, client):
        html = client.get("/").data.decode()
        assert 'id="theme-toggle"' in html
        assert "toggleTheme()" in html

    def test_all_modals_present(self, client):
        html = client.get("/").data.decode()
        assert 'id="add-modal"' in html
        assert 'id="edit-modal"' in html
        assert 'id="bulk-cat-modal"' in html
        assert 'id="pdf-modal"' in html
        assert 'id="export-modal"' in html
        assert 'id="customize-modal"' in html
        assert 'id="transfer-modal"' in html
        assert 'id="contribute-modal"' in html
        assert 'id="rule-modal"' in html
        assert 'id="template-modal"' in html


# ── CARD ACCENT BARS ────────────────────────────────────────────────────────

class TestCardAccentBars:
    """Stat cards should have colored accent bars."""

    def test_accent_bar_in_html(self, client):
        html = client.get("/").data.decode()
        assert "card-accent-bar" in html

    def test_accent_bar_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".card-accent-bar" in css
        assert ".card-accent-bar.green" in css
        assert ".card-accent-bar.red" in css
        assert ".card-accent-bar.blue" in css


# ── EXPORT API STILL WORKS ──────────────────────────────────────────────────

class TestExportAPIStillWorks:
    """Export APIs should still function correctly."""

    def test_csv_export_endpoint(self, client):
        from tests.conftest import seed_transaction
        seed_transaction(client)
        res = client.get("/api/export?month=2026-03")
        assert res.status_code == 200
        assert "text/csv" in res.content_type or "application/octet-stream" in res.content_type

    def test_csv_export_all(self, client):
        from tests.conftest import seed_transaction
        seed_transaction(client)
        res = client.get("/api/export?month=")
        assert res.status_code == 200


# ── QUICK ACTIONS POPOVER ───────────────────────────────────────────────────

class TestQuickActionsPopover:
    """Quick Actions popover should be present and functional."""

    def test_quick_actions_button_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="quick-actions-btn"' in html

    def test_quick_actions_popover_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="quick-actions-popover"' in html
        assert "quick-actions-popover" in html

    def test_toggle_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function toggleQuickActions" in js

    def test_close_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function closeQuickActions" in js

    def test_popover_has_actions(self, client):
        html = client.get("/").data.decode()
        pop_start = html.index('id="quick-actions-popover"')
        pop_section = html[pop_start:pop_start + 800]
        assert "Add Transaction" in pop_section
        assert "Transfer" in pop_section
        assert "Export Data" in pop_section
        assert "Import CSV" in pop_section

    def test_popover_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".quick-actions-popover" in css
        assert ".quick-action-item" in css


# ── UNIFIED EXPORT MODAL ───────────────────────────────────────────────────

class TestUnifiedExportModal:
    """Unified export modal combines CSV and PDF export."""

    def test_export_modal_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-modal"' in html

    def test_export_format_select(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-format"' in html

    def test_export_scope_select(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-scope"' in html

    def test_open_export_modal_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function openExportModal" in js

    def test_on_export_format_change_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function onExportFormatChange" in js

    def test_do_export_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function doExport" in js

    def test_pdf_options_toggle(self, client):
        html = client.get("/").data.decode()
        assert 'id="export-pdf-options"' in html
        assert 'id="export-include-txns"' in html


# ── MONTH CONTEXT MENU ─────────────────────────────────────────────────────

class TestMonthContextMenu:
    """Month header should have a context menu for exports."""

    def test_month_menu_exists(self, client):
        html = client.get("/").data.decode()
        assert 'id="month-menu"' in html

    def test_toggle_month_menu_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function toggleMonthMenu" in js

    def test_close_month_menu_function(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function closeMonthMenu" in js

    def test_month_menu_has_csv_export(self, client):
        html = client.get("/").data.decode()
        menu_start = html.index('id="month-menu"')
        menu_section = html[menu_start:menu_start + 600]
        assert "exportCSV(false)" in menu_section

    def test_month_menu_has_pdf_export(self, client):
        html = client.get("/").data.decode()
        menu_start = html.index('id="month-menu"')
        menu_section = html[menu_start:menu_start + 600]
        assert "openPdfModal()" in menu_section

    def test_month_menu_has_all_export(self, client):
        html = client.get("/").data.decode()
        menu_start = html.index('id="month-menu"')
        menu_section = html[menu_start:menu_start + 600]
        assert "exportCSV(true)" in menu_section

    def test_month_menu_css(self, client):
        css = client.get("/static/css/style.css").data.decode()
        assert ".month-menu" in css
        assert ".month-menu-item" in css


# ── SCHEDULED TRANSACTION ACCOUNT SELECTOR ───────────────────────────────────

class TestScheduledTransactionAccountSelector:
    """Scheduled transaction add form should have an account dropdown."""

    def test_account_selector_exists_in_html(self, client):
        html = client.get("/").data.decode()
        assert 'id="new-sched-account"' in html

    def test_account_selector_is_select_element(self, client):
        html = client.get("/").data.decode()
        assert '<select id="new-sched-account"' in html

    def test_addSchedule_reads_account_selector(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "new-sched-account" in js
        assert "getElementById('new-sched-account')" in js

    def test_loadSchedulesSettings_populates_account_dropdown(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "schedAcctSel" in js or "new-sched-account" in js

    def test_schedule_list_shows_account(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "s.account" in js

    def test_schedule_api_accepts_account(self, client):
        client.post("/api/accounts-list", json={"name": "TestAcct", "account_type": "chequing"})
        res = client.post("/api/schedules", json={
            "name": "Rent", "type": "Expense", "category": "Rent",
            "amount": 1500, "account": "TestAcct",
            "frequency": "monthly", "next_due": "2026-06-01"
        })
        assert res.get_json()["ok"]
        schedules = client.get("/api/schedules").get_json()
        assert schedules[0]["account"] == "TestAcct"


# ── ACCOUNT EDIT/RENAME BUTTON ───────────────────────────────────────────────

class TestAccountEditButton:
    """Accounts in settings should have edit/rename buttons."""

    def test_editAccount_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function editAccount(" in js

    def test_editAccount_calls_patch(self, client):
        js = client.get("/static/js/app.js").data.decode()
        func_start = js.index("function editAccount(")
        func_body = js[func_start:func_start + 500]
        assert "PATCH" in func_body
        assert "/api/accounts-list/" in func_body

    def test_editAccount_refreshes_dropdowns(self, client):
        js = client.get("/static/js/app.js").data.decode()
        func_start = js.index("function editAccount(")
        func_body = js[func_start:func_start + 600]
        assert "populateModalAccountDropdowns" in func_body

    def test_account_row_has_edit_button(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "editAccount(" in js
        assert "✏️" in js

    def test_rename_account_api_works(self, client):
        client.post("/api/accounts-list", json={"name": "Old Name", "account_type": "savings"})
        accounts = client.get("/api/accounts-list").get_json()
        aid = accounts[0]["id"]
        res = client.patch(f"/api/accounts-list/{aid}", json={"name": "New Name"})
        assert res.get_json()["ok"]
        updated = client.get("/api/accounts-list").get_json()
        assert updated[0]["name"] == "New Name"

    def test_rename_cascades_to_transactions(self, client):
        from tests.conftest import seed_transaction
        client.post("/api/accounts-list", json={"name": "AcctA", "account_type": "chequing"})
        seed_transaction(client, account="AcctA")
        accounts = client.get("/api/accounts-list").get_json()
        client.patch(f"/api/accounts-list/{accounts[0]['id']}", json={"name": "AcctB"})
        txns = client.get("/api/transactions?month=2026-03").get_json()
        assert txns[0]["account"] == "AcctB"


# ── CATEGORY GROUP REASSIGNMENT ──────────────────────────────────────────────

class TestCategoryGroupReassignment:
    """Categories within groups should have a dropdown to reassign to another group."""

    def test_reassignCategory_function_exists(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "function reassignCategory(" in js

    def test_reassignCategory_calls_patch(self, client):
        js = client.get("/static/js/app.js").data.decode()
        func_start = js.index("function reassignCategory(")
        func_body = js[func_start:func_start + 300]
        assert "PATCH" in func_body
        assert "/api/categories/" in func_body
        assert "group_id" in func_body

    def test_group_display_has_reassign_select(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "group-reassign-select" in js
        assert "reassignCategory(" in js

    def test_ungrouped_categories_shown(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "Ungrouped" in js

    def test_reassign_category_via_api(self, client):
        # Ensure we have two groups with categories
        groups = client.get("/api/category-groups").get_json()
        named_groups = [g for g in groups if g["id"] is not None]
        if len(named_groups) < 2:
            client.post("/api/category-groups", json={"name": "TestGroup"})
            groups = client.get("/api/category-groups").get_json()
            named_groups = [g for g in groups if g["id"] is not None]
        # Find groups that have categories
        groups_with_cats = [g for g in named_groups if g["categories"]]
        if not groups_with_cats:
            # Assign a category to the first group so we can test moving it
            cats = client.get("/api/categories").get_json()
            expense_cat = [c for c in cats if c["type"] == "Expense"][0]
            client.patch(f"/api/categories/{expense_cat['id']}", json={"group_id": named_groups[0]["id"]})
            groups = client.get("/api/category-groups").get_json()
            named_groups = [g for g in groups if g["id"] is not None]
            groups_with_cats = [g for g in named_groups if g["categories"]]
        source_group = groups_with_cats[0]
        target_group = [g for g in named_groups if g["id"] != source_group["id"]][0]
        cat_id = source_group["categories"][0]["id"]
        # Move category
        res = client.patch(f"/api/categories/{cat_id}", json={"group_id": target_group["id"]})
        assert res.get_json()["ok"]
        # Verify it moved
        updated_groups = client.get("/api/category-groups").get_json()
        target = [g for g in updated_groups if g["id"] == target_group["id"]][0]
        assert any(c["id"] == cat_id for c in target["categories"])

    def test_reassign_to_ungrouped_via_api(self, client):
        groups = client.get("/api/category-groups").get_json()
        named_groups = [g for g in groups if g["id"] is not None]
        # Ensure at least one group has a category
        groups_with_cats = [g for g in named_groups if g["categories"]]
        if not groups_with_cats:
            cats = client.get("/api/categories").get_json()
            expense_cat = [c for c in cats if c["type"] == "Expense"][0]
            client.patch(f"/api/categories/{expense_cat['id']}", json={"group_id": named_groups[0]["id"]})
            groups = client.get("/api/category-groups").get_json()
            groups_with_cats = [g for g in groups if g["id"] is not None and g["categories"]]
        source_group = groups_with_cats[0]
        cat_id = source_group["categories"][0]["id"]
        res = client.patch(f"/api/categories/{cat_id}", json={"group_id": None})
        assert res.get_json()["ok"]
        # Verify it's now ungrouped
        updated_groups = client.get("/api/category-groups").get_json()
        ungrouped = [g for g in updated_groups if g["id"] is None]
        assert ungrouped and any(c["id"] == cat_id for c in ungrouped[0]["categories"])

    def test_group_options_rendered_for_each_category(self, client):
        js = client.get("/static/js/app.js").data.decode()
        assert "groupOptions.map" in js
