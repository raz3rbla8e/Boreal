from canada_finance.routes.main import main_bp
from canada_finance.routes.transactions import transactions_bp
from canada_finance.routes.import_export import import_export_bp
from canada_finance.routes.summary import summary_bp
from canada_finance.routes.settings import settings_bp
from canada_finance.routes.rules import rules_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(import_export_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(rules_bp)
