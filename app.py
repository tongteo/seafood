import requests
import json
import sqlite3
import os
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

OPENROUTER_API_KEY = "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"

# Initialize SQLite database for chat history
def init_db():
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            model TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

conversation_history = {}

def save_message_to_db(user_id, role, content, model=None):
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversations (user_id, role, content, model)
        VALUES (?, ?, ?, ?)
    ''', (user_id, role, content, model))
    conn.commit()
    conn.close()

def load_conversation_from_db(user_id):
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp ASC
    ''', (user_id,))
    messages = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    conn.close()
    return messages

@app.route("/generate", methods=["POST"])
def generate_content():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        prompt = data.get("prompt")
        model_name = data.get("model", "deepseek/deepseek-chat-v3-0324:free")
        stream = data.get("stream", False)

        if not user_id or not prompt:
            return jsonify({"error": "User ID or prompt is missing"}), 400

        if user_id not in conversation_history:
            conversation_history[user_id] = []

        # Add user's message to history
        conversation_history[user_id].append({"role": "user", "content": prompt})

        messages = conversation_history[user_id]

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "<YOUR_SITE_URL>",
            "X-Title": "<YOUR_SITE_NAME>",
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": stream
        }

        if stream:
            def generate():
                with requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload),
                    stream=True
                ) as r:
                    r.raise_for_status()
                    full_response_content = ""
                    for chunk in r.iter_content(chunk_size=None):
                        if chunk:
                            try:
                                # OpenRouter sends data in 'data: {json}' format
                                chunk_str = chunk.decode('utf-8')
                                for line in chunk_str.splitlines():
                                    if line.startswith('data: '):
                                        json_data = line[len('data: '):]
                                        if json_data.strip() == '[DONE]':
                                            continue
                                        data_obj = json.loads(json_data)
                                        if 'choices' in data_obj and len(data_obj['choices']) > 0:
                                            delta = data_obj['choices'][0]['delta']
                                            if 'content' in delta:
                                                content = delta['content']
                                                full_response_content += content
                                                yield content
                            except json.JSONDecodeError:
                                print(f"Could not decode JSON from chunk: {chunk_str}")
                                continue
                    # Add bot's full response to history
                    conversation_history[user_id].append({"role": "assistant", "content": full_response_content})

            return Response(generate(), mimetype='text/plain')
        else:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"]
            # Add bot's response to history
            conversation_history[user_id].append({"role": "assistant", "content": generated_text})
            return jsonify({"generated_content": generated_text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if user_id:
            # Clear conversation history in memory
            conversation_history[user_id] = []
            # Clear conversation history in database
            conn = sqlite3.connect('chat_history.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return jsonify({"message": "New conversation started"}), 200
        return jsonify({"error": "User ID is missing"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_history", methods=["POST"])
def get_history():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if user_id:
            messages = load_conversation_from_db(user_id)
            return jsonify({"history": messages}), 200
        return jsonify({"error": "User ID is missing"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_conversations", methods=["GET"])
def get_conversations():
    try:
        conn = sqlite3.connect('chat_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, MIN(timestamp) as first_message, MAX(timestamp) as last_message, COUNT(*) as message_count
            FROM conversations 
            GROUP BY user_id 
            ORDER BY last_message DESC
        ''')
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                "user_id": row[0],
                "first_message": row[1],
                "last_message": row[2],
                "message_count": row[3]
            })
        conn.close()
        return jsonify({"conversations": conversations}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_conversation_detail", methods=["POST"])
def get_conversation_detail():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if user_id:
            conn = sqlite3.connect('chat_history.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content, timestamp, model FROM conversations 
                WHERE user_id = ? 
                ORDER BY timestamp ASC
            ''', (user_id,))
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[2],
                    "model": row[3]
                })
            conn.close()
            return jsonify({"messages": messages}), 200
        return jsonify({"error": "User ID is missing"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


