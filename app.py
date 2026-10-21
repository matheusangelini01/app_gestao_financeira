import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
from datetime import date
from pathlib import Path

import firebase_admin
import streamlit as st
from google import genai
from google.genai import errors as genai_errors
from streamlit.errors import StreamlitSecretNotFoundError
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError


APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"
DEFAULT_CREDENTIALS_PATH = (
    APP_DIR / "app-gestao-finaceira-firebase-adminsdk-fbsvc-7407dc7bf5.json"
)
PASSWORD_ITERATIONS = 600_000
EXPENSE_CATEGORIES = (
    "Moradia",
    "Alimentação",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Compras",
    "Contas",
    "Outros",
)
EXPENSE_CATEGORY_COLORS = (
    "#21e65b",
    "#f6bd32",
    "#48a9ff",
    "#c084fc",
    "#ff7b72",
    "#2dd4bf",
    "#fb923c",
    "#f472b6",
    "#94a3b8",
)
INCOME_DESCRIPTIONS = (
    "Salário",
    "Trabalho freelancer",
    "Venda",
    "Reembolso",
    "Investimentos",
    "Benefício",
)
EXPENSE_DESCRIPTIONS = (
    "Aluguel",
    "Condomínio",
    "Mercado",
    "Restaurante",
    "Transporte",
    "Combustível",
    "Conta de água",
    "Conta de luz",
    "Internet e telefone",
    "Saúde e farmácia",
    "Educação",
    "Lazer",
    "Compras",
)
CUSTOM_DESCRIPTION = "Personalizada (digitar)"
DESCRIPTION_PLACEHOLDER = "Selecione uma descrição"

