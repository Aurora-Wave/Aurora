from multiprocessing import Condition
import setproctitle

#Parche
import sys
import os

# Add the parent directory (src/) to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from main import app  # Import the Dash app from main.py
from dnb.domino import terminate_when_parent_process_dies

def start_dash(host: str, port: int, server_is_started: Condition, debug: bool = False):
    # Set process name for system monitoring
    setproctitle.setproctitle('dnb-dash')

    if not debug:
        # Kill this process if its parent dies (only in production)
        terminate_when_parent_process_dies()

        # Notify parent process that the Dash app is ready
        if server_is_started is not None:
            with server_is_started:
                server_is_started.notify()

        # Run the Dash app in production mode
        app.run_server(debug=False, host=host, port=port)

    else:
        # Run in development mode (useful for testing)
        app.run_server(debug=True, host=host, port=port)

# Optional: allow testing server.py directly (without webview)
if __name__ == '__main__':
    import os
    port = int(os.getenv("PORT", "8050"))
    host = os.getenv("HOST", "127.0.0.1")
    server_is_started = None

    start_dash(host, port, server_is_started, debug=True)
