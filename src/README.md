# Passo a Passo de Execução

# Passo a Passo de Execução — MoneyCoach (Reserva de Emergência + Metas)

## Setup do Ollama (Local)

```bash
# 1) Instalar o Ollama
# https://ollama.com

# 2) Baixar um modelo leve (recomendado para PCs com pouca RAM)
ollama pull llama3.2:3b

# 3) Testar se está funcionando
ollama run llama3.2:3b "Responda apenas: OK"
```

## Código Completo

Todo o código-fonte está no arquivo:
- src/app.py

O app:
- usa Streamlit como interface

- chama o modelo local via Ollama

- salva memória local em perfil.json (criado na primeira execução)

- lê os arquivos-base do curso dentro de data/

## Dependências

```bash
pip install streamlit pandas requests
```

## Como Rodar

```bash
# 1) (Opcional, recomendado) criar ambiente virtual
python -m venv .venv

# Ativar (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 2) Instalar dependências
pip install streamlit pandas requests

# 3) Garantir que o Ollama está rodando
# (no Windows, normalmente ele roda como app/serviço ao abrir o Ollama)
# opcional:
ollama serve

# 4) Rodar o app
streamlit run .\src\app.py
```

## Estrutura do Projeto (resumo)
```text
Projeto_Final_MoneyCoach/
├─ src/
│  └─ app.py
├─ data/
│  ├─ perfil_investidor.json
│  ├─ transacoes.csv
│  └─ produtos_financeiros.json
└─ perfil.json   # criado automaticamente (memória local)
```

## Evidência de Execução

### Print 1 — App rodando
![App rodando](evidencias/moneycoach1.png)

### Print 2 — App rodando
![Terminal](evidencias/moneycoach2.png)
