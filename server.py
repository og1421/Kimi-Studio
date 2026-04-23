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

import atexit
import errno
import functools
import logging
import os
import json
import re
import secrets
import stat
import sys
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
import openai

from kimi_client import get_client, MODEL

app = Flask(__name__)
# .absolute() torna o path absoluto sem seguir symlinks do próprio script.
# .resolve() seguiria o link e apontaria para o diretório real do target,
# expondo um path diferente do que o operador espera ao usar um symlink.
_PROJECT_ROOT = Path(__file__).parent.absolute()
# dir_fd para openat() — disponível em todo POSIX (Linux/macOS); ausente no Windows.
# os.supports_dir_fd cobre funções de alto nível, não os.open — usa-se sys.platform.
_USE_DIR_FD: bool = sys.platform != "win32"
_dir_fd: int = os.open(str(_PROJECT_ROOT), os.O_RDONLY) if _USE_DIR_FD else -1
if _dir_fd >= 0:
    atexit.register(os.close, _dir_fd)
_port = int(os.getenv("KIMI_IDE_PORT", 8000))
_API_TOKEN = secrets.token_hex(32)      # token de sessão gerado no startup; injetado no HTML


def _require_token(f):
    """Decorator: rejeita requests sem o token de sessão correto."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Kimi-Token", "")
        if not secrets.compare_digest(token, _API_TOKEN):
            return jsonify({"error": "Não autorizado"}), 401
        return f(*args, **kwargs)
    return decorated

ALLOWED_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".env.example",
    ".js", ".html", ".css", ".ts", ".yaml", ".yml", ".toml", ".sh"
}

HIDDEN = {".venv", "__pycache__", ".git", ".DS_Store"}

MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB
MAX_MESSAGES = 40

# O_NOFOLLOW rejeita atomicamente o acesso se o componente final do path for um symlink
# (POSIX: Linux/macOS). No Windows getattr devolve 0 — sem efeito, mas symlinks lá
# exigem privilégios de administrador, reduzindo o risco.
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

# PRESSUPOSTO DE SEGURANÇA: o diretório do projeto (_PROJECT_ROOT) não é gravável
# por atacantes. Se um adversário puder criar hardlinks dentro dele, poderá apontar
# para arquivos fora do projeto (ex: /etc/shadow). O_NOFOLLOW e openat() não
# detectam hardlinks; a mitigação de userspace é st_nlink == 1 (ver read_file /
# save_file). No Linux, /proc/sys/fs/protected_hardlinks = 1 (padrão desde 3.6)
# impede que usuários sem privilégio criem hardlinks para arquivos que não possuem.


# Nomes reservados do Windows (CON, NUL, COM1…9, LPT1…9, etc.).
# No Windows, os.open("NUL", ...) abre o dispositivo do sistema — bypass de segurança.
_WIN_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", re.IGNORECASE)


def _safe_filename(filename: str) -> bool:
    """
    Valida o filename para uso com os.open(filename, ..., dir_fd=_dir_fd).

    Rejeita: string vazia, . e .., separadores de path, null bytes e nomes
    reservados do Windows (NUL, CON, COM1…). A contenção final é feita pelo
    kernel: openat(_dir_fd) + O_NOFOLLOW abre atomicamente relativo ao diretório
    já fixado, sem TOCTOU.
    """
    if not filename or filename in (".", ".."):
        return False
    if "/" in filename or "\\" in filename or "\x00" in filename:
        return False
    if sys.platform == "win32" and _WIN_RESERVED.match(filename):
        return False
    return True


def _open_project_file(filename: str, flags: int) -> int:
    """
    Abre filename dentro de _PROJECT_ROOT de forma segura.

    POSIX (Linux/macOS): usa openat(_dir_fd) + O_NOFOLLOW — abertura atômica relativa
    ao diretório já fixado; o kernel rejeita symlinks sem janela de TOCTOU.

    Windows: dir_fd não é suportado. Usa os.path.join (não pathlib /) para evitar o
    comportamento documentado do pathlib em que um RHS absoluto sobrescreve a base
    (Path("base") / "C:/foo" → Path("C:/foo")). Valida com os.path.commonpath como
    defesa em profundidade contra regressões futuras em _safe_filename.
    Symlinks exigem privilégios de administrador no Windows, reduzindo o risco prático.
    """
    if _USE_DIR_FD:
        return os.open(filename, flags | _O_NOFOLLOW, dir_fd=_dir_fd)

    root = str(_PROJECT_ROOT)
    target = os.path.normpath(os.path.join(root, filename))
    try:
        common = os.path.commonpath([target, root])
    except ValueError:
        # commonpath levanta ValueError em Windows se os paths estiverem em drives diferentes
        raise OSError(errno.ELOOP, "Acesso negado", filename)
    if common != root:
        raise OSError(errno.ELOOP, "Acesso negado", filename)
    return os.open(target, flags)


# ─── Servir frontend ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    html = (_PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    injection = f'<script>const _KIMI_TOKEN = {json.dumps(_API_TOKEN)};</script>'
    return html.replace("</head>", injection + "\n</head>", 1)


# ─── API: arquivos ─────────────────────────────────────────────────────────────

@app.route("/api/files")
@_require_token
def list_files():
    """Lista arquivos do projeto (não ocultos e com extensão permitida)."""
    files = []
    for f in sorted(_PROJECT_ROOT.iterdir()):
        if f.name in HIDDEN or f.name.startswith(".venv"):
            continue
        if f.is_symlink():
            continue
        if f.is_file() and (f.suffix in ALLOWED_EXTENSIONS or f.name == ".env.example"):
            files.append({
                "name": f.name,
                "ext": f.suffix,
                "size": f.stat().st_size,
            })
    return jsonify(files)


@app.route("/api/file/read", methods=["POST"])
@_require_token
def read_file():
    """Lê o conteúdo de um arquivo do projeto."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename") or ""

    if not _safe_filename(filename):
        return jsonify({"error": "Acesso negado"}), 403

    if Path(filename).suffix not in ALLOWED_EXTENSIONS and filename != ".env.example":
        return jsonify({"error": "Tipo de arquivo não permitido"}), 403

    fd = -1
    try:
        fd = _open_project_file(filename, os.O_RDONLY)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            return jsonify({"error": "Acesso negado"}), 403
        if st.st_size > MAX_FILE_SIZE_BYTES:
            return jsonify({"error": "Arquivo muito grande (limite: 512 KB)"}), 413
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = -1
            content = f.read()
        return jsonify({"content": content, "filename": filename})
    except UnicodeDecodeError:
        return jsonify({"error": "Arquivo não é UTF-8 válido"}), 415
    except OSError as e:
        if e.errno == errno.ELOOP:
            return jsonify({"error": "Acesso negado"}), 403
        if e.errno == errno.ENOENT:
            return jsonify({"error": "Arquivo não encontrado"}), 404
        logging.exception("Erro ao ler arquivo: %s", filename)
        return jsonify({"error": "Não foi possível ler o arquivo"}), 400
    finally:
        if fd >= 0:
            os.close(fd)


