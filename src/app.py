import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ===== CONFIG =====
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2:3b"  # <- modelo leve e compatível com pouca RAM

DATA_DIR = Path(r"C:\Users\aless\OneDrive\Documentos\Maycon\Curso - Conquer Plus\Dio\Bradesco\Projeto_Final_MoneyCoach\data")
MEM_FILE = Path("perfil.json")

# Ajustes de velocidade
N_TRANSACOES_CONTEXTO = 10
MAX_CHARS_PRODUTOS = 1200

SYSTEM_PROMPT = """Você é o MoneyCoach, um agente financeiro focado em Reserva de Emergência e Metas.

MISSÃO:
Ajudar o usuário a definir a meta da reserva (3 a 12 meses, padrão 6), criar um plano de aporte e acompanhar o progresso.

GUARDRAILS:
- Use SOMENTE os dados do CONTEXTO e/ou informados pelo usuário.
- Se faltar dado, faça perguntas OU dê cenários marcando como ESTIMATIVA.
- Não invente taxas, rentabilidades, impostos ou números não presentes no contexto.
- Quando citar produtos, use apenas itens listados em PRODUTOS_DISPONIVEIS.
- Sempre inclua a seção "Como calculei".
- Moeda: BRL (R$). Linguagem: PT-BR.

FORMATO:
1) Resumo do plano
2) Como calculei
3) Próximo passo

Seja objetivo. Evite respostas longas.
"""

# ===== IO =====
def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_or_init_mem() -> dict:
    if MEM_FILE.exists():
        return load_json(MEM_FILE)
    mem = {
        "gastos_essenciais": None,
        "gastos_essenciais_fonte": None,  # "informado" ou "estimado"
        "meses_meta": 6,
        "reserva_atual": 0.0,
        "aporte_mensal": 0.0,
        "historico_aportes": []
    }
    save_json(MEM_FILE, mem)
    return mem

# ===== CORE =====
def estimate_gastos(transacoes: pd.DataFrame) -> float:
    # estimativa simples: média do valor das despesas (valores negativos) se existir coluna "valor"
    if transacoes.empty or "valor" not in [c.lower() for c in transacoes.columns]:
        raise ValueError("transacoes.csv precisa ter uma coluna de valor (ex: 'valor').")

    col_valor = next(c for c in transacoes.columns if c.lower() == "valor")
    df = transacoes.copy()
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce")
    df = df.dropna(subset=[col_valor])

    gastos = df[df[col_valor] < 0].copy()
    if gastos.empty:
        gastos = df.copy()

    return float(gastos[col_valor].abs().mean())

def extract_product_names(produtos) -> list[str]:
    """
    Tenta extrair nomes/títulos para não mandar JSON inteiro pro modelo.
    Funciona com:
    - lista de dicts (com 'nome' / 'name' / 'titulo' / 'title')
    - dict de listas
    - fallback: string cortada
    """
    names = []

    if isinstance(produtos, list):
        for item in produtos:
            if isinstance(item, dict):
                for k in ("nome", "name", "titulo", "title", "produto", "product"):
                    if k in item and item[k]:
                        names.append(str(item[k]))
                        break
            else:
                names.append(str(item))
        return names

    if isinstance(produtos, dict):
        # se tiver uma chave óbvia com lista
        for v in produtos.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        for k in ("nome", "name", "titulo", "title", "produto", "product"):
                            if k in item and item[k]:
                                names.append(str(item[k]))
                                break
                    else:
                        names.append(str(item))
        # se não achou nada, tenta as chaves como nomes (às vezes é categoria)
        if not names:
            names = [str(k) for k in produtos.keys()]
        return names

    return []

def build_context(perfil_base: dict | None, mem: dict, transacoes: pd.DataFrame, produtos) -> str:
    partes = []

    if perfil_base:
        partes.append(
            f"PERFIL_BASE: nome={perfil_base.get('nome')}, idade={perfil_base.get('idade')}, "
            f"perfil_investidor={perfil_base.get('perfil_investidor')}, objetivo={perfil_base.get('objetivo_principal')}, "
            f"reserva_base={perfil_base.get('reserva_emergencia_atual')}, patrimonio={perfil_base.get('patrimonio_total')}"
        )

    partes.append(
        "MEMORIA: "
        f"gastos_essenciais={mem.get('gastos_essenciais')} ({mem.get('gastos_essenciais_fonte')}), "
        f"meses_meta={mem.get('meses_meta')}, reserva_atual={mem.get('reserva_atual')}, aporte_mensal={mem.get('aporte_mensal')}"
    )

    if not transacoes.empty:
        partes.append(f"TRANSACOES (ultimas {N_TRANSACOES_CONTEXTO}):")
        partes.append(transacoes.tail(N_TRANSACOES_CONTEXTO).to_string(index=False))

    # Produtos bem reduzidos (mais rápido)
    nomes = extract_product_names(produtos)
    if nomes:
        partes.append("PRODUTOS_DISPONIVEIS (nomes):")
        partes.append("\n".join(f"- {n}" for n in nomes[:30]))
    else:
        partes.append("PRODUTOS_DISPONIVEIS (resumo):")
        partes.append(json.dumps(produtos, ensure_ascii=False)[:MAX_CHARS_PRODUTOS])

    return "\n".join(partes)

