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

import logging
import os
import json
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
import openai


from kimi_client import get_client, MODEL

app = Flask(__name__)
PROJECT_DIR = Path(__file__).parent
_port = int(os.getenv("KIMI_IDE_PORT", 8000))

ALLOWED_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".env.example",
    ".js", ".html", ".css", ".ts", ".yaml", ".yml", ".toml", ".sh"
}

HIDDEN = {".venv", "__pycache__", ".git", ".DS_Store"}

MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB
MAX_MESSAGES = 40


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
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    filepath = PROJECT_DIR / filename

    try:
        filepath.resolve().relative_to(PROJECT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Acesso negado"}), 403

    if filepath.suffix not in ALLOWED_EXTENSIONS and filepath.name != ".env.example":
        return jsonify({"error": "Tipo de arquivo não permitido"}), 403

    try:
        if not filepath.exists():
            return jsonify({"error": "Arquivo não encontrado"}), 404
        if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
            return jsonify({"error": "Arquivo muito grande (limite: 512 KB)"}), 413
        content = filepath.read_text(encoding="utf-8")
        return jsonify({"content": content, "filename": filename})
    except Exception:
        logging.exception("Erro ao ler arquivo: %s", filename)
        return jsonify({"error": "Não foi possível ler o arquivo"}), 400


@app.route("/api/file/save", methods=["POST"])
def save_file():
    """Salva o conteúdo editado de um arquivo existente."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    content = data.get("content", "")
    filepath = PROJECT_DIR / filename

    try:
        filepath.resolve().relative_to(PROJECT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Acesso negado"}), 403

    if filepath.suffix not in ALLOWED_EXTENSIONS and filepath.name != ".env.example":
        return jsonify({"error": "Tipo de arquivo não permitido"}), 403

    if not filepath.exists():
        return jsonify({"error": "Arquivo não encontrado"}), 404

    try:
        filepath.write_text(content, encoding="utf-8")
        return jsonify({"success": True})
    except Exception:
        logging.exception("Erro ao salvar arquivo: %s", filename)
        return jsonify({"error": "Não foi possível salvar o arquivo"}), 400


# ─── API: chat com streaming (SSE) ─────────────────────────────────────────────

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    Recebe o histórico de mensagens e faz streaming da resposta do Kimi
    usando Server-Sent Events (SSE).
    """
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Nenhuma mensagem fornecida"}), 400

    # Remove mensagens não-sistema com conteúdo vazio (evita BadRequestError da API)
    messages = [
        m for m in messages
        if m.get("role") == "system" or m.get("content", "").strip()
    ]

    if not messages:
        return jsonify({"error": "Nenhuma mensagem válida fornecida"}), 400

    # Mantém system prompt (índice 0) + últimas (MAX_MESSAGES - 1) mensagens
    if len(messages) > MAX_MESSAGES:
        head = messages[:1]
        tail = messages[1:]
        messages = head + tail[-(MAX_MESSAGES - 1):]

    def generate():
        try:
            stream = get_client().chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=8192,
                temperature=1,  # restrição do modelo: único valor aceito pela API
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'text': delta})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except openai.AuthenticationError:
            logging.error("Falha de autenticação na API Moonshot (chave inválida ou ausente)")
            yield f"data: {json.dumps({'error': 'Erro de autenticação. Verifique a MOONSHOT_API_KEY.'})}\n\n"
        except Exception:
            logging.exception("Erro no streaming SSE")
            yield f"data: {json.dumps({'error': 'Erro interno ao processar a resposta.'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": f"http://localhost:{_port}",
        },
    )


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n🌙 Kimi IDE iniciada!")
    print(f"   Acesse: http://localhost:{_port}")
    print(f"   Modelo: {MODEL}")
    print(f"   Pasta : {PROJECT_DIR}")
    print("\n   Pressione Ctrl+C para encerrar.\n")
    app.run(debug=False, port=_port, threaded=True)
