import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from io import BytesIO

import fitz  # PyMuPDF
import pandas as pd
import PyPDF2
import streamlit as st

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

st.set_page_config(page_title="Verificador NF x RMA - V2", layout="wide")


TRANSPORTADORAS = {
    "BRASPRESS": {
        "razao_social": "BRASPRESS TRANSPORTES URGENTES LTDA",
        "cnpj": "48740351000327",
        "ie": "9030546625",
        "endereco": "RUA JOAO BETTEGA, 3802 - CIDADE INDUSTRIAL",
        "cidade": "CURITIBA",
        "uf": "PR",
    },
    "CRUZEIRO DO SUL": {
        "razao_social": "VIACAO CRUZEIRO DO SUL LTDA",
        "cnpj": "03232675006195",
        "ie": "",
        "endereco": "AVENIDA DEZ DE DEZEMBRO, 5680 - JARDIM PIZA",
        "cidade": "LONDRINA",
        "uf": "PR",
    },
    "FL BRASIL": {
        "razao_social": "FL BRASIL HOLDIND, LOGISTICA",
        "cnpj": "18233211002850",
        "ie": "9076066008",
        "endereco": "RODOVIA BR 116, 22301 - TATUQUARA",
        "cidade": "CURITIBA",
        "uf": "PR",
    },
    "LOCAL EXPRESS": {
        "razao_social": "LOCAL EXPRESS TRANSPORTES E LOGISTICA",
        "cnpj": "06199523000195",
        "ie": "9030307558",
        "endereco": "RUA FORMOSA, 131 - PLANTA PORTAL DA SERRA",
        "cidade": "PINHAIS",
        "uf": "PR",
    },
    "RODONAVES": {
        "razao_social": "RODONAVES TRANSPORTES E ENCOMENDAS LTDA",
        "cnpj": "44914992001703",
        "ie": "6013031914",
        "endereco": "RUA RIO GRANDE DO NORTE, 1200, CENTRO",
        "cidade": "LONDRINA",
        "uf": "PR",
    },
}

CAMPOS_COMPARACAO = [
    "nome_cliente",
    "cnpj_cliente",
    "endereco_cliente",
    "quantidade_caixas",
    "peso",
    "frete",
    "cfop",
    "valor_total",
    "transportadora_razao",
]


