"""
examples.py — Exemplos de uso do kimi_client
=============================================
Execute diretamente para ver os exemplos em ação:

    python examples.py
"""

from kimi_client import chat_once, chat_stream


def exemplo_basico() -> None:
    resposta = chat_once("Explique o que é computação quântica em 3 linhas.")
    print(resposta)


def exemplo_streaming() -> None:
    for chunk in chat_stream("Escreva um haiku sobre inteligência artificial."):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    print("─── Exemplo básico ───────────────────────────────")
    exemplo_basico()
    print("\n─── Exemplo streaming ────────────────────────────")
    exemplo_streaming()
