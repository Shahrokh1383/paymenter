from flask import Flask, redirect, url_for
from database import init_db
from controllers.dashboard_controller import dashboard_bp
from controllers.transaction_controller import transaction_bp
from controllers.api_controller import api_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = "super_secret_simulator_key"

    with app.app_context():
        init_db()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.currencies'))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)