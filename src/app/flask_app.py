import os
from flask import Flask, redirect, url_for
from src.common.infrastructure.database import Database
from src.app.di_container import DIContainer

def create_app():
    # Resolve paths to the root 'templates' and 'static' folders
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    app.secret_key = "super_secret_simulator_key"

    # 1. Initialize Database Schema
    Database.initialize()

    # 2. Initialize DI Container and attach to App Context
    app.di_container = DIContainer()

    # 3. Register Hexagonal Blueprints
    from src.identity.infrastructure.web.dashboard_controller import dashboard_bp
    from src.ledger.infrastructure.web.transaction_controller import transaction_bp
    from src.checkout.infrastructure.web.gateway_controller import gateway_bp
    from src.checkout.infrastructure.web.api_controller import api_bp
    from src.ledger.infrastructure.web.schemas.transaction_api_controller import transaction_api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(gateway_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(transaction_api_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.currencies'))

    return app