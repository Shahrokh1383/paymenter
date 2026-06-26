import os
import socket
import threading
import webbrowser
from flask import Flask, redirect, url_for
from database import init_db

# Legacy Controllers (Still active for Phase 5 migration)
from controllers.dashboard_controller import dashboard_bp
from controllers.api_controller import api_bp
from controllers.gateway_controller import gateway_bp

# NEW Hexagonal Architecture Controller (Migrated in Phase 3)
from src.ledger.infrastructure.web.transaction_controller import transaction_bp 
from src.checkout.infrastructure.web.api_controller import api_bp as checkout_api_bp
from src.checkout.infrastructure.web.gateway_controller import gateway_bp as checkout_gateway_bp

def find_available_port(start_port=5000, max_port=5100):
    """Finds the first available port from start_port to max_port."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port # Fallback if all ports are busy

def open_browser(url):
    """Opens the webbrowser after a short delay."""
    webbrowser.open_new_tab(url)

def create_app():
    app = Flask(__name__)
    app.secret_key = "super_secret_simulator_key"

    with app.app_context():
        init_db()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transaction_bp) 
    app.register_blueprint(checkout_api_bp)
    app.register_blueprint(checkout_gateway_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.currencies'))

    return app

if __name__ == '__main__':
    app = create_app()
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"
    
    # Prevent double browser opening in Flask debug mode
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Timer(1.5, open_browser, args=[url]).start()

    print(f"Starting Paymenter on {url}")
    app.run(debug=True, port=port)