import os
import sys
import time
import subprocess
import requests
from flask import Flask, request, Response
from prometheus_flask_exporter import PrometheusMetrics

C_SERVER_PORT = 5050
WRAPPER_PORT = 5001
C_BINARY_PATH = "./stack-service"

app = Flask(__name__)
metrics = PrometheusMetrics(app)

def start_c_server():
    print(f"Starting C Server on port {C_SERVER_PORT}...")
    env = os.environ.copy()
    env["PORT"] = str(C_SERVER_PORT)

    process = subprocess.Popen(
        [C_BINARY_PATH],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    time.sleep(2)
    return process

c_process = start_c_server()

@app.route('/', defaults={'path': ''}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route('/<path:path>', methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    url = f"http://localhost:{C_SERVER_PORT}/{path}"
    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False
        )
        headers = [(name, value) for (name, value) in resp.headers.items()]
        return Response(resp.content, resp.status_code, headers)
    except requests.exceptions.ConnectionError:
        return Response("Error: C Server is not responding", status=502)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=WRAPPER_PORT)