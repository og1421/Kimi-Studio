# Kimi K2.6 — Cliente & IDE

**Modelo:** `kimi-k2.6`  
**Provedor:** Moonshot AI  
**API:** OpenAI-compatível · `https://api.moonshot.ai/v1`  
**Console:** [platform.moonshot.ai](https://platform.moonshot.ai)  
**Licença:** MIT

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
# Crie e ative o ambiente virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# Instale as dependências
pip install -r requirements.txt
```

Pacotes instalados:

| Pacote | Função |
|---|---|
| `openai` | SDK para chamar a API Moonshot (compatível com OpenAI) |
| `python-dotenv` | Carrega automaticamente o arquivo `.env` |
| `httpx` | Cliente HTTP usado internamente pelo SDK |
| `flask` | Servidor web local para a Kimi IDE |

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

> ⚠️ **Nunca** commite o arquivo `.env` em repositórios públicos. Ele já está protegido pelo `.gitignore`.

### 3.3 Alternativa: exportar via terminal

```bash
# macOS / Linux
export MOONSHOT_API_KEY=sk-SuaChaveAquiCompleta

# Windows (PowerShell)
$env:MOONSHOT_API_KEY = "sk-SuaChaveAquiCompleta"

# Windows (CMD)
set MOONSHOT_API_KEY=sk-SuaChaveAquiCompleta
```

---

## 4. Kimi IDE — Interface Visual

A **Kimi IDE** é uma interface web local que roda no navegador e permite editar arquivos, conversar com o Kimi K2.6 e aplicar sugestões de código com um clique.

### 4.1 Iniciar a IDE

```bash
python3 server.py
```

Acesse no navegador:

```
http://localhost:8000
```

### 4.2 Funcionalidades

**Explorador de arquivos (sidebar esquerda)**
Exibe todos os arquivos do projeto. Clique em qualquer arquivo para abri-lo no editor.

**Editor de código (centro)**
Editor completo com numeração de linhas, suporte a Tab e atalho `Cmd+S` / `Ctrl+S` para salvar.

**Botões de ação rápida**
Com um arquivo aberto, use os botões na barra do editor para acionar o Kimi automaticamente:

| Botão | O que faz |
|---|---|
| 🔍 Revisar código | Analisa problemas de lógica, estilo e segurança |
| 🐛 Corrigir bugs | Encontra e corrige bugs, mostrando o código corrigido |
| 💬 Explicar | Explica o que o código faz, função por função |
| ✨ Refatorar | Reescreve o código melhorando qualidade e legibilidade |
| 📝 Gerar docstrings | Gera documentação para todas as funções e classes |

**Chat com streaming (painel direito)**
Converse livremente com o Kimi sobre o arquivo aberto. As respostas aparecem em tempo real, token a token. Quando o Kimi sugere um bloco de código, aparece o botão **"✅ Aplicar no editor"** para substituir o conteúdo do editor com um clique.

### 4.3 Atalhos

| Atalho | Ação |
|---|---|
| `Cmd+S` / `Ctrl+S` | Salvar arquivo |
| `Tab` | Inserir 4 espaços no editor |
| `Enter` (no chat) | Enviar mensagem |
| `Shift+Enter` | Nova linha no chat |

### 4.4 Porta customizada

Para usar uma porta diferente da 8000:

```bash
KIMI_IDE_PORT=9000 python3 server.py
```

---

## 5. Usar via terminal (kimi_client.py)

### Chat interativo

```bash
python3 kimi_client.py
```

### Resposta única

```bash
python3 kimi_client.py --once "Explique o que é uma rede neural em 3 linhas"
```

### Streaming

```bash
python3 kimi_client.py --stream "Escreva um poema sobre o mar"
```

---

## 6. Usar como módulo Python

```python
from kimi_client import chat_once, chat_stream

# Resposta completa
resposta = chat_once("O que é o modelo Kimi K2.6?")
print(resposta)

# Streaming
chat_stream("Liste 5 linguagens de programação e suas aplicações.")
```

### Exemplo com system prompt personalizado

```python
from kimi_client import chat_once

resposta = chat_once(
    prompt="Analise esta função: def soma(a, b): return a + b",
    system="Você é um engenheiro de software sênior especialista em Python."
)
print(resposta)
```

---

## 7. Estrutura do projeto

```
Kimi-K2.6-Setup/
├── .env.example      ← Template da API key (copie para .env)
├── .env              ← Sua chave real (NÃO compartilhe)
├── .gitignore        ← Protege .env e .venv do git
├── requirements.txt  ← Dependências Python
├── kimi_client.py    ← Cliente principal (terminal)
├── server.py         ← Backend da Kimi IDE (Flask + SSE)
├── index.html        ← Frontend da Kimi IDE
├── LICENSE           ← Licença MIT
└── README.md         ← Esta documentação
```

---

## 8. Parâmetros da API

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `model` | string | Sempre `"kimi-k2.6"` |
| `messages` | array | Histórico de mensagens (`system`, `user`, `assistant`) |
| `max_tokens` | int | Máximo de tokens na resposta (recomendado: `4096`) |
| `temperature` | int | Deve ser `1` (único valor aceito pelo modelo) |
| `stream` | bool | `True` para resposta em tempo real |

---

## 9. Solução de problemas

**Erro: `MOONSHOT_API_KEY não encontrada`**  
→ Verifique se o arquivo `.env` existe e contém a chave correta.

**Erro: `AuthenticationError`**  
→ API key inválida ou expirada. Gere uma nova em [platform.moonshot.ai](https://platform.moonshot.ai/console/api-keys).

**Erro 429 — insufficient balance**  
→ Sem saldo na conta. Recarregue em [platform.moonshot.ai](https://platform.moonshot.ai) → Billing → Recharge.

**Erro: `invalid temperature`**  
→ O Kimi K2.6 aceita apenas `temperature=1`. O cliente já está configurado corretamente.

**Erro: `ModuleNotFoundError: No module named 'openai'`**  
→ Ative o ambiente virtual e instale as dependências: `pip install -r requirements.txt`.

**IDE não abre no navegador**  
→ Verifique se o `server.py` está rodando e acesse `http://localhost:8000`.

---

## 10. Links úteis

- [Console Moonshot AI](https://platform.moonshot.ai) — Gerenciar chaves e créditos
- [Documentação oficial da API](https://platform.moonshot.ai/docs) — Referência completa
- [Modelo no Hugging Face](https://huggingface.co/moonshotai/Kimi-K2.6) — Pesos open-source
- [Repositório Kimi K2](https://github.com/MoonshotAI/Kimi-K2) — Código e papers
