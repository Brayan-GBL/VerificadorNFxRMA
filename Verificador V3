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


st.set_page_config(page_title="Verificador NF x RMA - V3", layout="wide")


# ========================= CONFIG =========================
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

TIPOS_ESPELHO = ["PSD", "MARCA_A", "MARCA_B"]


# ========================= HELPERS =========================
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
        achado = buscar_regex(texto, pattern, flags=flags)
        if achado:
            return achado
    return None


def score_texto(texto):
    if not texto:
        return 0
    alnum = len(re.findall(r"[A-Za-z0-9]", texto))
    linhas = len([l for l in texto.splitlines() if normalize_ws(l)])
    return alnum + (linhas * 2)


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
    if "EMIT" in bruto or "REMET" in bruto:
        return "EMITENTE"
    if "DEST" in bruto:
        return "DESTINATARIO"
    if "TERC" in bruto:
        return "TERCEIROS"
    if "SEM" in bruto and "FRETE" in bruto:
        return "SEM FRETE"
    if "FOB" in bruto:
        return "DESTINATARIO"
    if "CIF" in bruto:
        return "EMITENTE"
    return bruto


def formatar_campo(campo):
    return campo.replace("_", " ").title()


def label_status(ok):
    if ok is True:
        return "OK"
    if ok is False:
        return "DIVERGENTE"
    return "NAO ENCONTRADO"