def perguntar_ollama(pergunta: str, contexto: str) -> str:
    prompt = f"""{SYSTEM_PROMPT}

CONTEXTO:
{contexto}

Pergunta: {pergunta}
"""

    # Ajustes: limitar tamanho da resposta e reduzir aleatoriedade -> mais rápido e consistente
    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 220  # <- principal ganho de velocidade
        }
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    return r.json().get("response", "").strip()

# ===== UI =====
st.set_page_config(page_title="MoneyCoach", page_icon="💰")
st.title("💰 MoneyCoach — Reserva de Emergência + Metas")

# carregar bases
perfil_path = DATA_DIR / "perfil_investidor.json"
transacoes_path = DATA_DIR / "transacoes.csv"
produtos_path = DATA_DIR / "produtos_financeiros.json"

perfil_base = load_json(perfil_path) if perfil_path.exists() else None
transacoes = pd.read_csv(transacoes_path) if transacoes_path.exists() else pd.DataFrame()
produtos = load_json(produtos_path) if produtos_path.exists() else {}

# memória local
mem = load_or_init_mem()

# sidebar setup mínimo
with st.sidebar:
    st.header("Setup")
    mem["reserva_atual"] = float(st.number_input("Reserva atual (R$)", min_value=0.0, value=float(mem["reserva_atual"]), step=50.0))
    mem["meses_meta"] = int(st.slider("Meses da meta (3–12)", 3, 12, int(mem["meses_meta"])))
    mem["aporte_mensal"] = float(st.number_input("Aporte mensal (R$)", min_value=0.0, value=float(mem["aporte_mensal"]), step=50.0))

    ge_txt = st.text_input(
        "Gastos essenciais (R$) [opcional]",
        value="" if mem["gastos_essenciais"] is None else str(mem["gastos_essenciais"])
    )
    if ge_txt.strip():
        mem["gastos_essenciais"] = float(ge_txt.replace(",", "."))
        mem["gastos_essenciais_fonte"] = "informado"

    if st.button("Estimar gastos via transações"):
        mem["gastos_essenciais"] = round(estimate_gastos(transacoes), 2)
        mem["gastos_essenciais_fonte"] = "estimado"

    aporte_val = st.number_input("Registrar aporte (R$)", min_value=0.0, value=0.0, step=50.0)
    if st.button("Registrar"):
        if aporte_val > 0:
            mem["reserva_atual"] += float(aporte_val)
            mem["historico_aportes"].append({"data": datetime.now().strftime("%Y-%m-%d"), "valor": float(aporte_val)})

    if st.button("Salvar"):
        save_json(MEM_FILE, mem)
        st.success("Salvo em perfil.json")

# painel rápido
gastos = mem.get("gastos_essenciais")
meses = mem.get("meses_meta", 6)
reserva = mem.get("reserva_atual", 0.0)
aporte = mem.get("aporte_mensal", 0.0)

meta = (gastos * meses) if isinstance(gastos, (int, float)) else None
faltante = (meta - reserva) if meta is not None else None
prazo = (faltante / aporte) if (faltante is not None and aporte > 0) else None

c1, c2, c3 = st.columns(3)
c1.metric("Gastos essenciais", f"R$ {gastos:.2f}" if isinstance(gastos, (int, float)) else "—")
c2.metric("Meta da reserva", f"R$ {meta:.2f}" if meta is not None else "—")
c3.metric("Reserva atual", f"R$ {reserva:.2f}")
if prazo is not None and prazo >= 0:
    st.caption(f"Prazo estimado: {prazo:.1f} meses (com aporte mensal)")

st.divider()

# chat
if "msgs" not in st.session_state:
    st.session_state.msgs = []

for m in st.session_state.msgs:
    st.chat_message(m["role"]).write(m["content"])

if pergunta := st.chat_input("Pergunte sobre meta, plano, aporte, onde guardar reserva..."):
    st.session_state.msgs.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    contexto = build_context(perfil_base, mem, transacoes, produtos)
    resposta = perguntar_ollama(pergunta, contexto)

    st.session_state.msgs.append({"role": "assistant", "content": resposta})
    st.chat_message("assistant").write(resposta)
