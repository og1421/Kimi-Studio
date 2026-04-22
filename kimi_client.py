"""
kimi_client.py — Cliente Python para Kimi K2.6 via Moonshot AI API
====================================================================
Modelo  : kimi-k2.6
API URL : https://api.moonshot.ai/v1  (compatível com OpenAI SDK)
Docs    : https://platform.moonshot.ai/docs

Como usar:
    python kimi_client.py                  → chat interativo
    python kimi_client.py --once "Sua pergunta"  → resposta única
    python kimi_client.py --stream "Sua pergunta" → resposta em streaming
"""

import os
import sys
import argparse
from pathlib import Path

# Carrega variáveis do .env automaticamente
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv opcional; a chave pode ser exportada via shell

from openai import OpenAI

# ─── Configuração ──────────────────────────────────────────────────────────────

API_KEY  = os.getenv("MOONSHOT_API_KEY")
BASE_URL = "https://api.moonshot.ai/v1"
MODEL    = "kimi-k2.6"

SYSTEM_PROMPT = (
    "Você é o Kimi, um assistente de IA criado pela Moonshot AI. "
    "Seja preciso, útil e direto ao ponto."
)

# ─── Cliente ───────────────────────────────────────────────────────────────────

def get_client() -> OpenAI:
    """Cria e retorna o cliente Moonshot (compatível com OpenAI SDK)."""
    if not API_KEY:
        print(
            "\n[ERRO] MOONSHOT_API_KEY não encontrada.\n"
            "  1. Copie .env.example → .env\n"
            "  2. Preencha sua chave em: https://platform.moonshot.ai/console/api-keys\n"
            "  3. Ou exporte via terminal:  export MOONSHOT_API_KEY=sk-...\n"
        )
        sys.exit(1)

    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ─── Funções de chat ───────────────────────────────────────────────────────────

def chat_once(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Envia uma única mensagem e retorna a resposta completa."""
    client = get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=4096,
        temperature=1,
    )
    return response.choices[0].message.content


def chat_stream(prompt: str, system: str = SYSTEM_PROMPT) -> None:
    """Envia uma mensagem e imprime a resposta token a token (streaming)."""
    client = get_client()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=4096,
        temperature=1,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()  # nova linha ao final


def chat_interactive() -> None:
    """Modo chat interativo com histórico de conversa."""
    client  = get_client()
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        history.append({"role": "user", "content": user_input})

        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=history,
                max_tokens=4096,
                temperature=1,
                stream=True,
            )

            print("\nKimi: ", end="", flush=True)
            full_reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    print(delta, end="", flush=True)
                    full_reply += delta
            print("\n")

            history.append({"role": "assistant", "content": full_reply})

        except Exception as e:
            print(f"\n[ERRO na API] {e}\n")


# ─── Exemplo de uso via código (importável) ────────────────────────────────────

def exemplo_basico() -> None:
    """Exemplo simples de chamada direta — útil ao importar este módulo."""
    resposta = chat_once("Explique o que é computação quântica em 3 linhas.")
    print(resposta)


def exemplo_streaming() -> None:
    """Exemplo de streaming — útil ao importar este módulo."""
    chat_stream("Escreva um haiku sobre inteligência artificial.")


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cliente Python para Kimi K2.6 (Moonshot AI)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--once", metavar="PROMPT",
        help="Envia uma única mensagem e imprime a resposta"
    )
    group.add_argument(
        "--stream", metavar="PROMPT",
        help="Envia uma mensagem e exibe a resposta em streaming"
    )
    args = parser.parse_args()

    if args.once:
        print(chat_once(args.once))
    elif args.stream:
        chat_stream(args.stream)
    else:
        chat_interactive()