# ========================= EXTRAÇÃO TEXTO PDF =========================
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
        return False, "Bibliotecas OCR indisponiveis."
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

    observacao = f"Melhor extracao: {fonte} (score={score})."

    if permitir_ocr and score < 350:
        texto_ocr, motivo = extrair_texto_com_ocr(file_bytes)
        score_ocr = score_texto(texto_ocr)
        if score_ocr > score:
            texto = texto_ocr
            fonte = f"{fonte} + OCR"
            score = score_ocr
            observacao = f"OCR melhorou a extracao (score={score_ocr})."
        else:
            observacao = f"{observacao} OCR nao superou a extracao atual ({motivo})."

    return {
        "texto": texto,
        "fonte": fonte,
        "score": score,
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


# ========================= EXTRAÇÃO POR BLOCOS =========================
def extrair_blocos_pdf(file_bytes):
    blocos = []

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for pagina_idx, page in enumerate(doc):
            blocks = page.get_text("blocks")
            for block in blocks:
                try:
                    x0, y0, x1, y1, texto, *_ = block
                except Exception:
                    continue

                texto = normalize_ws(texto)
                if not texto:
                    continue

                blocos.append({
                    "pagina": pagina_idx,
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                    "texto": texto,
                })

    return blocos


def encontrar_blocos_por_termo(blocos, termos):
    encontrados = []
    termos_up = [t.upper() for t in termos]

    for bloco in blocos:
        txt = bloco["texto"].upper()
        if any(t in txt for t in termos_up):
            encontrados.append(bloco)

    return encontrados


def selecionar_melhor_ancora(blocos, termos, preferir_primeira_pagina=True):
    candidatos = encontrar_blocos_por_termo(blocos, termos)
    if not candidatos:
        return None

    candidatos = sorted(candidatos, key=lambda b: (b["pagina"], b["y0"], b["x0"]))

    if preferir_primeira_pagina:
        primeira_pagina = min(c["pagina"] for c in candidatos)
        candidatos_primeira = [c for c in candidatos if c["pagina"] == primeira_pagina]
        if candidatos_primeira:
            return candidatos_primeira[0]

    return candidatos[0]


def texto_proximo_da_ancora(blocos, ancora, margem_direita=500, margem_baixo=220, margem_esquerda=20, margem_cima=20):
    if not ancora:
        return ""

    pagina = ancora["pagina"]
    resultado = []

    for bloco in blocos:
        if bloco["pagina"] != pagina:
            continue

        dentro_x = (
            bloco["x0"] >= (ancora["x0"] - margem_esquerda)
            and bloco["x1"] <= (ancora["x1"] + margem_direita)
        )
        dentro_y = (
            bloco["y0"] >= (ancora["y0"] - margem_cima)
            and bloco["y1"] <= (ancora["y1"] + margem_baixo)
        )

        if dentro_x and dentro_y:
            resultado.append(bloco)

    resultado = sorted(resultado, key=lambda b: (b["y0"], b["x0"]))
    return "\n".join(r["texto"] for r in resultado)


def texto_total_blocos(blocos):
    blocos_ordenados = sorted(blocos, key=lambda b: (b["pagina"], b["y0"], b["x0"]))
    return "\n".join(b["texto"] for b in blocos_ordenados)


def extrair_campos_nf_por_blocos(file_bytes):
    blocos = extrair_blocos_pdf(file_bytes)
    texto_global = texto_total_blocos(blocos)

    ancora_dest = selecionar_melhor_ancora(
        blocos,
        [
            "DESTINATARIO",
            "DESTINATÁRIO",
            "REMETENTE",
            "DADOS DO DESTINATARIO",
            "DADOS DO DESTINATÁRIO",
            "DESTINATARIO / REMETENTE",
            "DESTINATÁRIO / REMETENTE",
        ],
    )

    ancora_transp = selecionar_melhor_ancora(
        blocos,
        [
            "TRANSPORTADOR",
            "TRANSPORTE",
            "DADOS DO TRANSPORTE",
            "VOLUMES TRANSPORTADOS",
        ],
    )

    ancora_total = selecionar_melhor_ancora(
        blocos,
        [
            "VALOR TOTAL DA NOTA",
            "TOTAL DA NOTA",
        ],
    )

    ancora_frete = selecionar_melhor_ancora(
        blocos,
        [
            "FRETE POR CONTA",
            "MODALIDADE DO FRETE",
        ],
    )

    texto_dest = texto_proximo_da_ancora(blocos, ancora_dest, margem_direita=650, margem_baixo=260)
    texto_transp = texto_proximo_da_ancora(blocos, ancora_transp, margem_direita=650, margem_baixo=260)
    texto_total = texto_proximo_da_ancora(blocos, ancora_total, margem_direita=250, margem_baixo=120)
    texto_frete = texto_proximo_da_ancora(blocos, ancora_frete, margem_direita=300, margem_baixo=120)

    nome_cliente = buscar_primeiro(
        texto_dest,
        [
            r"NOME\s*/?\s*RAZ[AÃ]O SOCIAL\s*[:\-]?\s*([^\n\r]+)",
            r"RAZ[AÃ]O SOCIAL\s*[:\-]?\s*([^\n\r]+)",
            r"DESTINAT[ÁA]RIO\s*[:\-]?\s*([^\n\r]+)",
            r"REMETENTE\s*[:\-]?\s*([^\n\r]+)",
        ],
    )

    if not nome_cliente:
        linhas = [normalize_ws(l) for l in texto_dest.splitlines() if normalize_ws(l)]
        candidatos = []
        for l in linhas:
            l_up = l.upper()
            if any(chave in l_up for chave in ["CNPJ", "CPF", "INSCRI", "CEP", "ENDERE", "FONE"]):
                continue
            if len(l) >= 8 and len(l) <= 120:
                candidatos.append(l)
        if candidatos:
            nome_cliente = candidatos[0]

    cnpj_cliente = buscar_primeiro(
        texto_dest,
        [
            r"(?:CNPJ|CPF\/CNPJ)\s*[:\-]?\s*([\d./-]{11,18})",
            r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",
        ],
    )

    endereco_cliente = buscar_primeiro(
        texto_dest,
        [
            r"ENDERE[ÇC]O\s*[:\-]?\s*([^\n\r]+)",
            r"LOGRADOURO\s*[:\-]?\s*([^\n\r]+)",
        ],
    )

    if not endereco_cliente:
        linhas = [normalize_ws(l) for l in texto_dest.splitlines() if normalize_ws(l)]
        for i, l in enumerate(linhas):
            l_up = l.upper()
            if any(term in l_up for term in ["RUA ", "AV ", "AVENIDA ", "RODOVIA ", "ESTRADA ", "ALAMEDA "]):
                endereco_cliente = l
                break

    quantidade_caixas = buscar_primeiro(
        texto_transp,
        [
            r"(?:QTD|QUANTIDADE|VOLUME(?:S)?)\s*(?:DE\s*VOLUMES)?\s*[:\-]?\s*(\d+)",
            r"VOLUMES?\s*[:\-]?\s*(\d+)",
        ],
    )

    peso = buscar_primeiro(
        texto_transp,
        [
            r"PESO\s*(?:BRUTO|B)\s*[:\-]?\s*([\d.,]+)",
            r"PESO\s*(?:L[IÍ]QUIDO|L)\s*[:\-]?\s*([\d.,]+)",
            r"\b([\d.,]+)\s*(?:KG|KGS)\b",
        ],
    )

    frete_raw = buscar_primeiro(
        texto_frete or texto_global,
        [
            r"FRETE\s*POR\s*CONTA\s*[:\-]?\s*([^\n\r]+)",
            r"MODALIDADE\s*DO\s*FRETE\s*[:\-]?\s*([^\n\r]+)",
            r"FRETE\s*[:\-]?\s*([^\n\r]+)",
        ],
    )
    frete = normalizar_frete(frete_raw)

    cfop = buscar_primeiro(
        texto_global,
        [
            r"\bCFOP\s*[:\-]?\s*(\d{4})\b",
            r"\b(5202|6202|6949)\b",
            r"\b(5\d{3}|6\d{3}|7\d{3})\b",
        ],
    )

    valor_total = buscar_primeiro(
        texto_total or texto_global,
        [
            r"VALOR TOTAL DA NOTA\s*[:\s]*([\d.,]+)",
            r"TOTAL DA NOTA\s*[:\s]*([\d.,]+)",
            r"V[.]?\s*TOTAL\s*[:\s]*([\d.,]+)",
        ],
    )

    transportadora_razao = buscar_primeiro(
        texto_transp,
        [
            r"TRANSPORTADORA\s*[:\-]?\s*([^\n\r]+)",
            r"RAZ[AÃ]O SOCIAL\s*[:\-]?\s*([^\n\r]+)",
        ],
    )

    transportadora_cnpj = buscar_primeiro(
        texto_transp,
        [
            r"(?:CNPJ|CNPJ\/CPF)\s*[:\-]?\s*([\d./-]{11,18})",
            r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",
        ],
    )

    transportadora_ie = buscar_primeiro(
        texto_transp,
        [
            r"INSCRI[ÇC][AÃ]O ESTADUAL\s*[:\-]?\s*([0-9A-Za-z./-]+)",
        ],
    )

    transportadora_endereco = buscar_primeiro(
        texto_transp,
        [
            r"ENDERE[ÇC]O\s*[:\-]?\s*([^\n\r]+)",
            r"LOGRADOURO\s*[:\-]?\s*([^\n\r]+)",
        ],
    )

    diagnostico = {
        "ancora_dest_encontrada": bool(ancora_dest),
        "ancora_transp_encontrada": bool(ancora_transp),
        "ancora_total_encontrada": bool(ancora_total),
        "ancora_frete_encontrada": bool(ancora_frete),
        "texto_dest_len": len(texto_dest),
        "texto_transp_len": len(texto_transp),
    }

    return {
        "campos": {
            "nome_cliente": normalize_ws(nome_cliente),
            "cnpj_cliente": normalize_ws(cnpj_cliente),
            "endereco_cliente": normalize_ws(endereco_cliente),
            "quantidade_caixas": normalize_ws(quantidade_caixas),
            "peso": normalize_ws(peso),
            "frete": normalize_ws(frete),
            "cfop": normalize_ws(cfop),
            "valor_total": normalize_ws(valor_total),
            "transportadora_razao": normalize_ws(transportadora_razao),
            "transportadora_cnpj": normalize_ws(transportadora_cnpj),
            "transportadora_ie": normalize_ws(transportadora_ie),
            "transportadora_endereco": normalize_ws(transportadora_endereco),
        },
        "diagnostico": diagnostico,
        "texto_dest": texto_dest,
        "texto_transp": texto_transp,
        "texto_global": texto_global,
    }


# ========================= XML =========================
def get_namespace(root):
    match = re.match(r"\{(.+)\}", root.tag)
    return match.group(1) if match else None


def qname(ns, tag):
    return f"{{{ns}}}{tag}" if ns else tag


def child_text(elem, ns, tag):
    if elem is None:
        return ""
    return normalize_ws(elem.findtext(qname(ns, tag), ""))


def extrair_dados_xml(xml_file, lado_cliente="emit"):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    ns = get_namespace(root)

    emit = root.find(f".//{qname(ns, 'emit')}")
    dest = root.find(f".//{qname(ns, 'dest')}")
    transp = root.find(f".//{qname(ns, 'transporta')}")
    vol = root.find(f".//{qname(ns, 'vol')}")

    if lado_cliente == "dest" and dest is not None:
        entidade = dest
        endereco_tag = "enderDest"
    else:
        entidade = emit if emit is not None else dest
        endereco_tag = "enderEmit" if entidade is emit else "enderDest"

    end_elem = entidade.find(qname(ns, endereco_tag)) if entidade is not None else None

    log = child_text(end_elem, ns, "xLgr")
    nro = child_text(end_elem, ns, "nro")
    bairro = child_text(end_elem, ns, "xBairro")
    cidade = child_text(end_elem, ns, "xMun")
    uf = child_text(end_elem, ns, "UF")

    endereco_entidade = normalize_ws(" - ".join(filter(None, [
        f"{log}, {nro}".strip(", "),
        bairro,
        cidade,
        uf
    ])))

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


# ========================= RMA / ESPELHOS =========================
def extrair_valor_total_rma(texto_rma):
    return buscar_primeiro(
        texto_rma,
        [
            r"Tot[.]?\s*Liquido\(R\$\s*.*?\)\s*[:\-]?\s*([\d.,]+)",
            r"TOTAL GERAL\s*[:\-]?\s*([\d.,]+)",
            r"TOTAL\s*[:\-]?\s*R?\$?\s*([\d.,]+)",
        ],
    )


def extrair_campos_rma_psd(texto_rma):
    frete_raw = buscar_primeiro(texto_rma, [r"Frete\s*:\s*([^\n\r]+)"])
    return {
        "nome_cliente": buscar_primeiro(texto_rma, [r"Nome\/Raz[aã]o\s*Social:\s*([^\n\r]+)"]),
        "endereco_cliente": buscar_primeiro(
            texto_rma,
            [
                r"Endere[cç]o:\s*(.*?)\s+CEP",
                r"Endere[cç]o:\s*([^\n\r]+)",
            ],
        ),
        "cnpj_cliente": buscar_primeiro(texto_rma, [r"CPF\/CNPJ\s*[:\s]*([\d./-]+)"]),
        "quantidade_caixas": buscar_primeiro(texto_rma, [r"Volume:\s*(\d+)"]),
        "peso": buscar_primeiro(texto_rma, [r"Peso:\s*([\d.,]+)"]),
        "frete": normalizar_frete(frete_raw),
        "cfop": buscar_primeiro(texto_rma, [r"CFOP:\s*(\d{4})"]),
        "valor_total": extrair_valor_total_rma(texto_rma),
        "transportadora_razao": buscar_primeiro(texto_rma, [r"Transportadora:\s*([^\n\r]+)"]),
    }


def extrair_campos_rma_marca_a(texto_rma):
    # Ajuste futuro conforme o espelho real da marca A
    return extrair_campos_rma_psd(texto_rma)


def extrair_campos_rma_marca_b(texto_rma):
    # Ajuste futuro conforme o espelho real da marca B
    return extrair_campos_rma_psd(texto_rma)


def extrair_campos_rma(texto_rma, tipo_espelho):
    if tipo_espelho == "PSD":
        return extrair_campos_rma_psd(texto_rma)
    if tipo_espelho == "MARCA_A":
        return extrair_campos_rma_marca_a(texto_rma)
    if tipo_espelho == "MARCA_B":
        return extrair_campos_rma_marca_b(texto_rma)
    return extrair_campos_rma_psd(texto_rma)


# ========================= COMPARAÇÃO =========================
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

    if campo == "cnpj_cliente":
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
            melhor_nome = chave
            melhor_base = base
            melhor_score = score_total

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
    rows.append({
        "Campo": "Transportadora Razao (Base)",
        "Valor NF": nome_nf or "-",
        "Valor RMA": melhor_base["razao_social"],
        "Status": score_razao >= 0.80,
        "Detalhe": f"Melhor base: {melhor_nome}, similaridade={score_razao:.2f}",
    })

    cnpj_base = only_digits(melhor_base["cnpj"])
    rows.append({
        "Campo": "Transportadora CNPJ (Base)",
        "Valor NF": cnpj_nf or "-",
        "Valor RMA": cnpj_base,
        "Status": cnpj_nf == cnpj_base if cnpj_nf else None,
        "Detalhe": "Comparacao por CNPJ normalizado.",
    })

    ie_base = only_digits(melhor_base["ie"])
    rows.append({
        "Campo": "Transportadora IE (Base)",
        "Valor NF": ie_nf or "-",
        "Valor RMA": ie_base or "-",
        "Status": ie_nf == ie_base if (ie_nf and ie_base) else None,
        "Detalhe": "Comparacao por IE normalizada.",
    })

    score_end = similaridade(endereco_nf, melhor_base["endereco"])
    rows.append({
        "Campo": "Transportadora Endereco (Base)",
        "Valor NF": endereco_nf or "-",
        "Valor RMA": melhor_base["endereco"],
        "Status": score_end >= 0.75 if endereco_nf else None,
        "Detalhe": f"Similaridade endereco={score_end:.2f}",
    })

    return rows


def analisar_dados(dados_nf, dados_rma):
    rows = []

    for campo in CAMPOS_COMPARACAO:
        v_nf = dados_nf.get(campo, "")
        v_rma = dados_rma.get(campo, "")
        ok, detalhe = comparar_campo(campo, v_nf, v_rma)
        rows.append({
            "Campo": formatar_campo(campo),
            "Valor NF": normalize_ws(v_nf) or "-",
            "Valor RMA": normalize_ws(v_rma) or "-",
            "Status": ok,
            "Detalhe": detalhe,
        })

    rows.extend(validar_transportadora_catalogo(dados_nf))
    return pd.DataFrame(rows)


# ========================= STREAMLIT =========================
st.title("Verificador de Nota Fiscal x RMA - V3")
st.caption("Leitura da NF por blocos + âncoras, com XML prioritario e estrutura pronta para varios espelhos.")

with st.sidebar:
    st.subheader("Configuracoes")
    tipo_espelho = st.selectbox("Tipo de espelho / marca", TIPOS_ESPELHO)
    usar_ocr_nf = st.checkbox("Permitir OCR na NF quando necessario", value=True)
    lado_cliente_xml = st.selectbox(
        "Lado do cliente no XML",
        ["emit", "dest"],
        index=0,
        help="Ajuste conforme a regra do processo da marca.",
    )

col1, col2, col3 = st.columns(3)
with col1:
    nf_file = st.file_uploader("Enviar Nota Fiscal (PDF)", type=["pdf"])
with col2:
    rma_file = st.file_uploader("Enviar RMA / Espelho (PDF)", type=["pdf"])
with col3:
    xml_file = st.file_uploader("Enviar XML da NF-e", type=["xml"])

if rma_file:
    rma_bytes = rma_file.read()
    info_rma = extrair_texto_pdf_inteligente(rma_bytes, permitir_ocr=False)
    texto_rma = info_rma["texto"]
    dados_rma = extrair_campos_rma(texto_rma, tipo_espelho)

    nf_bytes = nf_file.read() if nf_file else None
    dados_nf = None
    origem_nf = ""
    diagnostico_nf = ""
    debug_nf_blocos = None

    if xml_file:
        try:
            dados_nf = extrair_dados_xml(xml_file, lado_cliente=lado_cliente_xml)
            origem_nf = f"XML ({lado_cliente_xml})"
            diagnostico_nf = "Dados da NF extraidos via XML."
        except Exception as exc:
            st.error(f"Falha ao ler XML: {exc}")
            st.stop()

    elif nf_bytes:
        info_nf = extrair_texto_pdf_inteligente(nf_bytes, permitir_ocr=usar_ocr_nf)

        try:
            resultado_blocos = extrair_campos_nf_por_blocos(nf_bytes)
            dados_nf_blocos = resultado_blocos["campos"]
            debug_nf_blocos = resultado_blocos
        except Exception as exc:
            dados_nf_blocos = {}
            debug_nf_blocos = {
                "diagnostico": {"erro_blocos": str(exc)},
                "texto_dest": "",
                "texto_transp": "",
                "texto_global": info_nf["texto"],
            }

        dados_nf_texto = {
            "nome_cliente": buscar_primeiro(info_nf["texto"], [
                r"NOME\/RAZAO SOCIAL\s*[:\-]?\s*([^\n\r]+)",
                r"RAZAO SOCIAL\s*[:\-]?\s*([^\n\r]+)"
            ]),
            "cnpj_cliente": buscar_primeiro(info_nf["texto"], [
                r"(?:CNPJ|CPF\/CNPJ)\s*[:\-]?\s*([\d./-]{11,18})",
                r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",
            ]),
            "endereco_cliente": buscar_primeiro(info_nf["texto"], [
                r"ENDERE[ÇC]O\s*[:\-]?\s*([^\n\r]+)"
            ]),
            "quantidade_caixas": buscar_primeiro(info_nf["texto"], [
                r"(?:QTD|QUANTIDADE|VOLUME(?:S)?)\s*[:\-]?\s*(\d+)"
            ]),
            "peso": buscar_primeiro(info_nf["texto"], [
                r"PESO\s*(?:BRUTO|B)\s*[:\-]?\s*([\d.,]+)",
                r"PESO\s*(?:L[IÍ]QUIDO|L)\s*[:\-]?\s*([\d.,]+)"
            ]),
            "frete": normalizar_frete(buscar_primeiro(info_nf["texto"], [
                r"FRETE\s*POR\s*CONTA\s*[:\-]?\s*([^\n\r]+)",
                r"MODALIDADE\s*DO\s*FRETE\s*[:\-]?\s*([^\n\r]+)"
            ])),
            "cfop": buscar_primeiro(info_nf["texto"], [
                r"\bCFOP\s*[:\-]?\s*(\d{4})\b",
                r"\b(5202|6202|6949)\b"
            ]),
            "valor_total": buscar_primeiro(info_nf["texto"], [
                r"VALOR TOTAL DA NOTA\s*[:\s]*([\d.,]+)",
                r"TOTAL DA NOTA\s*[:\s]*([\d.,]+)"
            ]),
            "transportadora_razao": buscar_primeiro(info_nf["texto"], [
                r"TRANSPORTADORA\s*[:\-]?\s*([^\n\r]+)",
                r"RAZ[AÃ]O SOCIAL\s*[:\-]?\s*([^\n\r]+)"
            ]),
            "transportadora_cnpj": buscar_primeiro(info_nf["texto"], [
                r"(?:CNPJ|CNPJ\/CPF)\s*[:\-]?\s*([\d./-]{11,18})"
            ]),
            "transportadora_ie": buscar_primeiro(info_nf["texto"], [
                r"INSCRI[ÇC][AÃ]O ESTADUAL\s*[:\-]?\s*([0-9A-Za-z./-]+)"
            ]),
            "transportadora_endereco": buscar_primeiro(info_nf["texto"], [
                r"ENDERE[ÇC]O\s*[:\-]?\s*([^\n\r]+)"
            ]),
        }

        dados_nf = {}
        for chave in [
            "nome_cliente",
            "cnpj_cliente",
            "endereco_cliente",
            "quantidade_caixas",
            "peso",
            "frete",
            "cfop",
            "valor_total",
            "transportadora_razao",
            "transportadora_cnpj",
            "transportadora_ie",
            "transportadora_endereco",
        ]:
            valor_blocos = normalize_ws(dados_nf_blocos.get(chave, ""))
            valor_texto = normalize_ws(dados_nf_texto.get(chave, ""))
            dados_nf[chave] = valor_blocos if valor_blocos else valor_texto

        origem_nf = f"PDF ({info_nf['fonte']} + blocos)"
        diagnostico_nf = info_nf["observacao"]

    else:
        st.info("Envie a NF em PDF ou o XML para iniciar a verificacao.")
        st.stop()

    st.markdown("### Diagnostico de leitura")
    st.write(f"- RMA: fonte={info_rma['fonte']}, score={info_rma['score']}.")
    st.write(f"- NF: origem={origem_nf}. {diagnostico_nf}")

    if debug_nf_blocos:
        diag = debug_nf_blocos.get("diagnostico", {})
        with st.expander("Debug da leitura por blocos"):
            st.json(diag)

    df = analisar_dados(dados_nf, dados_rma)
    df["Status"] = df["Status"].apply(label_status)

    st.markdown(f"### Comparacao dos dados (origem da NF: {origem_nf})")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Baixar relatorio CSV",
        data=csv,
        file_name="comparacao_nf_rma_v3.csv",
    )

    with st.expander("Campos extraidos da NF / XML"):
        st.json(dados_nf)

    with st.expander("Campos extraidos da RMA / Espelho"):
        st.json(dados_rma)

    if debug_nf_blocos:
        with st.expander("Texto capturado na area do DESTINATARIO / REMETENTE"):
            st.text(debug_nf_blocos.get("texto_dest", ""))

        with st.expander("Texto capturado na area do TRANSPORTE"):
            st.text(debug_nf_blocos.get("texto_transp", ""))

    guide_url = "https://raw.githubusercontent.com/Brayan-GBL/Controle/main/NFXRMA.jpg"
    st.markdown("---")
    st.subheader("Guia de consulta")
    st.image(guide_url, use_container_width=True)

    st.markdown("---")
    st.subheader("Visualizar PDFs")
    col_nf_prev, col_rma_prev = st.columns(2)

    with col_nf_prev:
        st.markdown("**Nota Fiscal**")
        if nf_bytes:
            for img in renderizar_paginas_para_preview(nf_bytes, n_paginas=3):
                st.image(img, use_container_width=True)
        else:
            st.info("Preview da NF indisponivel quando apenas o XML e enviado.")

    with col_rma_prev:
        st.markdown("**RMA / Espelho**")
        for img in renderizar_paginas_para_preview(rma_bytes, n_paginas=3):
            st.image(img, use_container_width=True)

else:
    st.info("Envie ao menos a RMA / Espelho para iniciar a verificacao.")
