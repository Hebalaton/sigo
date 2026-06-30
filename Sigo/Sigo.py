import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unicodedata

st.set_page_config(
    page_title='Painel Executivo Financeiro',
    layout='wide'
)

# =========================
# CSS
# =========================
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2rem;
        }

        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            padding: 16px;
            border-radius: 16px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 13px;
            color: #6B7280;
        }

        div[data-testid="stMetricValue"] {
            font-size: 24px;
            font-weight: 700;
            color: #111827;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# FUNÇÕES UTILITÁRIAS
# =========================
def formata_moeda_br(valor, prefixo='R$'):
    if pd.isna(valor):
        return '-'

    numero = f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{prefixo} {numero}'


def formata_desvio_br(valor):
    if pd.isna(valor):
        return '-'

    if valor < 0:
        return f"- {formata_moeda_br(abs(valor))}"

    return formata_moeda_br(valor)


def limpa_moeda(coluna):
    if pd.api.types.is_numeric_dtype(coluna):
        return pd.to_numeric(coluna, errors='coerce')

    serie = coluna.astype(str).str.strip()
    serie = serie.str.replace('R$', '', regex=False).str.strip()

    if serie.str.contains(',', na=False).any():
        serie = (
            serie
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
        )

    return pd.to_numeric(serie, errors='coerce')


def normalizar_texto(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    return texto


def limpar_busca_conta():
    st.session_state.busca_conta = ''
    st.session_state.conta_referencia_selecionada = 'Todas as contas encontradas'


@st.cache_data
def carregar_dados():
    df = pd.read_excel(
        r'C:/Users/henrique.balaton/Documents/Alura/Python/Streamlit/arquivo.xlsx',
        engine='openpyxl'
    )

    df.columns = df.columns.str.strip()
    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
    df['Orçado'] = limpa_moeda(df['Orçado'])
    df['Realizado'] = limpa_moeda(df['Realizado'])

    return df.dropna(subset=['Data']).copy()


# =========================
# FUNÇÕES DE ESTADO E FILTRO
# =========================
def inicializar_estado(base):
    if 'periodo_filtro' not in st.session_state:
        st.session_state.periodo_filtro = (
            base['Data'].min().date(),
            base['Data'].max().date()
        )

    if 'busca_conta' not in st.session_state:
        st.session_state.busca_conta = ''

    if 'conta_referencia_selecionada' not in st.session_state:
        st.session_state.conta_referencia_selecionada = 'Todas as contas encontradas'


def restaurar_periodo(base):
    st.session_state.periodo_filtro = (
        base['Data'].min().date(),
        base['Data'].max().date()
    )
    st.rerun()


def aplicar_filtro_multiselect(base, coluna, titulo, label):
    with st.sidebar.expander(titulo):
        opcoes = sorted(base[coluna].dropna().astype(str).unique())

        selecionados = st.multiselect(
            label,
            options=opcoes,
            default=opcoes
        )

    if selecionados:
        return base[base[coluna].astype(str).isin(selecionados)].copy()

    return base.copy()


def aplicar_busca_conta(base):
    busca_aplicada = False
    contas_card = []

    with st.sidebar.expander('Conta', expanded=True):
        st.text_input(
            'Buscar conta',
            key='busca_conta',
            placeholder='Digite parte do nome da conta...'
        )

        termo_digitado = st.session_state.get('busca_conta', '').strip()

        if termo_digitado:
            termo_busca = normalizar_texto(termo_digitado)

            contas_base = sorted(
                base['Conta']
                .dropna()
                .astype(str)
                .unique()
            )

            contas_encontradas = [
                conta for conta in contas_base
                if termo_busca in normalizar_texto(conta)
            ]

            if contas_encontradas:
                opcoes_conta = ['Todas as contas encontradas'] + contas_encontradas

                if st.session_state.get('conta_referencia_selecionada') not in opcoes_conta:
                    st.session_state.conta_referencia_selecionada = 'Todas as contas encontradas'

                conta_escolhida = st.selectbox(
                    'Contas encontradas',
                    options=opcoes_conta,
                    key='conta_referencia_selecionada'
                )

                st.caption(f'{len(contas_encontradas)} conta(s) encontrada(s).')

                if conta_escolhida == 'Todas as contas encontradas':
                    base = base[
                        base['Conta'].astype(str).isin(contas_encontradas)
                    ].copy()

                    contas_card = contas_encontradas
                else:
                    base = base[
                        base['Conta'].astype(str) == conta_escolhida
                    ].copy()

                    contas_card = [conta_escolhida]

                busca_aplicada = True

            else:
                st.warning('Nenhuma conta encontrada para o termo digitado.')
                base = base.iloc[0:0].copy()

        st.button(
            'Limpar conta',
            key='btn_limpar_busca_conta',
            width='stretch',
            on_click=limpar_busca_conta
        )

    return base, busca_aplicada, contas_card


# =========================
# FUNÇÕES DE RESUMO
# =========================
def preparar_resumo(base):
    total_orcado = base['Orçado'].sum()
    total_realizado = base['Realizado'].sum()
    desvio = total_realizado - total_orcado
    aderencia = (total_realizado / total_orcado * 100) if total_orcado != 0 else 0

    categoria_resumo = (
        base.groupby('Categoria', as_index=False)[['Orçado', 'Realizado']]
        .sum()
    )

    categoria_resumo['Desvio'] = (
        categoria_resumo['Realizado'] - categoria_resumo['Orçado']
    )

    maior_estouro = (
        categoria_resumo[categoria_resumo['Desvio'] > 0]
        .sort_values('Desvio', ascending=False)
        .head(1)
    )

    maior_economia = (
        categoria_resumo[categoria_resumo['Desvio'] < 0]
        .sort_values('Desvio', ascending=True)
        .head(1)
    )

    return {
        'total_orcado': total_orcado,
        'total_realizado': total_realizado,
        'desvio': desvio,
        'aderencia': aderencia,
        'categoria_resumo': categoria_resumo,
        'categoria_estouro': maior_estouro['Categoria'].iloc[0] if not maior_estouro.empty else '-',
        'valor_estouro': maior_estouro['Desvio'].iloc[0] if not maior_estouro.empty else 0,
        'categoria_economia': maior_economia['Categoria'].iloc[0] if not maior_economia.empty else '-',
        'valor_economia': maior_economia['Desvio'].iloc[0] if not maior_economia.empty else 0
    }


# =========================
# GRÁFICOS
# =========================
def criar_grafico_linha(base, titulo='Evolução Mensal', height=450):
    resumo = (
        base.groupby('Data', as_index=False)[['Realizado', 'Orçado']]
        .sum()
        .sort_values('Data')
    )

    fig = px.line(
        resumo,
        x='Data',
        y=['Realizado', 'Orçado'],
        markers=True,
        title=titulo,
        color_discrete_map={
            'Realizado': '#1565C0',
            'Orçado': '#9CA3AF'
        }
    )

    fig.update_traces(
        selector=dict(name='Orçado'),
        line=dict(color='#9CA3AF', dash='dash')
    )

    fig.update_layout(
        xaxis_title='Mês',
        yaxis_title='Valor',
        legend_title='Indicador',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(t=60, l=20, r=20, b=20),
        hovermode='x unified',
        height=height
    )

    return fig


def criar_gauge_aderencia(aderencia, height=260):
    limite_gauge = max(120, round(aderencia + 20))

    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=aderencia,
        number={'suffix': '%'},
        delta={'reference': 100},
        title={'text': 'Aderência ao Orçamento'},
        gauge={
            'axis': {'range': [0, limite_gauge]},
            'bar': {'color': '#1565C0'},
            'steps': [
                {'range': [0, 90], 'color': '#E8F5E9'},
                {'range': [90, 100], 'color': '#FFF8E1'},
                {'range': [100, limite_gauge], 'color': '#FFEBEE'}
            ],
            'threshold': {
                'line': {'color': '#C62828', 'width': 4},
                'thickness': 0.8,
                'value': 100
            }
        }
    ))

    fig.update_layout(
        height=height,
        margin=dict(t=50, l=10, r=10, b=10)
    )

    return fig


