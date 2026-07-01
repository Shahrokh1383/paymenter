import os

def find_ghost_data():
    terms = ['toman', 'Toman', 'TOMAN', 'IRT']
    found = False
    for root, dirs, files in os.walk('.'):
        # Ignore virtual environments and git/cache folders
        if any(ignore in root for ignore in ['.git', '__pycache__', 'venv', '.venv', 'env']):
            continue
        for file in files:
            if file.endswith(('.py', '.html', '.js', '.sql')):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for term in terms:
                            if term in content:
                                print(f"[!] FOUND '{term}' IN: {path}")
                                found = True
                except Exception:
                    pass
    if not found:
        print("[OK] No hardcoded 'toman' found in source files.")

find_ghost_data()