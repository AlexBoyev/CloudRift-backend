import os
import sys
import time
import subprocess
import requests
from flask import Flask, request, Response
from prometheus_flask_exporter import PrometheusMetrics

# Configuration
# The C Server will run internally on 5050
C_SERVER_PORT = 5050
# The Wrapper listens on 5001 (What Kubernetes expects)
WRAPPER_PORT = 5001
C_BINARY_PATH = "./stack-service"

app = Flask(__name__)
# Enable Monitoring
metrics = PrometheusMetrics(app)


def start_c_server():
    """Starts the C binary in the background on port 5050"""
    print(f"Starting C Server on port {C_SERVER_PORT}...")

    # We pass the port as an environment variable (Standard practice)
    # If your C code ignores PORT env, you might need to change this logic
    env = os.environ.copy()
    env["PORT"] = str(C_SERVER_PORT)

    # Start the process
    process = subprocess.Popen(
        [C_BINARY_PATH],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    # Give it 2 seconds to wake up
    time.sleep(2)
    return process


# Start C server immediately
c_process = start_c_server()


@app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    """Forwards EVERYTHING to the C Server"""
    url = f"http://localhost:{C_SERVER_PORT}/{path}"

    try:
        # Forward the request to the C Server
        resp = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False
        )

        # Return the response from C Server back to the user
        headers = [(name, value) for (name, value) in resp.headers.items()]
        return Response(resp.content, resp.status_code, headers)

    except requests.exceptions.ConnectionError:
        return Response("Error: C Server is not responding", status=502)


if __name__ == '__main__':
    # Listen on all interfaces
    app.run(host='0.0.0.0', port=WRAPPER_PORT)