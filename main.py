from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv()

app = Flask(__name__)
CORS(app)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
model = SentenceTransformer("all-MiniLM-L6-v2")

@app.route("/search", methods=["POST", "OPTIONS"])
def search():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response
    data = request.json
    query = data.get("query", "")
    embedding = model.encode(query).tolist()
    result = supabase.rpc("match_transcripts", {
        "query_embedding": embedding,
        "match_threshold": 0.3,
        "match_count": 5
    }).execute()
    return jsonify(result.data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
