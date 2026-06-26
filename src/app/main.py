import os
import socket
import threading
import webbrowser
from src.app.flask_app import create_app

def find_available_port(start_port=5000, max_port=5100):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser(url):
    webbrowser.open_new_tab(url)

if __name__ == '__main__':
    app = create_app()
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"
    
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Timer(1.5, open_browser, args=[url]).start()

    print(f"Starting Paymenter (Hexagonal Architecture) on {url}")
    app.run(debug=True, port=port)