def criar_detalhamento_visual(base):
    if base is None or base.empty:
        return {
            'qtd_linhas': 0,
            'qtd_categorias': 0,
            'qtd_ccusto': 0,
            'fig_categoria': go.Figure(),
            'fig_ccusto': go.Figure()
        }

    categoria_resumo = (
        base.groupby('Categoria', as_index=False)[['Orçado', 'Realizado']]
        .sum()
    )

    categoria_resumo['Desvio'] = (
        categoria_resumo['Realizado'] - categoria_resumo['Orçado']
    )

    top_categoria = (
        categoria_resumo
        .sort_values('Realizado', ascending=False)
        .head(8)
        .copy()
    )

    top_categoria_long = top_categoria.melt(
        id_vars='Categoria',
        value_vars=['Orçado', 'Realizado'],
        var_name='Indicador',
        value_name='Valor'
    )

    fig_categoria = px.bar(
        top_categoria_long.sort_values('Valor', ascending=True),
        x='Valor',
        y='Categoria',
        color='Indicador',
        barmode='group',
        orientation='h',
        title='Categorias — Orçado x Realizado',
        text_auto='.2s',
        color_discrete_map={
            'Orçado': '#9CA3AF',
            'Realizado': '#1565C0'
        }
    )

    fig_categoria.update_layout(
        xaxis_title='Valor',
        yaxis_title='Categoria',
        legend_title='Indicador',
        margin=dict(t=60, l=20, r=20, b=20),
        height=420
    )

    ccusto_resumo = (
        base.groupby('Centro de Custo', as_index=False)[['Realizado', 'Orçado']]
        .sum()
    )

    ccusto_resumo['Desvio'] = (
        ccusto_resumo['Realizado'] - ccusto_resumo['Orçado']
    )

    top_ccusto = (
        ccusto_resumo
        .sort_values('Realizado', ascending=False)
        .head(8)
        .copy()
    )

    fig_ccusto = px.bar(
        top_ccusto.sort_values('Realizado', ascending=True),
        x='Realizado',
        y='Centro de Custo',
        orientation='h',
        color='Desvio',
        title='Centros de Custo',
        text_auto='.2s',
        color_continuous_scale='RdBu_r'
    )

    fig_ccusto.update_layout(
        xaxis_title='Realizado',
        yaxis_title='Centro de Custo',
        coloraxis_colorbar_title='Desvio',
        margin=dict(t=60, l=20, r=20, b=20),
        height=420
    )

    return {
        'qtd_linhas': len(base),
        'qtd_categorias': base['Categoria'].nunique(dropna=True),
        'qtd_ccusto': base['Centro de Custo'].nunique(dropna=True),
        'fig_categoria': fig_categoria,
        'fig_ccusto': fig_ccusto
    }


