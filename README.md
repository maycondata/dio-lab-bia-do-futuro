# 💰 MoneyCoach — Agente Financeiro de Reserva de Emergência

Agente financeiro inteligente desenvolvido com IA Generativa para ajudar usuários a **definir, planejar e acompanhar sua reserva de emergência** de forma simples, transparente e sem alucinações.

---

## O Problema

A maioria das pessoas sabe que precisa de uma reserva de emergência, mas não sabe:
- **Quanto** juntar (qual a meta ideal?)
- **Como** juntar (qual plano de aporte?)
- **Se está no caminho certo** (como acompanhar o progresso?)

## A Solução

O MoneyCoach é um agente consultivo que:

1. Coleta o contexto do usuário (gastos essenciais, renda, reserva atual)
2. Define a meta (3 a 12 meses de gastos essenciais, padrão 6)
3. Calcula o plano de aporte mensal e o prazo estimado
4. Acompanha o progresso e recalcula quando há atualizações
5. Sempre exibe **"Como calculei"** — sem inventar dados

---

## Funcionalidades

- **Cálculo de meta** com base em meses configuráveis (3–12)
- **Estimativa de gastos essenciais** via histórico de transações
- **Simulação de prazo** dado aporte mensal informado
- **Sugestão de produtos** para guardar a reserva (apenas os da base de dados)
- **Memória local** em `perfil.json` com persistência entre sessões
- **Guardrails anti-alucinação**: o agente nunca inventa taxas, rentabilidades ou produtos

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Interface | Streamlit |
| LLM | Ollama (llama3.2:3b) |
| Linguagem | Python 3 |
| Dados | JSON + CSV locais |

---

## Como Rodar

```bash
# 1. Instalar dependências
pip install streamlit pandas requests

# 2. Baixar o modelo local (requer Ollama instalado)
ollama pull llama3.2:3b

# 3. Rodar o app
streamlit run src/app.py
```

> O arquivo `perfil.json` é criado automaticamente na primeira execução como memória do agente.

---

## Estrutura do Projeto

```
├── data/
│   ├── perfil_investidor.json       # Perfil e metas do cliente
│   ├── transacoes.csv               # Histórico de transações
│   ├── produtos_financeiros.json    # Produtos disponíveis para reserva
│   └── historico_atendimento.csv    # Histórico de atendimentos
│
├── docs/
│   ├── 01-documentacao-agente.md   # Caso de uso, persona e arquitetura
│   ├── 02-base-conhecimento.md     # Estratégia de dados e integração
│   ├── 03-prompts.md               # System prompt, exemplos e edge cases
│   ├── 04-metricas.md              # Testes e métricas de qualidade
│   └── 05-pitch.md                 # Roteiro do pitch
│
├── src/
│   └── app.py                      # Aplicação principal (Streamlit + Ollama)
│
└── perfil.json                     # Memória local do agente (gerado automaticamente)
```

---

## Segurança e Anti-Alucinação

- Respostas baseadas **somente** nos dados fornecidos ou presentes na base
- Estimativas são sempre sinalizadas como **ESTIMATIVA**
- Cálculos feitos em Python e injetados no contexto (o LLM não recalcula)
- Produtos sugeridos restritos ao `produtos_financeiros.json`
- Agente recusa perguntas fora do escopo com redirecionamento educado

---

## Resultados dos Testes

| Teste | Resultado |
|-------|-----------|
| Cálculo da meta (6 meses) | ✅ Correto |
| Prazo estimado com aporte | ✅ Correto |
| Gastos essenciais ausentes | ✅ Oferece cenários / estima |
| Pergunta fora do escopo | ✅ Redireciona corretamente |
| Produto inexistente na base | ✅ Não inventa |
| Atualização de reserva (memória) | ✅ Recalcula corretamente |
| Informação inexistente ("produto XYZ") | ⚠️ Em melhoria |

---

## Documentação Completa

Toda a documentação do agente está na pasta [`docs/`](./docs/), incluindo system prompt, exemplos de interação, edge cases e métricas de avaliação.

---

*Desenvolvido como projeto final do Lab de Agentes Financeiros com IA Generativa — DIO + Bradesco.*