def normalize_ws(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def only_digits(texto):
    return re.sub(r"\D", "", str(texto or ""))


def parse_num(texto):
    if texto is None:
        return None
    txt = normalize_ws(texto)
    if not txt:
        return None
    txt = re.sub(r"[^0-9,.\-]", "", txt)
    if not txt:
        return None
    if "," in txt and "." in txt:
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif "," in txt and "." not in txt:
        txt = txt.replace(",", ".")
    if txt.count(".") > 1:
        partes = txt.split(".")
        txt = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(txt)
    except ValueError:
        return None


def similaridade(a, b):
    return SequenceMatcher(None, normalize_ws(a).lower(), normalize_ws(b).lower()).ratio()


def buscar_regex(texto, pattern, flags=re.IGNORECASE):
    if not texto:
        return None
    match = re.search(pattern, texto, flags=flags)
    if not match:
        return None
    return match.group(1).strip() if match.lastindex else match.group(0).strip()


def buscar_primeiro(texto, patterns, flags=re.IGNORECASE | re.DOTALL):
    for pattern in patterns:
        found = buscar_regex(texto, pattern, flags=flags)
        if found:
            return found
    return None


def score_texto(texto):
    if not texto:
        return 0
    alnum = len(re.findall(r"[A-Za-z0-9]", texto))
    linhas = len([l for l in texto.splitlines() if normalize_ws(l)])
    return alnum + (linhas * 2)


def extrair_texto_com_pypdf2(file_bytes):
    try:
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        paginas = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(paginas)
    except Exception:
        return ""


def extrair_texto_com_fitz(file_bytes):
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except Exception:
        return ""


def ocr_disponivel():
    if pytesseract is None or Image is None:
        return False, "Bibliotecas OCR indisponiveis (pytesseract/Pillow)."
    try:
        pytesseract.get_tesseract_version()
        return True, "OCR pronto."
    except Exception as exc:
        return False, f"Tesseract nao encontrado: {exc}"


def extrair_texto_com_ocr(file_bytes, dpi=220):
    ok, motivo = ocr_disponivel()
    if not ok:
        return "", motivo
    textos = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(BytesIO(pix.tobytes("png")))
                txt = ""
                for idioma in ("por+eng", "por", "eng"):
                    try:
                        txt = pytesseract.image_to_string(img, lang=idioma)
                        if normalize_ws(txt):
                            break
                    except Exception:
                        continue
                textos.append(txt or "")
    except Exception as exc:
        return "", f"Falha no OCR: {exc}"
    return "\n".join(textos), "OCR aplicado"


def extrair_texto_pdf_inteligente(file_bytes, permitir_ocr=True):
    texto_fitz = extrair_texto_com_fitz(file_bytes)
    texto_pypdf = extrair_texto_com_pypdf2(file_bytes)

    score_fitz = score_texto(texto_fitz)
    score_pypdf = score_texto(texto_pypdf)

    if score_fitz >= score_pypdf:
        texto = texto_fitz
        fonte = "PyMuPDF"
        score = score_fitz
    else:
        texto = texto_pypdf
        fonte = "PyPDF2"
        score = score_pypdf

    ocr_usado = False
    observacao = f"Melhor extracao: {fonte} (score={score})."

    if permitir_ocr and score < 350:
        texto_ocr, motivo = extrair_texto_com_ocr(file_bytes)
        score_ocr = score_texto(texto_ocr)
        if score_ocr > score:
            texto = texto_ocr
            fonte = f"{fonte} + OCR"
            score = score_ocr
            ocr_usado = True
            observacao = f"OCR melhorou a extracao (score={score_ocr})."
        else:
            observacao = f"{observacao} OCR nao superou extracao atual ({motivo})."

    return {
        "texto": texto,
        "fonte": fonte,
        "score": score,
        "ocr_usado": ocr_usado,
        "observacao": observacao,
    }


def renderizar_paginas_para_preview(file_bytes, n_paginas=3, dpi=120):
    imagens = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total = min(n_paginas, len(doc))
        for idx in range(total):
            pix = doc[idx].get_pixmap(dpi=dpi)
            imagens.append(pix.tobytes("png"))
    return imagens


def recortar_secao(texto, inicios, fins):
    if not texto:
        return ""
    texto_up = texto.upper()
    inicio = -1
    for item in inicios:
        pos = texto_up.find(item.upper())
        if pos != -1 and (inicio == -1 or pos < inicio):
            inicio = pos
    if inicio == -1:
        return texto
    fim = len(texto)
    for item in fins:
        pos = texto_up.find(item.upper(), inicio + 1)
        if pos != -1 and pos < fim:
            fim = pos
    return texto[inicio:fim]


def normalizar_frete(valor):
    bruto = normalize_ws(valor).upper()
    if not bruto:
        return ""
    mapa = {
        "0": "EMITENTE",
        "1": "DESTINATARIO",
        "2": "TERCEIROS",
        "9": "SEM FRETE",
    }
    if bruto in mapa:
        return mapa[bruto]
    if "EMIT" in bruto:
        return "EMITENTE"
    if "DEST" in bruto:
        return "DESTINATARIO"
    if "TERC" in bruto:
        return "TERCEIROS"
    if "SEM" in bruto and "FRETE" in bruto:
        return "SEM FRETE"
    return bruto


def extrair_campos_nf(texto_nf):
    secao_cliente = recortar_secao(
        texto_nf,
        inicios=["DESTINATARIO", "REMETENTE", "DADOS DO DESTINATARIO"],
        fins=["CALCULO DO IMPOSTO", "TRANSPORTADOR", "DADOS DO PRODUTO"],
    )
    secao_transporte = recortar_secao(
        texto_nf,
        inicios=["TRANSPORTADOR", "DADOS DO TRANSPORTE", "TRANSPORTE"],
        fins=["DADOS DO PRODUTO", "CALCULO DO IMPOSTO", "FATURA"],
    )

    nome_cliente = buscar_primeiro(
        secao_cliente,
        [
            r"NOME\/RAZAO SOCIAL\s*[:\-]?\s*([^\n\r]+)",
            r"RAZAO SOCIAL\s*[:\-]?\s*([^\n\r]+)",
            r"DESTINATARIO\s*[:\-]?\s*([^\n\r]+)",
        ],
    ) or buscar_primeiro(texto_nf, [r"(?<=\n)[A-Z0-9 ][A-Z0-9 .,&/-]{8,}(?=\n)"])

    endereco_cliente = buscar_primeiro(
        secao_cliente,
        [
            r"ENDERECO\s*[:\-]?\s*([^\n\r]+)",
            r"LOGRADOURO\s*[:\-]?\s*([^\n\r]+)",
        ],
    )

    cnpj_cliente = buscar_primeiro(
        secao_cliente,
        [
            r"(?:CNPJ|CPF\/CNPJ)\s*[:\-]?\s*([\d./-]{11,18})",
            r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",
        ],
    ) or buscar_primeiro(texto_nf, [r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b"])

    qtd = buscar_primeiro(
        secao_transporte,
        [r"(?:QTD|QUANTIDADE|VOLUME(?:S)?)\s*(?:DE\s*VOLUMES)?\s*[:\-]?\s*(\d+)"],
    )
    if not qtd:
        qtd = buscar_primeiro(texto_nf, [r"VOLUME(?:S)?\s*[:\-]?\s*(\d+)"])

    peso = buscar_primeiro(
        secao_transporte,
        [
            r"PESO\s*(?:BRUTO|B)\s*[:\-]?\s*([\d.,]+)",
            r"PESO\s*(?:LIQUIDO|L[IÍ]QUIDO|L)\s*[:\-]?\s*([\d.,]+)",
        ],
    )

    frete_raw = buscar_primeiro(
        texto_nf,
        [
            r"FRETE\s*POR\s*CONTA\s*[:\-]?\s*([^\n\r]+)",
            r"MODALIDADE\s*DO\s*FRETE\s*[:\-]?\s*([^\n\r]+)",
        ],
    )
    frete = normalizar_frete(frete_raw)

    cfop = buscar_primeiro(
        texto_nf,
        [
            r"\bCFOP\s*[:\-]?\s*(\d{4})\b",
            r"\b(5\d{3}|6\d{3}|7\d{3})\b",
        ],
    )

    valor_total = buscar_primeiro(
        texto_nf,
        [
            r"VALOR TOTAL DA NOTA\s*[:\s]*([\d.,]+)",
            r"V[.]?\s*TOTAL\s*[:\s]*([\d.,]+)",
            r"TOTAL\s*[:\s]*R?\$?\s*([\d.,]+)",
        ],
    )

    transportadora_razao = buscar_primeiro(
        secao_transporte,
        [
            r"TRANSPORTADORA\s*[:\-]?\s*([^\n\r]+)",
            r"RAZAO SOCIAL\s*[:\-]?\s*([^\n\r]+)",
        ],
    )
    transportadora_cnpj = buscar_primeiro(
        secao_transporte,
        [r"(?:CNPJ|CNPJ\/CPF)\s*[:\-]?\s*([\d./-]{11,18})"],
    )
    transportadora_ie = buscar_primeiro(
        secao_transporte,
        [r"INSCRICAO ESTADUAL\s*[:\-]?\s*([0-9A-Za-z./-]+)"],
    )
    transportadora_endereco = buscar_primeiro(
        secao_transporte,
        [r"ENDERECO\s*[:\-]?\s*([^\n\r]+)"],
    )

    return {
        "nome_cliente": normalize_ws(nome_cliente),
        "cnpj_cliente": normalize_ws(cnpj_cliente),
        "endereco_cliente": normalize_ws(endereco_cliente),
        "quantidade_caixas": normalize_ws(qtd),
        "peso": normalize_ws(peso),
        "frete": normalize_ws(frete),
        "cfop": normalize_ws(cfop),
        "valor_total": normalize_ws(valor_total),
        "transportadora_razao": normalize_ws(transportadora_razao),
        "transportadora_cnpj": normalize_ws(transportadora_cnpj),
        "transportadora_ie": normalize_ws(transportadora_ie),
        "transportadora_endereco": normalize_ws(transportadora_endereco),
    }


def get_namespace(root):
    match = re.match(r"\{(.+)\}", root.tag)
    return match.group(1) if match else None


def qname(ns, tag):
    return f"{{{ns}}}{tag}" if ns else tag


def child_text(elem, ns, tag):
    if elem is None:
        return ""
    return normalize_ws(elem.findtext(qname(ns, tag), ""))


def extrair_dados_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    ns = get_namespace(root)

    emit = root.find(f".//{qname(ns, 'emit')}")
    dest = root.find(f".//{qname(ns, 'dest')}")
    transp = root.find(f".//{qname(ns, 'transporta')}")
    vol = root.find(f".//{qname(ns, 'vol')}")

    entidade = emit if emit is not None else dest
    endereco_tag = "enderEmit" if entidade is emit else "enderDest"
    end_elem = entidade.find(qname(ns, endereco_tag)) if entidade is not None else None

    log = child_text(end_elem, ns, "xLgr")
    nro = child_text(end_elem, ns, "nro")
    endereco_entidade = normalize_ws(f"{log}, {nro}".strip(", "))

    pb = child_text(vol, ns, "pesoB") if vol is not None else ""
    pl = child_text(vol, ns, "pesoL") if vol is not None else ""
    peso = pb if (parse_num(pb) or 0) > 0 else pl

    mod_frete = normalize_ws(root.findtext(f".//{qname(ns, 'modFrete')}", ""))
    frete = normalizar_frete(mod_frete)

    cnpj_entidade = child_text(entidade, ns, "CNPJ")
    if not cnpj_entidade:
        cnpj_entidade = child_text(entidade, ns, "CPF")

    return {
        "nome_cliente": child_text(entidade, ns, "xNome"),
        "cnpj_cliente": cnpj_entidade,
        "endereco_cliente": endereco_entidade,
        "quantidade_caixas": child_text(vol, ns, "qVol"),
        "peso": peso,
        "frete": frete,
        "cfop": normalize_ws(root.findtext(f".//{qname(ns, 'CFOP')}", "")),
        "valor_total": normalize_ws(root.findtext(f".//{qname(ns, 'vNF')}", "")),
        "transportadora_razao": child_text(transp, ns, "xNome"),
        "transportadora_cnpj": child_text(transp, ns, "CNPJ"),
        "transportadora_ie": child_text(transp, ns, "IE"),
        "transportadora_endereco": child_text(transp, ns, "xEnder"),
    }


def extrair_valor_total_rma(texto_rma):
    return buscar_primeiro(
        texto_rma,
        [
            r"Tot[.]?\s*Liquido\(R\$\s*.*?\)\s*[:\-]?\s*([\d.,]+)",
            r"TOTAL GERAL\s*[:\-]?\s*([\d.,]+)",
            r"TOTAL\s*[:\-]?\s*R?\$?\s*([\d.,]+)",
        ],
    )


def extrair_campos_rma(texto_rma):
    frete_raw = buscar_primeiro(texto_rma, [r"Frete\s*:\s*([^\n\r]+)"])
    return {
        "nome_cliente": buscar_primeiro(
            texto_rma,
            [r"Nome\/Raz[aã]o\s*Social:\s*([^\n\r]+)"],
        ),
        "endereco_cliente": buscar_primeiro(
            texto_rma,
            [
                r"Endere[cç]o:\s*(.*?)\s+CEP",
                r"Endere[cç]o:\s*([^\n\r]+)",
            ],
        ),
        "cnpj_cliente": buscar_primeiro(
            texto_rma,
            [r"CPF\/CNPJ\s*[:\s]*([\d./-]+)"],
        ),
        "quantidade_caixas": buscar_primeiro(texto_rma, [r"Volume:\s*(\d+)"]),
        "peso": buscar_primeiro(texto_rma, [r"Peso:\s*([\d.,]+)"]),
        "frete": normalizar_frete(frete_raw),
        "cfop": buscar_primeiro(texto_rma, [r"CFOP:\s*(\d{4})"]),
        "valor_total": extrair_valor_total_rma(texto_rma),
        "transportadora_razao": buscar_primeiro(
            texto_rma,
            [r"Transportadora:\s*([^\n\r]+)"],
        ),
    }


def formatar_campo(campo):
    return campo.replace("_", " ").title()


def comparar_campo(campo, v_nf, v_rma):
    v_nf_norm = normalize_ws(v_nf)
    v_rma_norm = normalize_ws(v_rma)

    if not v_nf_norm and not v_rma_norm:
        return None, "Nao encontrado nos dois arquivos."
    if not v_nf_norm:
        return False, "Campo ausente na NF/XML."
    if not v_rma_norm:
        return False, "Campo ausente na RMA."

    if campo in {"valor_total", "peso"}:
        n_nf = parse_num(v_nf_norm)
        n_rma = parse_num(v_rma_norm)
        if n_nf is None or n_rma is None:
            return False, "Nao foi possivel converter numero."
        tolerancia = 0.99 if campo == "valor_total" else 0.05
        ok = abs(n_nf - n_rma) <= tolerancia
        return ok, f"NF={n_nf:.2f} | RMA={n_rma:.2f} | tol={tolerancia}"

    if campo in {"cnpj_cliente"}:
        ok = only_digits(v_nf_norm) == only_digits(v_rma_norm)
        return ok, "Comparacao por CNPJ normalizado."

    if campo in {"cfop", "quantidade_caixas"}:
        ok = only_digits(v_nf_norm) == only_digits(v_rma_norm)
        return ok, "Comparacao numerica exata."

    if campo == "frete":
        ok = normalizar_frete(v_nf_norm) == normalizar_frete(v_rma_norm)
        return ok, "Comparacao por modalidade de frete."

    limiar = 0.85
    if campo == "endereco_cliente":
        limiar = 0.75
    ratio = similaridade(v_nf_norm, v_rma_norm)
    return ratio >= limiar, f"Similaridade={ratio:.2f}, limiar={limiar:.2f}"


def validar_transportadora_catalogo(dados_nf):
    nome_nf = normalize_ws(dados_nf.get("transportadora_razao", ""))
    cnpj_nf = only_digits(dados_nf.get("transportadora_cnpj", ""))
    ie_nf = only_digits(dados_nf.get("transportadora_ie", ""))
    endereco_nf = normalize_ws(dados_nf.get("transportadora_endereco", ""))

    if not nome_nf and not cnpj_nf:
        return [
            {
                "Campo": "Transportadora Catalogo",
                "Valor NF": "-",
                "Valor RMA": "-",
                "Status": None,
                "Detalhe": "Transportadora nao encontrada na NF/XML.",
            }
        ]

    melhor_nome = None
    melhor_base = None
    melhor_score = -1.0
    for chave, base in TRANSPORTADORAS.items():
        score_nome = similaridade(nome_nf, base["razao_social"])
        bonus = 0.15 if cnpj_nf and cnpj_nf == only_digits(base["cnpj"]) else 0.0
        score_total = score_nome + bonus
        if score_total > melhor_score:
            melhor_nome, melhor_base, melhor_score = chave, base, score_total

    if melhor_base is None or melhor_score < 0.60:
        return [
            {
                "Campo": "Transportadora Catalogo",
                "Valor NF": nome_nf or cnpj_nf or "-",
                "Valor RMA": "-",
                "Status": False,
                "Detalhe": "Nenhuma transportadora base com confianca minima.",
            }
        ]

    rows = []
    score_razao = similaridade(nome_nf, melhor_base["razao_social"])
    rows.append(
        {
            "Campo": "Transportadora Razao (Base)",
            "Valor NF": nome_nf or "-",
            "Valor RMA": melhor_base["razao_social"],
            "Status": score_razao >= 0.80,
            "Detalhe": f"Melhor base: {melhor_nome}, similaridade={score_razao:.2f}",
        }
    )

    cnpj_base = only_digits(melhor_base["cnpj"])
    rows.append(
        {
            "Campo": "Transportadora CNPJ (Base)",
            "Valor NF": cnpj_nf or "-",
            "Valor RMA": cnpj_base,
            "Status": cnpj_nf == cnpj_base if cnpj_nf else None,
            "Detalhe": "Comparacao por CNPJ normalizado.",
        }
    )

    ie_base = only_digits(melhor_base["ie"])
    rows.append(
        {
            "Campo": "Transportadora IE (Base)",
            "Valor NF": ie_nf or "-",
            "Valor RMA": ie_base or "-",
            "Status": ie_nf == ie_base if (ie_nf and ie_base) else None,
            "Detalhe": "Comparacao por IE normalizada.",
        }
    )

    score_end = similaridade(endereco_nf, melhor_base["endereco"])
    rows.append(
        {
            "Campo": "Transportadora Endereco (Base)",
            "Valor NF": endereco_nf or "-",
            "Valor RMA": melhor_base["endereco"],
            "Status": score_end >= 0.75 if endereco_nf else None,
            "Detalhe": f"Similaridade endereco={score_end:.2f}",
        }
    )

    return rows


def analisar_dados(dados_nf, texto_rma):
    dados_rma = extrair_campos_rma(texto_rma)
    rows = []

    for campo in CAMPOS_COMPARACAO:
        v_nf = dados_nf.get(campo, "")
        v_rma = dados_rma.get(campo, "")
        ok, detalhe = comparar_campo(campo, v_nf, v_rma)
        rows.append(
            {
                "Campo": formatar_campo(campo),
                "Valor NF": normalize_ws(v_nf) or "-",
                "Valor RMA": normalize_ws(v_rma) or "-",
                "Status": ok,
                "Detalhe": detalhe,
            }
        )

    rows.extend(validar_transportadora_catalogo(dados_nf))
    return pd.DataFrame(rows)


def label_status(ok):
    if ok is True:
        return "OK"
    if ok is False:
        return "DIVERGENTE"
    return "NAO ENCONTRADO"


st.title("Verificador de Nota Fiscal x RMA - V2")
st.caption("V2 com extracao PDF mais robusta, fallback OCR opcional e comparacao por tipo de campo.")

col1, col2, col3 = st.columns(3)
with col1:
    nf_file = st.file_uploader("Enviar Nota Fiscal (PDF)", type=["pdf"])
with col2:
    rma_file = st.file_uploader("Enviar RMA (PDF)", type=["pdf"])
with col3:
    xml_file = st.file_uploader("Enviar XML da NF-e", type=["xml"])

if rma_file:
    rma_bytes = rma_file.read()
    info_rma = extrair_texto_pdf_inteligente(rma_bytes, permitir_ocr=False)
    texto_rma = info_rma["texto"]

    nf_bytes = nf_file.read() if nf_file else None
    dados_nf = None
    origem = ""
    diagnostico_nf = ""

    if xml_file:
        try:
            dados_nf = extrair_dados_xml(xml_file)
            origem = "XML"
            diagnostico_nf = "Dados da NF extraidos via XML."
        except Exception as exc:
            st.error(f"Falha ao ler XML: {exc}")
            st.stop()
    elif nf_bytes:
        info_nf = extrair_texto_pdf_inteligente(nf_bytes, permitir_ocr=True)
        dados_nf = extrair_campos_nf(info_nf["texto"])
        origem = f"PDF ({info_nf['fonte']})"
        diagnostico_nf = info_nf["observacao"]
    else:
        st.info("Envie a NF em PDF ou o XML para iniciar a verificacao.")
        st.stop()

    st.markdown("### Diagnostico de leitura")
    st.write(f"- RMA: fonte={info_rma['fonte']}, score={info_rma['score']}.")
    st.write(f"- NF: origem={origem}. {diagnostico_nf}")

    df = analisar_dados(dados_nf, texto_rma)
    df["Status"] = df["Status"].apply(label_status)

    st.markdown(f"### Comparacao dos dados (origem da NF: {origem})")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Baixar relatorio CSV",
        data=csv,
        file_name="comparacao_nf_rma_v2.csv",
    )

    guide_url = "https://raw.githubusercontent.com/Brayan-GBL/Controle/main/NFXRMA.jpg"
    st.markdown("---")
    st.subheader("Guia de consulta")
    st.image(guide_url, use_column_width=True)

    st.markdown("---")
    st.subheader("Visualizar PDFs")
    col_nf, col_rma = st.columns(2)
    with col_nf:
        st.markdown("**Nota Fiscal**")
        if nf_bytes:
            for img in renderizar_paginas_para_preview(nf_bytes, n_paginas=3):
                st.image(img, use_column_width=True)
        else:
            st.info("Preview da NF indisponivel quando so o XML e enviado.")
    with col_rma:
        st.markdown("**RMA**")
        for img in renderizar_paginas_para_preview(rma_bytes, n_paginas=3):
            st.image(img, use_column_width=True)

else:
    st.info("Envie ao menos a RMA para iniciar a verificacao.")
