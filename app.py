from flask import Flask
from database import init_db

def create_app():
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)

    # Initialize the database when the app starts
    with app.app_context():
        init_db()

    @app.route('/')
    def index():
        return "Paymenter is running and database is initialized!"

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)