@app.route("/api/file/save", methods=["POST"])
@_require_token
def save_file():
    """Salva o conteúdo editado de um arquivo existente."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename") or ""
    content  = data.get("content") or ""

    if not _safe_filename(filename):
        return jsonify({"error": "Acesso negado"}), 403

    if Path(filename).suffix not in ALLOWED_EXTENSIONS and filename != ".env.example":
        return jsonify({"error": "Tipo de arquivo não permitido"}), 403

    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        return jsonify({"error": "Conteúdo excede o limite permitido (512 KB)"}), 413

    # Fase 1: valida o arquivo alvo sem modificá-lo.
    val_fd = -1
    try:
        val_fd = _open_project_file(filename, os.O_RDONLY)
        st = os.fstat(val_fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            return jsonify({"error": "Acesso negado"}), 403
    except OSError as e:
        if e.errno == errno.ELOOP:
            return jsonify({"error": "Acesso negado"}), 403
        if e.errno == errno.ENOENT:
            return jsonify({"error": "Arquivo não encontrado"}), 404
        logging.exception("Erro ao validar arquivo: %s", filename)
        return jsonify({"error": "Não foi possível salvar o arquivo"}), 400
    finally:
        if val_fd >= 0:
            os.close(val_fd)

    # Fase 2: escreve em arquivo temporário e renomeia atomicamente.
    # Se houver falha entre escrita e rename, o original permanece intacto.
    tmp_name = f".{filename}.tmp"
    tmp_fd = -1
    try:
        tmp_fd = _open_project_file(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = -1
            f.write(content)
        os.replace(_PROJECT_ROOT / tmp_name, _PROJECT_ROOT / filename)
        return jsonify({"success": True})
    except OSError:
        logging.exception("Erro ao salvar arquivo: %s", filename)
        return jsonify({"error": "Não foi possível salvar o arquivo"}), 400
    finally:
        if tmp_fd >= 0:
            os.close(tmp_fd)
        try:
            (_PROJECT_ROOT / tmp_name).unlink(missing_ok=True)
        except OSError:
            pass


# ─── API: chat com streaming (SSE) ─────────────────────────────────────────────

@app.route("/api/chat/stream", methods=["POST"])
@_require_token
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
    print(f"   Pasta : {_PROJECT_ROOT}")
    print("\n   Pressione Ctrl+C para encerrar.\n")
    app.run(host="127.0.0.1", port=_port, debug=False, threaded=True)
