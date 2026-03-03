import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ===== CONFIG =====
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2:3b"  # bom para 8GB RAM

DATA_DIR = Path(r"C:\Users\aless\OneDrive\Documentos\Maycon\Curso - Conquer Plus\Dio\Bradesco\Projeto_Final_MoneyCoach\data")
MEM_FILE = Path("perfil.json")

# Ajustes de velocidade
N_TRANSACOES_CONTEXTO = 5
MAX_CHARS_PRODUTOS = 900

SYSTEM_PROMPT = """Você é o MoneyCoach, um agente financeiro focado em Reserva de Emergência e Metas.

MISSÃO:
Ajudar o usuário a definir a meta da reserva (3 a 12 meses, padrão 6), criar um plano de aporte e acompanhar o progresso.

GUARDRAILS:
- Use SOMENTE os dados do CONTEXTO e/ou informados pelo usuário.
- Se faltar dado, faça perguntas OU dê cenários marcando como ESTIMATIVA.
- Não invente taxas, rentabilidades, impostos ou números não presentes no contexto.
- Quando citar produtos, use apenas itens listados em PRODUTOS_DISPONIVEIS.
- Sempre inclua a seção "Como calculei".
- Se houver NUMEROS_OFICIAIS e/ou APORTE_NECESSARIO_PRAZO, use exatamente esses valores e NÃO recalcule.
- Se o usuário pedir "em X meses", priorize esse prazo (X) e use APORTE_NECESSARIO_PRAZO.
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

def calc_reserva(mem: dict) -> dict:
    gastos = mem.get("gastos_essenciais")
    meses = int(mem.get("meses_meta", 6))
    reserva = float(mem.get("reserva_atual", 0.0))
    aporte = float(mem.get("aporte_mensal", 0.0))

    out = {
        "gastos": gastos,
        "meses": meses,
        "reserva": reserva,
        "aporte": aporte,
        "meta": None,
        "faltante": None,
        "prazo_meses": None,  # prazo estimado dado o aporte atual
    }

    if isinstance(gastos, (int, float)):
        meta = float(gastos) * meses
        faltante = meta - reserva
        out["meta"] = meta
        out["faltante"] = faltante
        if aporte > 0:
            out["prazo_meses"] = faltante / aporte

    return out

def extrair_prazo_meses(texto: str) -> int | None:
    m = re.search(r"\b(\d{1,2})\s*mes(?:es)?\b", texto.lower())
    return int(m.group(1)) if m else None

def extract_product_names(produtos) -> list[str]:
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
        if not names:
            names = [str(k) for k in produtos.keys()]
        return names

    return []

def build_context(perfil_base: dict | None, mem: dict, transacoes: pd.DataFrame, produtos) -> str:
    partes = []

    # PERFIL_BASE só como contexto geral (sem números que confundem)
    if perfil_base:
        partes.append(
            f"PERFIL_BASE: nome={perfil_base.get('nome')}, idade={perfil_base.get('idade')}, "
            f"perfil_investidor={perfil_base.get('perfil_investidor')}, objetivo={perfil_base.get('objetivo_principal')}"
        )

    # FONTE DA VERDADE: MEMORIA
    partes.append("FONTE_DA_VERDADE: use MEMORIA para todos os cálculos.")
    partes.append(
        "MEMORIA: "
        f"gastos_essenciais={mem.get('gastos_essenciais')} ({mem.get('gastos_essenciais_fonte')}), "
        f"meses_meta={mem.get('meses_meta')}, reserva_atual={mem.get('reserva_atual')}, aporte_mensal={mem.get('aporte_mensal')}"
    )

    # NÚMEROS OFICIAIS calculados em Python (para evitar erro do modelo)
    nums = calc_reserva(mem)
    partes.append(
        "NUMEROS_OFICIAIS (use estes valores; não recalcule): "
        f"meta={nums['meta']}, faltante={nums['faltante']}, prazo_meses_aporte_atual={nums['prazo_meses']}"
    )

    # Se usuário pediu um prazo específico, calcula o aporte mensal necessário para esse prazo
    prazo_desejado = mem.get("_prazo_desejado_meses")
    aporte_necessario_prazo = None
    if nums["faltante"] is not None and prazo_desejado and prazo_desejado > 0:
        aporte_necessario_prazo = nums["faltante"] / prazo_desejado

    partes.append(
        "APORTE_NECESSARIO_PRAZO (se prazo_desejado_meses existir, use este valor; não recalcule): "
        f"prazo_desejado_meses={prazo_desejado}, aporte_mensal_necessario={aporte_necessario_prazo}"
    )

    if not transacoes.empty:
        partes.append(f"TRANSACOES (ultimas {N_TRANSACOES_CONTEXTO}):")
        partes.append(transacoes.tail(N_TRANSACOES_CONTEXTO).to_string(index=False))

    nomes = extract_product_names(produtos)
    if nomes:
        partes.append("PRODUTOS_DISPONIVEIS (nomes):")
        partes.append("\n".join(f"- {n}" for n in nomes[:25]))
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

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 160  # mais rápido e direto para demo
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

# mem em session_state (evita “sumir” entre reruns)
if "mem" not in st.session_state:
    st.session_state.mem = load_or_init_mem()
mem = st.session_state.mem

# sidebar setup mínimo
with st.sidebar:
    st.header("Setup")

    mem["reserva_atual"] = float(st.number_input(
        "Reserva atual (R$)", min_value=0.0, value=float(mem.get("reserva_atual") or 0.0), step=50.0
    ))
    mem["meses_meta"] = int(st.slider(
        "Meses da meta (3–12)", 3, 12, int(mem.get("meses_meta") or 6)
    ))
    mem["aporte_mensal"] = float(st.number_input(
        "Aporte mensal (R$)", min_value=0.0, value=float(mem.get("aporte_mensal") or 0.0), step=50.0
    ))

    ge_txt = st.text_input(
        "Gastos essenciais (R$) [opcional]",
        value="" if mem.get("gastos_essenciais") is None else str(mem.get("gastos_essenciais"))
    )
    if ge_txt.strip():
        mem["gastos_essenciais"] = float(ge_txt.replace(",", "."))
        mem["gastos_essenciais_fonte"] = "informado"

    colA, colB = st.columns(2)
    with colA:
        if st.button("Estimar gastos"):
            mem["gastos_essenciais"] = round(estimate_gastos(transacoes), 2)
            mem["gastos_essenciais_fonte"] = "estimado"
            save_json(MEM_FILE, mem)
            st.success("Gastos estimados e salvos ✅")

    with colB:
        if st.button("Limpar gastos"):
            mem["gastos_essenciais"] = None
            mem["gastos_essenciais_fonte"] = None
            save_json(MEM_FILE, mem)
            st.success("Gastos limpos ✅")

    st.divider()

    aporte_val = st.number_input("Registrar aporte (R$)", min_value=0.0, value=0.0, step=50.0)
    if st.button("Registrar"):
        if aporte_val > 0:
            mem["reserva_atual"] += float(aporte_val)
            mem["historico_aportes"].append({"data": datetime.now().strftime("%Y-%m-%d"), "valor": float(aporte_val)})
            save_json(MEM_FILE, mem)
            st.success("Aporte registrado e salvo ✅")

    if st.button("Salvar setup"):
        save_json(MEM_FILE, mem)
        st.success("Setup salvo em perfil.json ✅")

# painel rápido (sempre baseado na MEMORIA)
nums = calc_reserva(mem)
gastos = nums["gastos"]
meses = nums["meses"]
reserva = nums["reserva"]
aporte = nums["aporte"]
meta = nums["meta"]
faltante = nums["faltante"]
prazo = nums["prazo_meses"]

c1, c2, c3 = st.columns(3)
c1.metric("Gastos essenciais", f"R$ {gastos:.2f}" if isinstance(gastos, (int, float)) else "—")
c2.metric("Meta da reserva", f"R$ {meta:.2f}" if meta is not None else "—")
c3.metric("Reserva atual", f"R$ {reserva:.2f}")

if prazo is not None:
    st.caption(f"Prazo estimado (pelo aporte atual): {prazo:.1f} meses")

st.divider()

# chat
if "msgs" not in st.session_state:
    st.session_state.msgs = []

for m in st.session_state.msgs:
    st.chat_message(m["role"]).write(m["content"])

if pergunta := st.chat_input("Pergunte sobre meta, plano, aporte, onde guardar reserva..."):
    # captura prazo desejado na pergunta (ex.: "em 6 meses")
    mem["_prazo_desejado_meses"] = extrair_prazo_meses(pergunta)

    # garante persistência antes de perguntar
    save_json(MEM_FILE, mem)

    st.session_state.msgs.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    contexto = build_context(perfil_base, mem, transacoes, produtos)
    resposta = perguntar_ollama(pergunta, contexto)

    st.session_state.msgs.append({"role": "assistant", "content": resposta})
    st.chat_message("assistant").write(resposta)
