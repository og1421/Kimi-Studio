# Kimi K2.6 — Guia de Configuração e Uso

**Modelo:** `kimi-k2.6`  
**Provedor:** Moonshot AI  
**API:** OpenAI-compatível · `https://api.moonshot.ai/v1`  
**Console:** [platform.moonshot.ai](https://platform.moonshot.ai)

---

## O que é o Kimi K2.6?

O **Kimi K2.6** é o modelo mais avançado da Moonshot AI, lançado em abril de 2026. É um modelo de linguagem de arquitetura MoE (Mixture of Experts) com 1 trilhão de parâmetros totais e 32 bilhões de parâmetros ativos. Destaca-se por:

- Codificação contínua de longa duração (até 13 horas ininterruptas)
- Tarefas autônomas de agente (agentic workflows)
- API totalmente compatível com o SDK da OpenAI

---

## 1. Pré-requisitos

- Python **3.9** ou superior
- Conta no [Moonshot AI Platform](https://platform.moonshot.ai)

---

## 2. Instalação das dependências

No terminal, dentro desta pasta, execute:

```bash
pip install -r requirements.txt
```

Isso instala:

| Pacote | Função |
|---|---|
| `openai` | SDK para chamar a API Moonshot (compatível com OpenAI) |
| `python-dotenv` | Carrega automaticamente o arquivo `.env` |
| `httpx` | Cliente HTTP usado internamente pelo SDK |

---

## 3. Configuração da API Key

### 3.1 Obter sua chave

1. Acesse [platform.moonshot.ai/console/api-keys](https://platform.moonshot.ai/console/api-keys)
2. Crie uma nova chave clicando em **"New API Key"**
3. Copie o valor gerado (começa com `sk-`)

### 3.2 Criar o arquivo `.env`

```bash
cp .env.example .env
```

Abra o arquivo `.env` e substitua o valor placeholder pela sua chave real:

```env
MOONSHOT_API_KEY=sk-SuaChaveAquiCompleta
```

> ⚠️ **Nunca** commite o arquivo `.env` em repositórios públicos. Ele já está no `.gitignore` por padrão se você usar um projeto Git.

### 3.3 Alternativa: exportar via terminal

Se preferir não usar o arquivo `.env`, exporte a variável diretamente no terminal:

```bash
# macOS / Linux
export MOONSHOT_API_KEY=sk-SuaChaveAquiCompleta

# Windows (PowerShell)
$env:MOONSHOT_API_KEY = "sk-SuaChaveAquiCompleta"

# Windows (CMD)
set MOONSHOT_API_KEY=sk-SuaChaveAquiCompleta
```

---

## 4. Como executar

### Chat interativo (padrão)

Inicia uma conversa com histórico, onde você digita mensagens livremente:

```bash
python kimi_client.py
```

Exemplo de sessão:

```
🌙 Kimi K2.6 — Chat Interativo
   Modelo  : kimi-k2.6
   API URL : https://api.moonshot.ai/v1
   Digite 'sair' ou pressione Ctrl+C para encerrar.

Você: Quais são as vantagens da computação quântica?

Kimi: A computação quântica oferece...
```

### Resposta única (--once)

Envia uma pergunta e exibe a resposta completa:

```bash
python kimi_client.py --once "Explique o que é uma rede neural em 3 linhas"
```

### Resposta em streaming (--stream)

Exibe a resposta sendo gerada token a token em tempo real:

```bash
python kimi_client.py --stream "Escreva um poema sobre o mar"
```

---

## 5. Usar como módulo Python

Você pode importar as funções diretamente em seus scripts:

```python
from kimi_client import chat_once, chat_stream

# Resposta completa de uma vez
resposta = chat_once("O que é o modelo Kimi K2.6?")
print(resposta)

# Resposta em streaming
chat_stream("Liste 5 linguagens de programação e suas aplicações.")
```

### Exemplo com system prompt personalizado

```python
from kimi_client import chat_once

resposta = chat_once(
    prompt="Analise os prós e contras desta função Python: def soma(a, b): return a + b",
    system="Você é um engenheiro de software sênior especialista em Python. Seja técnico e preciso."
)
print(resposta)
```

### Exemplo de conversa com histórico manual

```python
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1"
)

messages = [
    {"role": "system", "content": "Você é um assistente especialista em finanças."},
    {"role": "user",   "content": "O que é um ETF?"},
]

response = client.chat.completions.create(
    model="kimi-k2.6",
    messages=messages,
    max_tokens=2048,
    temperature=0.6,
)

reply = response.choices[0].message.content
print(reply)

# Adiciona a resposta ao histórico e continua a conversa
messages.append({"role": "assistant", "content": reply})
messages.append({"role": "user", "content": "Quais são os ETFs mais populares do Brasil?"})

response2 = client.chat.completions.create(
    model="kimi-k2.6",
    messages=messages,
    max_tokens=2048,
)
print(response2.choices[0].message.content)
```

---

## 6. Parâmetros da API

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `model` | string | Sempre `"kimi-k2.6"` |
| `messages` | array | Histórico de mensagens (`system`, `user`, `assistant`) |
| `max_tokens` | int | Máximo de tokens na resposta (padrão recomendado: `4096`) |
| `temperature` | float | Criatividade: `0.0` (determinístico) a `1.0` (criativo). Padrão: `0.6` |
| `stream` | bool | `True` para receber resposta em tempo real token a token |
| `top_p` | float | Amostragem nucleus (alternativa ao temperature) |

---

## 7. Estrutura dos arquivos

```
Kimi K/
├── .env.example      ← Template da API key (copie para .env)
├── .env              ← Sua chave real (NÃO compartilhe)
├── requirements.txt  ← Dependências Python
├── kimi_client.py    ← Cliente principal (chat, streaming, interativo)
└── README.md         ← Esta documentação
```

---

## 8. Solução de problemas

**Erro: `MOONSHOT_API_KEY não encontrada`**  
→ Verifique se o arquivo `.env` existe e contém a chave correta, ou exporte via terminal.

**Erro: `AuthenticationError`**  
→ Sua API key está inválida ou expirada. Gere uma nova em [platform.moonshot.ai](https://platform.moonshot.ai/console/api-keys).

**Erro: `RateLimitError`**  
→ Você atingiu o limite de requisições. Aguarde alguns segundos e tente novamente.

**Erro: `ModuleNotFoundError: No module named 'openai'`**  
→ Execute `pip install -r requirements.txt` antes de rodar o script.

---

## 9. Links úteis

- [Console Moonshot AI](https://platform.moonshot.ai) — Gerenciar chaves e créditos
- [Documentação oficial da API](https://platform.moonshot.ai/docs) — Referência completa
- [Modelo no Hugging Face](https://huggingface.co/moonshotai/Kimi-K2.6) — Pesos open-source
- [Repositório Kimi K2](https://github.com/MoonshotAI/Kimi-K2) — Código e papers
