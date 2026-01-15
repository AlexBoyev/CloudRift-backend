from flask import Flask, jsonify, request
from flask_cors import CORS
import db_client

app = Flask(__name__)
CORS(app)

# --- HELPER: GET CURRENT STATE ---
def get_current_state():
    """Fetches full graph from DB and formats it for the UI."""
    nodes_data = db_client.execute_query("SELECT label FROM nodes", fetch=True)
    edges_data = db_client.execute_query("SELECT source, target FROM edges", fetch=True)

    # Convert DB rows to UI format
    nodes = [r['label'] for r in (nodes_data or [])]
    edges = [[r['source'], r['target']] for r in (edges_data or [])]

    return {"nodes": nodes, "edges": edges}


# --- ROUTES ---

@app.route('/data', methods=['GET'])
def get_graph():
    return jsonify(get_current_state())


@app.route('/add-node', methods=['POST'])
def add_node():
    data = request.json
    label = data.get('label')

    if not label:
        return jsonify({"error": "Label is required"}), 400

    # FIXED: Python uses .upper(), not .toUpperCase()
    label = str(label).strip().upper()

    success = db_client.execute_query(
        "INSERT INTO nodes (label) VALUES (%s) ON CONFLICT DO NOTHING",
        (label,)
    )

    if success:
        return jsonify({"status": "processed", "graph": get_current_state()})
    else:
        return jsonify({"error": "Database error"}), 500


@app.route('/add-edge', methods=['POST'])
def add_edge():
    data = request.json
    u = data.get('from')
    v = data.get('to')

    if not u or not v:
        return jsonify({"error": "From and To are required"}), 400

    u = str(u).strip().upper()
    v = str(v).strip().upper()

    # Ensure Nodes Exist (Canonical IDs)
    db_client.execute_query("INSERT INTO nodes (label) VALUES (%s) ON CONFLICT DO NOTHING", (u,))
    db_client.execute_query("INSERT INTO nodes (label) VALUES (%s) ON CONFLICT DO NOTHING", (v,))

    success = db_client.execute_query(
        "INSERT INTO edges (source, target) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (u, v)
    )

    if success:
        return jsonify({"status": "processed", "graph": get_current_state()})
    else:
        return jsonify({"error": "Database error"}), 500


@app.route('/delete-node', methods=['POST'])
def delete_node():
    data = request.json
    label = data.get('label')

    if not label:
        return jsonify({"error": "Label is required"}), 400

    label = str(label).strip().upper()

    # Delete associated edges first to maintain integrity
    db_client.execute_query(
        "DELETE FROM edges WHERE source = %s OR target = %s",
        (label, label)
    )

    success = db_client.execute_query(
        "DELETE FROM nodes WHERE label = %s",
        (label,)
    )

    if success:
        return jsonify({"status": "deleted", "graph": get_current_state()})
    else:
        return jsonify({"error": "Database error"}), 500


@app.route('/delete-edge', methods=['POST'])
def delete_edge():
    data = request.json
    u = data.get('from')
    v = data.get('to')

    if not u or not v:
        return jsonify({"error": "From and To are required"}), 400

    u = str(u).strip().upper()
    v = str(v).strip().upper()

    success = db_client.execute_query(
        "DELETE FROM edges WHERE source = %s AND target = %s",
        (u, v)
    )

    if success:
        return jsonify({"status": "edge_deleted", "graph": get_current_state()})
    else:
        return jsonify({"error": "Database error"}), 500


@app.route('/clear', methods=['POST'])
def clear_graph():
    db_client.execute_query("DELETE FROM edges")
    success = db_client.execute_query("DELETE FROM nodes")

    if success:
        return jsonify({"status": "cleared", "graph": {"nodes": [], "edges": []}})
    else:
        return jsonify({"error": "Database error"}), 500


@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "Graph Service Active"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)