st.set_page_config(
    page_title="MeuSaldo | Gestão financeira",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #07111f;
        --surface: #101d2d;
        --surface-soft: #142438;
        --line: #22344a;
        --text: #f2f6fa;
        --muted: #9aabba;
        --green: #21e65b;
        --gold: #f6bd32;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: radial-gradient(ellipse at 50% -15%, #153226 0, var(--bg) 48%); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMainBlockContainer"] { max-width: 1080px; padding-top: 1.7rem; padding-bottom: 5rem; }
    h1, h2, h3, p, label { color: var(--text); }
    .brand { color: var(--green); font-size: 1.15rem; font-weight: 800; letter-spacing: -.03em; }
    .page-title { font-size: clamp(1.7rem, 4vw, 2.35rem); font-weight: 800; letter-spacing: -.045em; margin: .2rem 0 0; }
    .muted { color: var(--muted); }
    .profile-avatar, .profile-placeholder {
        width: 76px; height: 76px; border-radius: 50%; border: 2px solid var(--green);
        object-fit: cover; display: flex; align-items: center; justify-content: center;
        background: var(--surface-soft); color: var(--green); font-size: 1.5rem;
        font-weight: 800; overflow: hidden;
    }
    .category-legend { display: flex; align-items: center; gap: .65rem; padding: .45rem 0; }
    .category-dot { width: .75rem; height: .75rem; border-radius: 50%; flex: 0 0 auto; }
    .category-name { flex: 1; color: var(--text); font-weight: 600; }
    .category-amount { color: var(--muted); text-align: right; white-space: nowrap; }
    .metric-card, .transaction-card, .auth-card, .form-card {
        background: linear-gradient(145deg, #142438, #0e1a29);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.1rem 1.25rem;
    }
    .metric-label { color: var(--muted); font-size: .9rem; font-weight: 600; }
    .metric-value { color: var(--text); font-size: clamp(1.35rem, 3vw, 1.8rem); font-weight: 800; margin-top: .35rem; overflow-wrap: anywhere; }
    .metric-income .metric-value { color: var(--green); }
    .metric-expense .metric-value { color: var(--gold); }
    .transaction-title { font-weight: 700; font-size: 1rem; }
    .transaction-meta { color: var(--muted); font-size: .84rem; margin-top: .2rem; }
    .amount-income { color: var(--green); font-weight: 800; }
    .amount-expense { color: #ffca64; font-weight: 800; }
    div.stButton > button {
        border: 1px solid #2b4657; border-radius: 12px; font-weight: 700;
        min-height: 2.75rem; transition: .15s ease;
    }
    div.stButton > button[kind="primary"] {
        background: var(--green); border-color: var(--green); color: #06130a;
    }
    div.stButton > button:hover { border-color: var(--green); color: var(--green); }
    div.stButton > button[kind="primary"]:hover { background: #47f178; color: #06130a; }
    .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] > div {
        background-color: #0b1725; color: var(--text); border-color: var(--line); border-radius: 10px;
    }
    [data-testid="stMetric"] { background: transparent; }
    [data-testid="stAlert"] { border-radius: 12px; }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding: 1rem 1rem 4rem; }
        .metric-card { padding: .85rem; border-radius: 14px; }
        .metric-label { font-size: .78rem; }
        .metric-value { font-size: 1.02rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_database():
    try:
        app = firebase_admin.get_app()
    except ValueError:
        credential_path = Path(
            os.environ.get("FIREBASE_CREDENTIALS_PATH", str(DEFAULT_CREDENTIALS_PATH))
        )
        if credential_path.is_file():
            firebase_credential = credentials.Certificate(str(credential_path))
        else:
            try:
                firebase_secrets = st.secrets["firebase"]
            except (KeyError, StreamlitSecretNotFoundError) as exc:
                raise FileNotFoundError(
                    "Credencial Firebase não encontrada. Configure [firebase] "
                    "nos Secrets do Streamlit ou defina FIREBASE_CREDENTIALS_PATH."
                ) from exc
            firebase_config = dict(firebase_secrets)
            if any(
                isinstance(value, str) and "PREENCHA_" in value
                for value in firebase_config.values()
            ):
                raise ValueError(
                    "Os Secrets do Firebase ainda contêm valores de exemplo. "
                    "Substitua todos os campos PREENCHA_ pelos valores do JSON "
                    "da conta de serviço."
                )
            firebase_credential = credentials.Certificate(firebase_config)

        app = firebase_admin.initialize_app(firebase_credential)
    return firestore.client(app=app)


@st.cache_resource
def database():
    return get_database()


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return salt.hex(), password_hash.hex()


def password_matches(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, candidate_hash = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate_hash, expected_hash)


def money(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def show_brand(width: int = 180):
    if LOGO_PATH.is_file():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown('<div class="brand">MeuSaldo</div>', unsafe_allow_html=True)


def show_auth():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        with st.container(border=True):
            _, logo_column, _ = st.columns([1, 2, 1])
            with logo_column:
                show_brand(230)
            st.markdown(
                '<p class="muted">Entre na sua conta ou crie seu cadastro para começar.</p>',
                unsafe_allow_html=True,
            )
            mode = st.radio(
                "Acesso",
                ["Entrar", "Criar conta"],
                horizontal=True,
                label_visibility="collapsed",
            )
            username = st.text_input("Usuário", max_chars=40, placeholder="Seu usuário")
            password = st.text_input("Senha", type="password", placeholder="Sua senha")

            if mode == "Criar conta":
                confirm_password = st.text_input(
                    "Confirmar senha",
                    type="password",
                    placeholder="Digite a senha novamente",
                )
                if st.button("Criar conta", type="primary", use_container_width=True):
                    normalized_username = username.strip().lower()
                    if not normalized_username or not password:
                        st.error("Informe usuário e senha.")
                    elif not re.fullmatch(r"[a-z0-9_.-]{3,40}", normalized_username):
                        st.error(
                            "Use de 3 a 40 caracteres: letras, números, ponto, "
                            "hífen ou sublinhado."
                        )
                    elif len(password) < 8:
                        st.error("A senha precisa ter pelo menos 8 caracteres.")
                    elif password != confirm_password:
                        st.error("As senhas não são iguais.")
                    else:
                        try:
                            salt, password_hash = hash_password(password)
                            database().collection("users").document(
                                normalized_username
                            ).create(
                                {
                                    "username": normalized_username,
                                    "password_salt": salt,
                                    "password_hash": password_hash,
                                }
                            )
                            st.success("Cadastro criado. Agora você já pode entrar.")
                        except AlreadyExists:
                            st.error("Esse usuário já está cadastrado.")
                        except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
                            st.error(f"Não foi possível criar a conta no Firebase: {exc}")
            else:
                if st.button("Entrar", type="primary", use_container_width=True):
                    normalized_username = username.strip().lower()
                    if not normalized_username or not password:
                        st.error("Informe usuário e senha.")
                    elif not re.fullmatch(r"[a-z0-9_.-]{3,40}", normalized_username):
                        st.error("Usuário ou senha inválidos.")
                    else:
                        try:
                            user = (
                                database()
                                .collection("users")
                                .document(normalized_username)
                                .get()
                            )
                            user_data = user.to_dict() if user.exists else None
                            if user_data and password_matches(
                                password,
                                user_data["password_salt"],
                                user_data["password_hash"],
                            ):
                                st.session_state.user_id = normalized_username
                                st.session_state.username = user_data["username"]
                                st.rerun()
                            else:
                                st.error("Usuário ou senha inválidos.")
                        except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
                            st.error(f"Não foi possível entrar no Firebase: {exc}")


def save_transaction(transaction_id: str | None, data: dict):
    collection = database().collection("transactions")
    if transaction_id:
        collection.document(transaction_id).update(data)
    else:
        collection.add(data)


def transaction_form(transaction: dict | None = None):
    editing = transaction is not None
    st.markdown(
        f'<h1 class="page-title">{"Editar lançamento" if editing else "Novo lançamento"}</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="muted">Registre uma receita ou despesa na sua movimentação.</p>',
        unsafe_allow_html=True,
    )
    kind = st.selectbox(
        "Tipo",
        ["Receita", "Despesa"],
        index=0 if not editing or transaction["type"] == "Receita" else 1,
    )
    category = None
    if kind == "Despesa":
        previous_category = transaction.get("category", "Outros") if editing else "Outros"
        category = st.selectbox(
            "Categoria da despesa",
            EXPENSE_CATEGORIES,
            index=(
                EXPENSE_CATEGORIES.index(previous_category)
                if previous_category in EXPENSE_CATEGORIES
                else EXPENSE_CATEGORIES.index("Outros")
            ),
            key=f"category-{transaction.get('id', 'new') if editing else 'new'}",
        )

    description_options = (
        INCOME_DESCRIPTIONS if kind == "Receita" else EXPENSE_DESCRIPTIONS
    )
    previous_description = transaction.get("description", "") if editing else ""
    if previous_description in description_options:
        selected_description = previous_description
    elif editing:
        selected_description = CUSTOM_DESCRIPTION
    else:
        selected_description = DESCRIPTION_PLACEHOLDER
    description_choices = [
        DESCRIPTION_PLACEHOLDER,
        *description_options,
        CUSTOM_DESCRIPTION,
    ]
    description_choice = st.selectbox(
        "Descrição",
        description_choices,
        index=description_choices.index(selected_description),
        key=(
            f"description-option-"
            f"{transaction.get('id', 'new') if editing else 'new'}-{kind.lower()}"
        ),
    )
    if description_choice == CUSTOM_DESCRIPTION:
        description = st.text_input(
            "Descreva o lançamento",
            value=(
                previous_description
                if previous_description not in description_options
                else ""
            ),
            max_chars=100,
            placeholder="Digite uma descrição",
        )
    elif description_choice == DESCRIPTION_PLACEHOLDER:
        description = ""
    else:
        description = description_choice

    with st.form("transaction_form"):
        amount = st.number_input(
            "Valor (R$)",
            min_value=0.01,
            value=float(transaction.get("amount", 0.01)) if editing else 0.01,
            step=10.0,
            format="%.2f",
        )
        transaction_date = st.date_input(
            "Data",
            value=(
                date.fromisoformat(transaction["date"])
                if editing
                else date.today()
            ),
            format="DD/MM/YYYY",
        )
        left, right = st.columns(2)
        submitted = left.form_submit_button(
            "Salvar alterações" if editing else "Salvar lançamento",
            type="primary",
            use_container_width=True,
        )
        cancelled = right.form_submit_button("Cancelar", use_container_width=True)

    if cancelled:
        st.session_state.page = "home"
        st.session_state.editing_transaction = None
        st.rerun()
    if submitted:
        if not description.strip():
            st.error("Informe uma descrição para o lançamento.")
        else:
            try:
                save_transaction(
                    transaction.get("id") if editing else None,
                    {
                        "user_id": st.session_state.user_id,
                        "type": kind,
                        "category": category,
                        "description": description.strip(),
                        "amount": round(float(amount), 2),
                        "date": transaction_date.isoformat(),
                    },
                )
                st.session_state.page = "home"
                st.session_state.editing_transaction = None
                st.rerun()
            except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
                st.error(f"Não foi possível salvar o lançamento: {exc}")


def load_transactions() -> list[dict]:
    documents = (
        database()
        .collection("transactions")
        .where("user_id", "==", st.session_state.user_id)
        .stream()
    )
    transactions = []
    for document in documents:
        item = document.to_dict()
        item["id"] = document.id
        transactions.append(item)
    return sorted(
        transactions,
        key=lambda item: (item.get("date", ""), item["id"]),
        reverse=True,
    )


def gemini_api_key() -> str | None:
    try:
        api_key = st.secrets["gemini"]["api_key"]
    except (KeyError, StreamlitSecretNotFoundError):
        return None
    return api_key.strip() if isinstance(api_key, str) and api_key.strip() else None


def analyze_finances(question: str, transactions: list[dict]) -> str:
    api_key = gemini_api_key()
    if not api_key:
        raise ValueError(
            "Configure a chave em [gemini] api_key nos Secrets do Streamlit "
            "para usar a análise."
        )

    income = sum(
        float(item["amount"]) for item in transactions if item["type"] == "Receita"
    )
    expenses = sum(
        float(item["amount"]) for item in transactions if item["type"] == "Despesa"
    )
    recent_transactions = [
        {
            "data": item["date"],
            "tipo": item["type"],
            "categoria": item.get("category") or "Outros",
            "descricao": item["description"],
            "valor": round(float(item["amount"]), 2),
        }
        for item in transactions[:200]
    ]
    financial_data = {
        "quantidade_total_de_lancamentos": len(transactions),
        "receitas_totais": round(income, 2),
        "despesas_totais": round(expenses, 2),
        "saldo": round(income - expenses, 2),
        "lancamentos_mais_recentes": recent_transactions,
        "observacao": (
            "A lista inclui no máximo os 200 lançamentos mais recentes; "
            "os totais consideram todos os lançamentos."
        ),
    }
    prompt = (
        f"Dados financeiros (JSON):\n{json.dumps(financial_data, ensure_ascii=False)}\n\n"
        f"Pergunta do usuário:\n{question}"
    )
    client = genai.Client(api_key=api_key)
    response = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt,
        system_instruction=(
            "Responda em português brasileiro à pergunta do usuário sobre as finanças. "
            "Use somente os dados financeiros fornecidos, explique limitações quando "
            "relevante e não invente informações. Ofereça observações claras e práticas, "
            "sem apresentar a resposta como aconselhamento financeiro profissional."
        ),
        store=False,
    )
    if not response.output_text:
        raise ValueError("O Gemini não retornou uma análise. Tente novamente.")
    return response.output_text


def show_expense_categories(transactions: list[dict]):
    totals = {category: 0.0 for category in EXPENSE_CATEGORIES}
    for item in transactions:
        if item["type"] == "Despesa":
            category = item.get("category")
            if category not in totals:
                category = "Outros"
            totals[category] += float(item["amount"])

    totals = {category: amount for category, amount in totals.items() if amount > 0}
    total_expenses = sum(totals.values())
    st.markdown("### Despesas por categoria")
    if not totals:
        st.info("Adicione uma despesa para visualizar o gráfico por categoria.")
        return

    chart_data = [
        {"Categoria": category, "Valor": amount}
        for category, amount in totals.items()
    ]
    color_by_category = dict(zip(EXPENSE_CATEGORIES, EXPENSE_CATEGORY_COLORS))
    chart_column, legend_column = st.columns([1.1, 1])
    with chart_column:
        st.vega_lite_chart(
            data=chart_data,
            spec={
                "mark": {"type": "arc", "innerRadius": 62, "stroke": "#101d2d"},
                "encoding": {
                    "theta": {"field": "Valor", "type": "quantitative"},
                    "color": {
                        "field": "Categoria",
                        "type": "nominal",
                        "scale": {
                            "domain": list(EXPENSE_CATEGORIES),
                            "range": list(EXPENSE_CATEGORY_COLORS),
                        },
                        "legend": None,
                    },
                    "tooltip": [
                        {"field": "Categoria", "type": "nominal", "title": "Categoria"},
                        {
                            "field": "Valor",
                            "type": "quantitative",
                            "title": "Gasto",
                            "format": ",.2f",
                        },
                    ],
                },
                "height": 260,
                "view": {"stroke": None},
            },
            use_container_width=True,
            key="expense-category-chart",
        )
    with legend_column:
        st.markdown(
            f'<p class="muted">Total gasto: <strong>{money(total_expenses)}</strong></p>',
            unsafe_allow_html=True,
        )
        for category, amount in totals.items():
            color = color_by_category[category]
            percentage = amount / total_expenses * 100
            st.markdown(
                f'<div class="category-legend"><span class="category-dot" '
                f'style="background:{color}"></span><span class="category-name">'
                f'{html.escape(category)}</span><span class="category-amount">'
                f'{money(amount)} · {percentage:.1f}%</span></div>',
                unsafe_allow_html=True,
            )


def show_home():
    avatar_column, top_left, analysis_column, top_right = st.columns([1, 5, 2, 1])
    with avatar_column:
        photo = st.session_state.get("profile_photo")
        if photo:
            photo_bytes = photo.getvalue()
            if len(photo_bytes) > 5 * 1024 * 1024:
                st.error("A foto deve ter no máximo 5 MB.")
            else:
                photo_type = photo.type
                if photo_type not in ("image/png", "image/jpeg", "image/webp"):
                    st.error("Formato de imagem não suportado.")
                else:
                    encoded_photo = base64.b64encode(photo_bytes).decode("ascii")
                    st.markdown(
                        f'<img class="profile-avatar" alt="Foto de perfil" '
                        f'src="data:{photo_type};base64,{encoded_photo}">',
                        unsafe_allow_html=True,
                    )
        else:
            initials = html.escape(st.session_state.username[:1].upper())
            st.markdown(
                f'<div class="profile-placeholder">{initials}</div>',
                unsafe_allow_html=True,
            )
        st.file_uploader(
            "Adicionar ou alterar foto",
            type=["png", "jpg", "jpeg", "webp"],
            label_visibility="collapsed",
            key="profile_photo",
        )
        st.caption("Foto de perfil")
    with top_left:
        st.markdown(
            f'<h1 class="page-title">Olá, {html.escape(st.session_state.username)} 👋</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="muted">Acompanhe suas finanças em um só lugar.</p>',
            unsafe_allow_html=True,
        )
    with top_right:
        if st.button("Sair", use_container_width=True):
            for key in (
                "user_id",
                "username",
                "page",
                "editing_transaction",
                "analysis_response",
            ):
                st.session_state.pop(key, None)
            st.session_state.clear_profile_photo = True
            st.rerun()
    with analysis_column:
        if st.button("Analisar", use_container_width=True):
            st.session_state.page = "analysis"
            st.rerun()

    try:
        transactions = load_transactions()
    except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
        st.error(f"Não foi possível carregar os lançamentos do Firebase: {exc}")
        return

    income = sum(item["amount"] for item in transactions if item["type"] == "Receita")
    expenses = sum(item["amount"] for item in transactions if item["type"] == "Despesa")
    balance = income - expenses
    show_expense_categories(transactions)

    first, second, third = st.columns(3)
    for column, label, value, extra_class in (
        (first, "Receitas", income, "metric-income"),
        (second, "Despesas", expenses, "metric-expense"),
        (third, "Saldo", balance, ""),
    ):
        with column:
            st.markdown(
                f'<div class="metric-card {extra_class}"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{money(value)}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("### Lançamentos")
    selected_filter = st.selectbox(
        "Exibir",
        ["Todos", "Receitas", "Despesas"],
        label_visibility="collapsed",
    )
    filtered = [
        item
        for item in transactions
        if selected_filter == "Todos"
        or item["type"] == ("Receita" if selected_filter == "Receitas" else "Despesa")
    ]
    if not filtered:
        st.info("Ainda não há lançamentos. Use o botão + para adicionar o primeiro.")

    for item in filtered:
        left, amount_col, edit_col, delete_col = st.columns([5, 2, 1, 1])
        with left:
            st.markdown(
                f'<div class="transaction-card"><div class="transaction-title">'
                f'{"🟢" if item["type"] == "Receita" else "🟡"} '
                f'{html.escape(item["description"])}</div>'
                f'<div class="transaction-meta">{item["type"]} · '
                f'{html.escape(item.get("category") or "Outros") + " · " if item["type"] == "Despesa" else ""}'
                f'{date.fromisoformat(item["date"]).strftime("%d/%m/%Y")}</div></div>',
                unsafe_allow_html=True,
            )
        with amount_col:
            amount_class = "amount-income" if item["type"] == "Receita" else "amount-expense"
            sign = "+" if item["type"] == "Receita" else "−"
            st.markdown(
                f'<div style="padding-top:1.2rem;text-align:right" class="{amount_class}">'
                f'{sign} {money(item["amount"])}</div>',
                unsafe_allow_html=True,
            )
        with edit_col:
            if st.button("✏️", key=f"edit-{item['id']}", help="Editar lançamento"):
                st.session_state.editing_transaction = item
                st.session_state.page = "form"
                st.rerun()
        with delete_col:
            if st.button("🗑️", key=f"delete-{item['id']}", help="Excluir lançamento"):
                try:
                    database().collection("transactions").document(item["id"]).delete()
                    st.rerun()
                except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
                    st.error(f"Não foi possível excluir o lançamento: {exc}")

    st.markdown("<br>", unsafe_allow_html=True)
    _, add_col, _ = st.columns([4, 1, 4])
    with add_col:
        if st.button("＋", type="primary", use_container_width=True, help="Novo lançamento"):
            st.session_state.page = "form"
            st.session_state.editing_transaction = None
            st.rerun()


def show_analysis():
    back_column, _ = st.columns([1, 5])
    with back_column:
        if st.button("← Voltar", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

    st.markdown('<h1 class="page-title">Analisar finanças</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="muted">Pergunte sobre seus lançamentos. Os dados financeiros '
        'serão enviados ao Google Gemini para gerar a análise.</p>',
        unsafe_allow_html=True,
    )
    with st.form("financial_analysis_form"):
        question = st.text_area(
            "O que você quer analisar?",
            max_chars=2000,
            placeholder="Ex.: Como posso reduzir meus gastos com alimentação?",
        )
        submitted = st.form_submit_button("Analisar", type="primary")

    if submitted:
        st.session_state.pop("analysis_response", None)
        if not question.strip():
            st.error("Digite o que você quer analisar.")
        else:
            try:
                transactions = load_transactions()
            except (GoogleAPICallError, FirebaseError, OSError, ValueError) as exc:
                st.error(f"Não foi possível carregar os lançamentos do Firebase: {exc}")
                return

            try:
                with st.spinner("Analisando seus lançamentos com o Gemini..."):
                    st.session_state.analysis_response = analyze_finances(
                        question.strip(), transactions
                    )
            except (genai_errors.APIError, ValueError) as exc:
                st.error(f"Não foi possível gerar a análise: {exc}")

    if st.session_state.get("analysis_response"):
        st.markdown("### Resultado")
        st.markdown(st.session_state.analysis_response)


def main():
    if st.session_state.pop("clear_profile_photo", False):
        st.session_state.pop("profile_photo", None)
    if "user_id" not in st.session_state:
        show_auth()
        return
    if st.session_state.get("page") == "form":
        transaction_form(st.session_state.get("editing_transaction"))
    elif st.session_state.get("page") == "analysis":
        show_analysis()
    else:
        show_home()


main()
