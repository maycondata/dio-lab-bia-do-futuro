# Base de Conhecimento (MoneyCoach)

## Dados Utilizados

| Arquivo | Formato | Utilização no Agente |
|---------|---------|---------------------|
| `perfil_investidor.json` | JSON | Puxar contexto do cliente (objetivo, reserva atual, metas) para personalizar o plano |
| `transacoes.csv` | CSV | Estimar gastos essenciais mensais (quando possível) e apoiar cálculo da meta |
| `produtos_financeiros.json` | JSON | Explicar opções seguras para reserva (ex.: liquidez diária) sem “inventar” recomendações |
| `historico_atendimento.csv` | CSV | Lembrar preferências e continuidade (ex.: última meta definida, dúvidas recorrentes) |

---

## Adaptações nos Dados

- Não alteramos os arquivos originais do curso.
- Criamos um `perfil.json` local (memória do agente) para salvar:
  - `gastos_essenciais` (informado pelo usuário ou estimado por transações)
  - `meses_meta` (3 a 12)
  - `aporte_mensal` e `historico_aportes`

> Observação: `gastos_essenciais` é o dado central para calcular “3 a 6 meses”. Se a estimativa via transações não for confiável, o agente solicita esse valor ao usuário.

---

## Estratégia de Integração

### Como os dados são carregados?
- JSON/CSV são carregados em tempo de execução (Python), via leitura local de arquivos.
- O agente monta um “contexto mínimo” com os campos relevantes (sem despejar o arquivo inteiro no prompt).

### Como os dados são usados no prompt?
- Uso dinâmico (RAG simples/local):
  1) Carrega os dados
  2) Extrai apenas o necessário para a resposta atual
  3) Gera a resposta com:
     - Resumo do plano
     - Cálculo (transparência)
     - Próximo passo (pergunta ou ação)

> Os dados não ficam fixos no system prompt. São consultados conforme a pergunta do usuário.

---

## Exemplo de Contexto Montado

```text
Contexto do Cliente (MoneyCoach)
- Objetivo: Construir reserva de emergencia
- Reserva atual: R$ 2.000
- Gastos essenciais estimados: R$ 2.500 (estimativa via transacoes)
- Meses de meta: 6
- Meta calculada: R$ 15.000  (2.500 x 6)
- Aporte mensal planejado: R$ 500
- Prazo estimado: 26 meses (faltante 13.000 / 500)

Produtos citados (base do curso)
- Opcoes com liquidez para reserva: Tesouro Selic, CDB liquidez diaria

Historico recente (se existir)
- Ultima conversa: usuario perguntou onde guardar a reserva e recebeu sugestao de liquidez diaria
