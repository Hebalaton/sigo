import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from io import BytesIO

st.set_page_config(layout='wide')

# =========================
# Funções utilitárias
# =========================
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


def formata_moeda_br(valor, prefixo='R$'):
    if pd.isna(valor):
        return '-'

    numero = f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{prefixo} {numero}'


@st.cache_data
def carregar_dados():
    df = pd.read_excel(
        r'C:/Users/henrique.balaton/Documents/Alura/Python/Streamlit/arquivo.xlsx',
        engine='openpyxl'
    )

    df.columns = df.columns.str.strip()
    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')

    if 'Orçado' in df.columns:
        df['Orçado'] = limpa_moeda(df['Orçado'])

    if 'Realizado' in df.columns:
        df['Realizado'] = limpa_moeda(df['Realizado'])

    df = df.dropna(subset=['Data']).copy()

    df['Desvio'] = df['Realizado'] - df['Orçado']

    df['Status'] = df.apply(
        lambda linha: (
            'Sem orçamento'
            if pd.isna(linha['Orçado']) or linha['Orçado'] == 0
            else 'Acima do orçamento'
            if linha['Realizado'] > linha['Orçado']
            else 'Dentro do orçamento'
        ),
        axis=1
    )

    return df


@st.cache_data
def converte_csv(df_exportacao):
    return df_exportacao.to_csv(index=False).encode('utf-8-sig')


@st.cache_data
def converte_excel(df_exportacao):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exportacao.to_excel(
            writer,
            index=False,
            sheet_name='Dados Filtrados'
        )

    return output.getvalue()


def mensagem_sucesso():
    sucesso = st.success('Arquivo gerado com sucesso!', icon='✅')
    time.sleep(2)
    sucesso.empty()


def aplicar_filtro_multiselect(base, coluna, titulo, label):
    with st.sidebar.expander(titulo):
        opcoes = sorted(base[coluna].dropna().unique())

        selecionados = st.multiselect(
            label,
            options=opcoes,
            default=opcoes
        )

    if selecionados:
        return base[base[coluna].isin(selecionados)].copy()

    return base.copy()


def aplicar_busca_textual(base, termo):
    if not termo.strip():
        return base.copy()

    colunas_busca = [
        'Nível Organizacional',
        'Consolidador',
        'Totalizador',
        'Centro de Custo',
        'Categoria',
        'Conta'
    ]

    colunas_existentes = [col for col in colunas_busca if col in base.columns]

    if not colunas_existentes:
        return base.copy()

    termo = termo.lower().strip()
    mascara = pd.Series(False, index=base.index)

    for coluna in colunas_existentes:
        mascara = mascara | (
            base[coluna]
            .fillna('')
            .astype(str)
            .str.lower()
            .str.contains(termo, na=False)
        )

    return base[mascara].copy()


def extrair_valores_selecionados(evento_plotly, campo='y'):
    """
    Extrai valores selecionados em gráfico Plotly no Streamlit.
    Para gráficos horizontais, o campo relevante normalmente é 'y'.
    """
    if evento_plotly is None:
        return []

    try:
        pontos = evento_plotly.selection.points
    except Exception:
        try:
            pontos = evento_plotly.get('selection', {}).get('points', [])
        except Exception:
            pontos = []

    valores = []

    for ponto in pontos:
        try:
            valor = ponto.get(fcampo, None)
        except Exception:
            valor = None

        if valor is None:
            try:
                valor = ponto.get(campo, None)
            except Exception:
                valor = None

        if valor is not None:
            valores.append(valor)

    return sorted(list(set(valores)))


def criar_graficos_detalhe_contexto(base):
    if base is None or base.empty:
        return {
            'fig_categoria': go.Figure(),
            'fig_ccusto': go.Figure()
        }

    # =========================
    # Gráfico categoria
    # =========================
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
        .head(10)
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
            'Orçado': '#9E9E9E',
            'Realizado': '#1565C0'
        }
    )

    fig_categoria.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        legend_title='Indicador',
        margin=dict(t=60, l=20, r=20, b=20),
        height=440,
        clickmode='event+select'
    )

    # =========================
    # Gráfico centro de custo
    # =========================
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
        .head(10)
        .copy()
    )

    fig_ccusto = px.bar(
        top_ccusto.sort_values('Realizado', ascending=True),
        x='Realizado',
        y='Centro de Custo',
        orientation='h',
        color='Desvio',
        title='Centros de Custo por Realizado',
        text_auto='.2s',
        color_continuous_scale='RdBu_r'
    )

    fig_ccusto.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        coloraxis_colorbar_title='Desvio',
        margin=dict(t=60, l=20, r=20, b=20),
        height=440,
        clickmode='event+select'
    )

    return {
        'fig_categoria': fig_categoria,
        'fig_ccusto': fig_ccusto
    }


# =========================
# Carga
# =========================
dados = carregar_dados()

# =========================
# Título
# =========================
#st.title('Detalhamento Analítico')
#st.caption('Consulta, análise visual, auditoria e exportação dos dados filtrados.')

# =========================
# Sidebar - Filtros
# =========================
st.sidebar.title('Filtros')

with st.sidebar.expander('Período de Análise', expanded=True):
    periodo = st.date_input(
        'Selecione o período',
        value=(dados['Data'].min().date(), dados['Data'].max().date()),
        min_value=dados['Data'].min().date(),
        max_value=dados['Data'].max().date()
    )

if isinstance(periodo, tuple) and len(periodo) == 2:
    data_inicio, data_fim = periodo
else:
    data_inicio = dados['Data'].min().date()
    data_fim = dados['Data'].max().date()

