"""
kimi_client.py — Cliente Python para Kimi K2.6 via Moonshot AI API
====================================================================
Modelo  : kimi-k2.6
API URL : https://api.moonshot.ai/v1  (compatível com OpenAI SDK)
Docs    : https://platform.moonshot.ai/docs

Como usar:
    python kimi_client.py                        → chat interativo
    python kimi_client.py --once "Sua pergunta"  → resposta única
    python kimi_client.py --stream "Sua pergunta" → resposta em streaming
"""

import atexit
import os
import re
import stat
import sys
import argparse
import threading
import unicodedata
from collections import deque
from pathlib import Path
from typing import Generator

import httpx

def _warn_env_permissions(path: Path) -> None:
    """Avisa se .env puder ser lido por grupo ou outros usuários no sistema."""
    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            print(
                f"[aviso de segurança] {path} está legível por outros usuários "
                f"(modo {oct(mode & 0o777)}). Execute: chmod 600 {path}",
                file=sys.stderr,
            )
    except OSError:
        pass  # arquivo inexistente ou inacessível — ignorar


try:
    from dotenv import load_dotenv
    try:
        _env_path = Path(__file__).parent / ".env"
    except NameError:
        _env_path = Path.cwd() / ".env"  # frozen / REPL: tenta o diretório de trabalho
    _warn_env_permissions(_env_path)
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv opcional; a chave pode ser exportada via shell

import openai
from openai import OpenAI

# ─── Configuração ──────────────────────────────────────────────────────────────

BASE_URL = "https://api.moonshot.ai/v1"
MODEL = "kimi-k2.6"
DEFAULT_MAX_TOKENS = 8192
MAX_HISTORY_TURNS = 40  # pares user/assistant mantidos no modo interativo

SYSTEM_PROMPT = (
    "Você é o Kimi, um assistente de IA criado pela Moonshot AI. "
    "Seja preciso, útil e direto ao ponto."
)

# ─── Sanitização de saída ─────────────────────────────────────────────────────

# Cobre sequências CSI, OSC, DCS, ESC simples, etc.
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|][^\x07]*(?:\x07|\x1b\\))")

# Categorias Unicode seguras para exibição em terminal:
#   L* = letras, N* = números, P* = pontuação, S* = símbolos, Z* = separadores
# Bloqueados explicitamente: Cc (controles C0/C1, inclui BEL/CR/DEL),
#   Cf (formato: bidirectional overrides, zero-width), Co (uso privado), Cs (surrogates)
_SAFE_CATEGORIES = frozenset("LNPSZ")


def _sanitize(text: str) -> str:
    """Remove sequências ANSI e caracteres de controle da saída do modelo."""
    text = _ANSI_ESCAPE.sub("", text)
    return "".join(
        c for c in text
        if c in "\n\t" or unicodedata.category(c)[0] in _SAFE_CATEGORIES
    )


def _split_carry(text: str) -> tuple[str, str]:
    """
    Retorna (safe, carry) para streaming seguro entre chunks.

    Procura o último ESC no texto. Se ele NÃO iniciar uma sequência ANSI
    completa (pode ser o começo de uma sequência cortada no limite do chunk),
    move esse sufixo para carry e retorna apenas o prefixo seguro para
    sanitização. O carry é prefixado ao próximo chunk antes de repetir.

    Sequências ANSI têm no máximo ~64 bytes; tails maiores são processados
    como texto normal (não podem ser sequências parciais).
    """
    last_esc = text.rfind("\x1b")
    if last_esc == -1:
        return text, ""
    if _ANSI_ESCAPE.match(text, last_esc):
        return text, ""
    tail = text[last_esc:]
    if len(tail) <= 64:
        return text[:last_esc], tail
    return text, ""



# ─── Cliente (singleton) ───────────────────────────────────────────────────────

_client: OpenAI | None = None
_client_lock = threading.Lock()


def _close_client() -> None:
    """Fecha o pool de conexões HTTP ao encerrar o processo."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client() -> OpenAI:
    """Retorna o cliente Moonshot reutilizável (singleton thread-safe)."""
    global _client
    with _client_lock:
        if _client is None:
            api_key = os.getenv("MOONSHOT_API_KEY")
            if not api_key:
                raise ValueError(
                    "MOONSHOT_API_KEY não encontrada. "
                    "Copie .env.example para .env e preencha sua chave, "
                    "ou exporte via terminal: export MOONSHOT_API_KEY=sk-..."
                )
            _client = OpenAI(
                api_key=api_key,
                base_url=BASE_URL,
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            )
            atexit.register(_close_client)
    return _client


# ─── Funções de chat ───────────────────────────────────────────────────────────

def chat_once(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Envia uma única mensagem e retorna a resposta completa."""
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=1,  # restrição do modelo: único valor aceito pela API
    )
    if not response.choices:
        return ""
    return _sanitize(response.choices[0].message.content or "")