# =========================
# COMPONENTES VISUAIS
# =========================
def render_card_contexto_conta(contas):
    if len(contas) == 1:
        titulo = contas[0]
        subtitulo = 'Conta selecionada'
    else:
        titulo = f'{len(contas)} contas encontradas'
        subtitulo = 'Resultado da busca por conta'

    lista_contas = ', '.join(contas[:5])

    if len(contas) > 5:
        lista_contas += '...'

    with st.container(border=True):
        st.caption(subtitulo)
        st.markdown(f'### {titulo}')

        if lista_contas:
            st.caption(lista_contas)


def render_insight_executivo(resumo):
    desvio = resumo.get('desvio', 0)

    if desvio > 0:
        st.error(
            f"O realizado está acima do orçamento em **{formata_moeda_br(desvio)}**. "
            f"A principal pressão está em **{resumo.get('categoria_estouro', '-')}**."
        )
    elif desvio < 0:
        st.success(
            f"O realizado está abaixo do orçamento em **{formata_moeda_br(abs(desvio))}**. "
            f"A maior economia está em **{resumo.get('categoria_economia', '-')}**."
        )
    else:
        st.info(
            'O realizado está alinhado ao orçamento no contexto atual.'
        )


# =========================
# CARGA
# =========================
df = carregar_dados()
inicializar_estado(df)

# =========================
# SIDEBAR
# =========================
st.sidebar.title('Filtros')

with st.sidebar.expander('Período de Análise', expanded=True):
    periodo = st.date_input(
        'Selecione o período',
        min_value=df['Data'].min().date(),
        max_value=df['Data'].max().date(),
        key='periodo_filtro'
    )

    if st.button('Restaurar período', key='btn_restaurar_periodo', width='stretch'):
        restaurar_periodo(df)

