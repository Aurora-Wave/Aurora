import os
import time
from multiprocessing import Process, Condition
import setproctitle
import webview

from dnb.domino import terminate_when_process_dies
from dnb.server import start_dash


def start():
    port = int(os.getenv("PORT", "8050"))
    host = os.getenv("HOST", "127.0.0.1")

    server_is_started = Condition()

    # Set the process title (for monitoring)
    setproctitle.setproctitle('dnb-webview')

    # Start the Dash server in a separate process
    p = Process(target=start_dash, args=(host, port, server_is_started,))
    p.start()

    # Kill this process if the Dash process dies
    terminate_when_process_dies(p)

    # Wait for Dash to be ready
    with server_is_started:
        server_is_started.wait()

    time.sleep(0.2)  # Optional delay

    # Open the Webview window
    webview.create_window('Dash', f'http://{host}:{port}')
    webview.start()

    # Cleanup when the window is closed
    p.terminate()
    exit(0)


if __name__ == '__main__':
    start()