def chat_stream(prompt: str, system: str = SYSTEM_PROMPT) -> Generator[str, None, None]:
    """Gera os chunks da resposta token a token (streaming)."""
    stream = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=1,  # restrição do modelo: único valor aceito pela API
        stream=True,
    )
    carry = ""
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        safe, carry = _split_carry(carry + delta)
        out = _sanitize(safe)
        if out:
            yield out
    if carry:
        yield _sanitize(carry)


def chat_interactive() -> None:
    """Modo chat interativo com histórico de conversa."""
    # system_msgs é fixo; conversation acumula turnos user/assistant
    # deque(maxlen) descarta os turnos mais antigos em O(1) — sem slice, sem reconstrução
    # Nota: o limite é por número de turnos, não por tokens. Mensagens muito longas
    # podem estourar o context window antes de atingir MAX_HISTORY_TURNS.
    system_msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation: deque[dict] = deque(maxlen=MAX_HISTORY_TURNS * 2)

    print(f"\n🌙 Kimi K2.6 — Chat Interativo")
    print(f"   Modelo  : {MODEL}")
    print(f"   API URL : {BASE_URL}")
    print("   Digite 'sair' ou pressione Ctrl+C para encerrar.\n")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nEncerrando. Até logo!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"sair", "exit", "quit", "bye"}:
            print("Encerrando. Até logo!")
            break

        send_msgs = system_msgs + list(conversation) + [{"role": "user", "content": user_input}]

        try:
            stream = get_client().chat.completions.create(
                model=MODEL,
                messages=send_msgs,
                max_tokens=DEFAULT_MAX_TOKENS,
                temperature=1,  # restrição do modelo: único valor aceito pela API
                stream=True,
            )

            print("\nKimi: ", end="", flush=True)
            full_reply = ""
            carry = ""
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                safe, carry = _split_carry(carry + delta)
                out = _sanitize(safe)
                if out:
                    print(out, end="", flush=True)
                    full_reply += out
            if carry:
                out = _sanitize(carry)
                if out:
                    print(out, end="", flush=True)
                    full_reply += out
            print("\n")

            # Só persiste no histórico após sucesso, e apenas se o reply não for vazio
            if not full_reply:
                print("[aviso: resposta vazia após sanitização — turno não salvo]\n")
                continue

            if len(conversation) + 2 > (conversation.maxlen or 0):
                evicting = len(conversation) + 2 - (conversation.maxlen or 0)
                turns_kept = MAX_HISTORY_TURNS - evicting // 2
                print(
                    f"   [aviso: histórico cheio — "
                    f"{evicting // 2} turno(s) antigo(s) descartado(s), "
                    f"{turns_kept} turno(s) mantido(s)]\n"
                )
            conversation.append({"role": "user", "content": user_input})
            conversation.append({"role": "assistant", "content": full_reply})

        except openai.AuthenticationError:
            print("\n[ERRO] Falha de autenticação. Verifique sua MOONSHOT_API_KEY.\n")
        except openai.RateLimitError:
            print("\n[ERRO] Limite de requisições atingido. Tente novamente em instantes.\n")
        except openai.APIStatusError as e:
            print(f"\n[ERRO] {type(e).__name__} (código {e.status_code})\n")
        except Exception as e:
            print(f"\n[ERRO] {type(e).__name__}\n")


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cliente Python para Kimi K2.6 (Moonshot AI)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--once", metavar="PROMPT",
        help="Envia uma única mensagem e imprime a resposta",
    )
    group.add_argument(
        "--stream", metavar="PROMPT",
        help="Envia uma mensagem e exibe a resposta em streaming",
    )
    args = parser.parse_args()

    try:
        if args.once:
            print(chat_once(args.once))
        elif args.stream:
            for chunk in chat_stream(args.stream):
                print(chunk, end="", flush=True)
            print()
        else:
            chat_interactive()
    except ValueError as e:
        # Chave ausente ou inválida antes de qualquer chamada à API
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)
    except openai.AuthenticationError:
        print("[ERRO] Falha de autenticação. Verifique sua MOONSHOT_API_KEY.", file=sys.stderr)
        sys.exit(1)
    except openai.RateLimitError:
        print("[ERRO] Limite de requisições atingido. Tente novamente em instantes.", file=sys.stderr)
        sys.exit(1)
    except openai.APIStatusError as e:
        print(f"[ERRO] {type(e).__name__} (código {e.status_code})", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERRO] {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