dados_filtrados = dados[
    (dados['Data'] >= pd.to_datetime(data_inicio)) &
    (dados['Data'] <= pd.to_datetime(data_fim))
].copy()

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Nível Organizacional',
    'Nível Organizacional',
    'Selecione os níveis organizacionais'
)

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Consolidador',
    'Consolidador',
    'Selecione os consolidadores'
)

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Totalizador',
    'Totalizador',
    'Selecione os totalizadores'
)

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Centro de Custo',
    'Centro de Custo',
    'Selecione os centros de custo'
)

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Categoria',
    'Categoria',
    'Selecione as categorias'
)

dados_filtrados = aplicar_filtro_multiselect(
    dados_filtrados,
    'Conta',
    'Conta',
    'Selecione as contas'
)

with st.sidebar.expander('Busca Textual', expanded=True):
    termo_busca = st.text_input(
        'Buscar na base filtrada',
        placeholder='Ex.: energia, aluguel, Adamantina...'
    )

dados_filtrados = aplicar_busca_textual(dados_filtrados, termo_busca)

# =========================
# Validação
# =========================
if dados_filtrados.empty:
    st.warning('Nenhum dado foi encontrado para os filtros selecionados.')
    st.stop()



# =========================
# Análise Visual Interativa
# =========================
detalhe = criar_graficos_detalhe_contexto(dados_filtrados)

with st.container(border=True):
    st.markdown('### Análise Visual')
    st.caption('Selecione barras nos gráficos para filtrar a tabela abaixo.')

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        evento_categoria = st.plotly_chart(
            detalhe.get('fig_categoria', go.Figure()),
            width='stretch',
            key='fig_categoria_dados_brutos',
            on_select='rerun',
            selection_mode=('points', 'box', 'lasso')
        )

    with col_graf2:
        evento_ccusto = st.plotly_chart(
            detalhe.get('fig_ccusto', go.Figure()),
            width='stretch',
            key='fig_ccusto_dados_brutos',
            on_select='rerun',
            selection_mode=('points', 'box', 'lasso')
        )

# =========================
# Seleção de colunas
# =========================
with st.expander('Selecionar colunas da tabela', expanded=False):
    colunas = st.multiselect(
        'Selecione as colunas',
        options=list(dados_filtrados.columns),
        default=list(dados_filtrados.columns)
    )

if not colunas:
    st.warning('Selecione pelo menos uma coluna para visualizar os dados.')
    st.stop()

# =========================
# Aplicar seleção dos gráficos na tabela
# =========================
categorias_selecionadas = extrair_valores_selecionados(
    evento_categoria,
    campo='y'
)

ccustos_selecionados = extrair_valores_selecionados(
    evento_ccusto,
    campo='y'
)

dados_tabela = dados_filtrados.copy()

if categorias_selecionadas:
    dados_tabela = dados_tabela[
        dados_tabela['Categoria'].astype(str).isin(categorias_selecionadas)
    ].copy()

if ccustos_selecionados:
    dados_tabela = dados_tabela[
        dados_tabela['Centro de Custo'].astype(str).isin(ccustos_selecionados)
    ].copy()

# =========================
# Indicador de interação
# =========================
if categorias_selecionadas or ccustos_selecionados:
    filtros_ativos = []

    if categorias_selecionadas:
        filtros_ativos.append(
            'Categoria: ' + ', '.join(categorias_selecionadas)
        )

    if ccustos_selecionados:
        filtros_ativos.append(
            'Centro de Custo: ' + ', '.join(ccustos_selecionados)
        )

    st.info(
        'Tabela filtrada pela seleção dos gráficos — ' +
        ' | '.join(filtros_ativos)
    )

# =========================
# Tabela Filtrada
# =========================
dados_filtrados_exportacao = dados_tabela[colunas].copy()

if 'Realizado' in dados_filtrados_exportacao.columns:
    dados_filtrados_exportacao = dados_filtrados_exportacao.sort_values(
        by='Realizado',
        ascending=False
    )

with st.container(border=True):
    st.markdown('### Base Filtrada')
    st.caption('A tabela considera os filtros da sidebar e as seleções feitas nos gráficos.')

    st.dataframe(
        dados_filtrados_exportacao,
        width='stretch',
        hide_index=True
    )

    st.markdown(
        f'A tabela possui :blue[{dados_filtrados_exportacao.shape[0]}] linhas e '
        f':blue[{dados_filtrados_exportacao.shape[1]}] colunas.'
    )

# =========================
# Exportação
# =========================
with st.container(border=True):
    st.markdown('### Exportar Dados Filtrados')
    st.caption('Os arquivos exportados consideram todos os filtros aplicados, incluindo seleção dos gráficos.')

    coluna1, coluna2, coluna3 = st.columns([1.5, 1, 1])

    with coluna1:
        nome_arquivo = st.text_input(
            'Nome do arquivo',
            value='dados_brutos_filtrados'
        ).strip()

        if not nome_arquivo:
            nome_arquivo = 'dados_brutos_filtrados'

    nome_csv = nome_arquivo if nome_arquivo.lower().endswith('.csv') else f'{nome_arquivo}.csv'
    nome_excel = nome_arquivo if nome_arquivo.lower().endswith('.xlsx') else f'{nome_arquivo}.xlsx'

    with coluna2:
        st.write('')
        st.write('')

        st.download_button(
            'Download CSV',
            data=converte_csv(dados_filtrados_exportacao),
            file_name=nome_csv,
            mime='text/csv',
            on_click=mensagem_sucesso,
            width='stretch'
        )

    with coluna3:
        st.write('')
        st.write('')

        st.download_button(
            'Download Excel',
            data=converte_excel(dados_filtrados_exportacao),
            file_name=nome_excel,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            on_click=mensagem_sucesso,
            width='stretch'
        )