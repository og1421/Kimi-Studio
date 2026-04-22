"""
server.py — Backend da Kimi IDE
=================================
Inicia um servidor local Flask que expõe o kimi_client.py
como uma API e serve a interface HTML da IDE.

Como executar:
    python3 server.py

Acesse no navegador:
    http://localhost:8000
"""

import os
import json
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory

# Carrega o cliente Kimi existente
from kimi_client import get_client, SYSTEM_PROMPT, MODEL

app = Flask(__name__)
PROJECT_DIR = Path(__file__).parent

# Extensões permitidas no explorador de arquivos
ALLOWED_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".env.example",
    ".js", ".html", ".css", ".ts", ".yaml", ".yml", ".toml", ".sh"
}

HIDDEN = {".venv", "__pycache__", ".git", ".DS_Store"}

MAX_FILE_SIZE_BYTES = 512 * 1024   # 512 KB — evita travar o contexto do modelo
MAX_MESSAGES        = 40           # limite de mensagens no histórico de chat


# ─── Servir frontend ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(PROJECT_DIR, "index.html")


# ─── API: arquivos ─────────────────────────────────────────────────────────────

@app.route("/api/files")
def list_files():
    """Lista arquivos do projeto (não ocultos e com extensão permitida)."""
    files = []
    for f in sorted(PROJECT_DIR.iterdir()):
        if f.name in HIDDEN or f.name.startswith(".venv"):
            continue
        if f.is_file() and (f.suffix in ALLOWED_EXTENSIONS or f.name == ".env.example"):
            files.append({
                "name": f.name,
                "ext": f.suffix,
                "size": f.stat().st_size,
            })
    return jsonify(files)


@app.route("/api/file/read", methods=["POST"])
def read_file():
    """Lê o conteúdo de um arquivo do projeto."""
    data = request.get_json()
    filename = data.get("filename", "")
    filepath = PROJECT_DIR / filename

    # Segurança: não permite sair da pasta do projeto
    try:
        filepath.resolve().relative_to(PROJECT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Acesso negado"}), 403

    try:
        if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
            return jsonify({"error": "Arquivo muito grande (limite: 512 KB)"}), 413
        content = filepath.read_text(encoding="utf-8")
        return jsonify({"content": content, "filename": filename})
    except Exception as e:
        return jsonify({"error": "Não foi possível ler o arquivo"}), 400


@app.route("/api/file/save", methods=["POST"])
def save_file():
    """Salva o conteúdo editado de um arquivo."""
    data = request.get_json()
    filename = data.get("filename", "")
    content = data.get("content", "")
    filepath = PROJECT_DIR / filename

    try:
        filepath.resolve().relative_to(PROJECT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Acesso negado"}), 403

    try:
        filepath.write_text(content, encoding="utf-8")
        return jsonify({"success": True})
    except Exception:
        return jsonify({"error": "Não foi possível salvar o arquivo"}), 400


# ─── API: chat com streaming (SSE) ─────────────────────────────────────────────

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    Recebe o histórico de mensagens e faz streaming da resposta do Kimi
    usando Server-Sent Events (SSE).
    """
    data = request.get_json()
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Nenhuma mensagem fornecida"}), 400

    # Limita histórico para evitar custos excessivos de API
    if len(messages) > MAX_MESSAGES:
        messages = [messages[0]] + messages[-(MAX_MESSAGES - 1):]

    def generate():
        try:
            client = get_client()
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=4096,
                temperature=1,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "http://localhost:8000",
        },
    )


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("KIMI_IDE_PORT", 8000))
    print(f"\n🌙 Kimi IDE iniciada!")
    print(f"   Acesse: http://localhost:{port}")
    print(f"   Modelo: {MODEL}")
    print(f"   Pasta : {PROJECT_DIR}")
    print("\n   Pressione Ctrl+C para encerrar.\n")
    app.run(debug=False, port=port, threaded=True)