if isinstance(periodo, tuple) and len(periodo) == 2:
    data_inicio, data_fim = periodo
else:
    data_inicio = df['Data'].min().date()
    data_fim = df['Data'].max().date()

df_filtrado = df[
    (df['Data'] >= pd.to_datetime(data_inicio)) &
    (df['Data'] <= pd.to_datetime(data_fim))
].copy()

df_filtrado = aplicar_filtro_multiselect(
    df_filtrado,
    'Nível Organizacional',
    'Nível Organizacional',
    'Selecione os níveis organizacionais'
)

df_filtrado = aplicar_filtro_multiselect(
    df_filtrado,
    'Consolidador',
    'Consolidador',
    'Selecione os consolidadores'
)

df_filtrado = aplicar_filtro_multiselect(
    df_filtrado,
    'Totalizador',
    'Totalizador',
    'Selecione os totalizadores'
)

df_filtrado = aplicar_filtro_multiselect(
    df_filtrado,
    'Centro de Custo',
    'Centro de Custo',
    'Selecione os centros de custo'
)

df_filtrado = aplicar_filtro_multiselect(
    df_filtrado,
    'Categoria',
    'Categoria',
    'Selecione as categorias'
)

df_filtrado, busca_conta_aplicada, contas_card = aplicar_busca_conta(df_filtrado)

# =========================
# VALIDAÇÃO
# =========================
if df_filtrado.empty:
    st.warning('Nenhum dado foi encontrado para os filtros selecionados.')
    st.stop()

# =========================
# RESUMOS
# =========================
contexto_base = df_filtrado.copy()

resumo_geral = preparar_resumo(df_filtrado)
resumo_contexto = preparar_resumo(contexto_base)

fig_real_mensal = criar_grafico_linha(
    df_filtrado,
    titulo='Evolução Mensal',
    height=450
)

detalhe = criar_detalhamento_visual(contexto_base)

qtd_linhas = detalhe.get('qtd_linhas', 0)
qtd_categorias = detalhe.get('qtd_categorias', 0)
qtd_ccusto = detalhe.get('qtd_ccusto', 0)

fig_categoria = detalhe.get('fig_categoria', go.Figure())
fig_ccusto = detalhe.get('fig_ccusto', go.Figure())

# =========================
# VISÃO GERAL
# =========================
if busca_conta_aplicada:
    render_card_contexto_conta(contas_card)

k1, k2, k3 = st.columns(3)

with k1:
    st.metric(
        'Total Orçado',
        formata_moeda_br(resumo_geral.get('total_orcado', 0))
    )

with k2:
    st.metric(
        'Total Realizado',
        formata_moeda_br(resumo_geral.get('total_realizado', 0))
    )

with k3:
    desvio_total = resumo_geral.get('desvio', 0)
    st.metric(
        'Desvio',
        formata_desvio_br(desvio_total)
    )

st.plotly_chart(
    fig_real_mensal,
    width='stretch',
    key='grafico_mensal'
)

render_insight_executivo(resumo_contexto)

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    fig_gauge_resumo = criar_gauge_aderencia(
        resumo_contexto.get('aderencia', 0),
        height=260
    )

    st.plotly_chart(
        fig_gauge_resumo,
        width='stretch',
        key='gauge_aderencia_resumo'
    )

with kpi2:
    valor_estouro = resumo_contexto.get('valor_estouro', 0)
    categoria_estouro = resumo_contexto.get('categoria_estouro', '-')

    if valor_estouro != 0:
        st.metric(
            'Maior Estouro',
            categoria_estouro,
            delta=formata_moeda_br(valor_estouro),
            delta_color='inverse'
        )
    else:
        st.metric(
            'Maior Estouro',
            '-',
            delta='Sem estouro no contexto',
            delta_color='off'
        )

with kpi3:
    valor_economia = resumo_contexto.get('valor_economia', 0)

    if valor_economia < 0:
        st.metric(
            'Maior Economia',
            resumo_contexto.get('categoria_economia', '-'),
            delta=formata_moeda_br(abs(valor_economia)),
            delta_color='normal'
        )
    else:
        st.metric(
            'Maior Economia',
            '-',
            delta='Sem economia no contexto',
            delta_color='off'
        )