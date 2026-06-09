from flask import Flask
from database import init_db
from controllers.dashboard_controller import dashboard_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = "super_secret_simulator_key" # Needed for flash messages

    # Initialize the database
    with app.app_context():
        init_db()

    # Register Blueprints (Controllers)
    app.register_blueprint(dashboard_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.currencies'))

    return app

if __name__ == '__main__':
    from flask import url_for # Import here just for the redirect above to work cleanly
    app = create_app()
    app.run(debug=True)