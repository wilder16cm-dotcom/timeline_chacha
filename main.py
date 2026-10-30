import os
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from typing import Optional
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
import io
import pdfkit
import tempfile


# 1. Cargar variables de entorno ocultas
load_dotenv()
DB_URL = os.getenv("DB_URL")

# 2. Conexión a Neon
engine = create_engine(DB_URL)

# 3. Inicializar la app web
app = FastAPI(title="API CHACHA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Endpoints
@app.get("/cartas")
def obtener_cartas(
    componente: Optional[str] = Query(None),
    entregable: Optional[str] = Query(None),
    busqueda: Optional[str] = Query(None)
):
    df = pd.read_sql('SELECT * FROM control_documentario ORDER BY "FECHA_DOC" ASC', engine)
    df.columns = df.columns.str.upper()

    if componente and componente != "Todos":
        df = df[df['COMPONENTE'] == componente]
    if entregable and entregable != "Todos":
        df = df[df['ENTREGABLE'] == entregable]
    if busqueda:
        df = df[
            df['ASUNTO'].str.contains(busqueda, case=False, na=False) |
            df['NRO_DOC'].str.contains(busqueda, case=False, na=False)
        ]

    df['FECHA_STR'] = pd.to_datetime(df['FECHA_DOC']).dt.strftime('%d/%m/%Y')
    
    # Escudo protector
    if 'NRO_EXPENDIENTE' in df.columns:
        df['NRO_EXPENDIENTE'] = df['NRO_EXPENDIENTE'].fillna("").astype(str).str.strip()
        df['NRO_EXPENDIENTE'] = df.apply(lambda x: "" if str(x['NRO_EXPENDIENTE']).lower() in ["none", "nan", ""] else x['NRO_EXPENDIENTE'], axis=1)
    else:
        df['NRO_EXPENDIENTE'] = ""

    df = df.fillna("")
    return df.to_dict(orient="records")

@app.get("/filtros")
def obtener_opciones_filtros(componente: Optional[str] = Query(None)):
    df = pd.read_sql('SELECT "COMPONENTE", "ENTREGABLE" FROM control_documentario', engine)
    df.columns = df.columns.str.upper()
    
    componentes = df['COMPONENTE'].dropna().unique().tolist()
    
    if componente and componente != "Todos":
        entregables = df[df['COMPONENTE'] == componente]['ENTREGABLE'].dropna().unique().tolist()
    else:
        entregables = df['ENTREGABLE'].dropna().unique().tolist()
        
    return {
        "componentes": ["Todos"] + [c for c in componentes if c],
        "entregables": ["Todos"] + [e for e in entregables if e]
    }

@app.get("/links")
def obtener_links():
    try:
        df_n = pd.read_sql("SELECT * FROM links_drive", engine)
        df_n.rename(columns={'NOMBRE': 'Nombre', 'URL': 'URL', 'CARPETA': 'Carpeta'}, inplace=True)
        if 'Carpeta' not in df_n.columns:
            df_n['Carpeta'] = ""
        df_n = df_n.fillna("")
        return df_n.to_dict(orient="records")
    except Exception as e:
        print(f"Error links: {e}")
        return []

@app.get("/cartas-completas")
def obtener_cartas_completas():
    try:
        df_cartas = pd.read_sql("SELECT * FROM control_documentario", engine)
        df_links = pd.read_sql("SELECT * FROM links_drive", engine)
        
        df_cartas['LLAVE_CRUCE'] = df_cartas['NRO_DOC'] + '.pdf'
        
        df_final = pd.merge(
            df_cartas, 
            df_links[['NOMBRE', 'URL']], 
            left_on='LLAVE_CRUCE', 
            right_on='NOMBRE', 
            how='left'
        )
        
        df_final.drop(columns=['LLAVE_CRUCE', 'NOMBRE'], inplace=True)
        df_final = df_final.fillna("")
        
        return df_final.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@app.get("/reporte-pdf")
def generar_reporte_pdf(
    componente: str = Query("PGV"),
    entregable: str = Query("Segundo Informe")
):
    try:
        with engine.connect() as conn:
            df = pd.read_sql('SELECT * FROM control_documentario ORDER BY "FECHA_DOC" DESC', conn)
            
        df.columns = df.columns.str.upper()
        
        if componente and componente != "Todos":
            df = df[df['COMPONENTE'] == componente]
        if entregable and entregable != "Todos":
            df = df[df['ENTREGABLE'] == entregable]

        df['FECHA_STR'] = pd.to_datetime(df['FECHA_DOC']).dt.strftime('%d/%m/%Y')
        cartas = df.to_dict(orient="records")

        # 1. Filas usando BLOQUES BLINDADOS (Inmunes al corte de página)
        filas_html = ""
        for i, c in enumerate(cartas):
            es_enviada = 'ENV' in str(c.get('ORIGEN_DOC', '')).upper()
            es_hito = 'HITO' in str(c.get('TIPO_EVENTO', '')).upper()
            es_ultimo = (i == len(cartas) - 1)
            
            borde = "transparent" if es_ultimo else "#E5E7EB"
            
            nro_doc = str(c.get('NRO_DOC', ''))
            if nro_doc.lower() in ['none', 'nan', '']: nro_doc = ""
            asunto = str(c.get('ASUNTO', ''))
            if asunto.lower() in ['none', 'nan']: asunto = ""

            if es_hito:
                filas_html += f"""
                <div class="item">
                    <div class="line" style="background-color: {borde};"></div>
                    <div class="center-content">
                        <div class="dot-hito"></div>
                        <div class="card card-hito">
                            <span class="tag tag-hito">HITO CONTRACTUAL</span><span class="fecha">{c['FECHA_STR']}</span>
                            <div class="asunto" style="font-weight: bold; color: #881337; font-size: 10pt;">{asunto}</div>
                        </div>
                    </div>
                </div>
                """
            elif es_enviada:
                filas_html += f"""
                <div class="item">
                    <div class="line" style="background-color: {borde};"></div>
                    <div class="left-col">
                        <div class="dot dot-enviada"></div>
                        <div class="card card-enviada">
                            <span class="tag tag-enviada">ENVIADA</span><span class="fecha">{c['FECHA_STR']}</span>
                            <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                        </div>
                    </div>
                </div>
                """
            else:
                filas_html += f"""
                <div class="item">
                    <div class="line" style="background-color: {borde};"></div>
                    <div class="right-col">
                        <div class="dot dot-recibida"></div>
                        <div class="card card-recibida">
                            <span class="tag tag-recibida">RECIBIDA</span><span class="fecha">{c['FECHA_STR']}</span>
                            <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                        </div>
                    </div>
                </div>
                """

        # 2. HTML Maestro: Mezcla del Encabezado Flotante y la Tabla Fantasma
        html_completo = f"""
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <style>
            *, *::before, *::after {{ box-sizing: border-box; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #111827; background-color: #F9FAFB; }}
            
            /* TRUCO 1: ENCABEZADO FIJO (Imprime en todas las hojas automáticamente) */
            .fixed-header {{
                position: fixed;
                top: 0; left: 0; width: 100%; height: 85px;
                background-color: #1E293B; color: #F8FAFC;
                padding: 15px 20px; border-radius: 6px;
                z-index: 9999; text-align: left;
            }}
            .fixed-header h1 {{ margin: 0; font-size: 16pt; font-weight: bold; letter-spacing: 0.5px; }}
            .fixed-header h1 span {{ color: #94A3B8; font-weight: normal; font-size: 12pt; }}
            .fixed-header h2 {{ margin: 6px 0 0 0; font-size: 10pt; color: #CBD5E1; text-transform: uppercase; letter-spacing: 1px; }}
            
            /* TRUCO 2: TABLA FANTASMA (Evita que el texto choque con el encabezado) */
            .ghost-table {{ width: 100%; border-collapse: collapse; border: none; }}
            .ghost-table thead {{ display: table-header-group; }}
            .spacer {{ height: 110px; border: none; padding: 0; margin: 0; }}
            
            /* ESTILOS DE BLOQUES INQUEBRANTABLES */
            .item {{ page-break-inside: avoid !important; break-inside: avoid !important; position: relative; width: 100%; display: block; clear: both; min-height: 60px; }}
            .item::after {{ content: ""; display: table; clear: both; }}
            
            .line {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; margin-left: -1px; z-index: 1; }}
            
            .left-col {{ width: 50%; float: left; padding-right: 35px; padding-bottom: 20px; position: relative; }}
            .right-col {{ width: 50%; float: right; padding-left: 35px; padding-bottom: 20px; position: relative; }}
            .center-content {{ width: 100%; clear: both; padding-bottom: 20px; text-align: center; position: relative; z-index: 10; }}
            
            .card {{ border-radius: 6px; padding: 12px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); width: 100%; position: relative; z-index: 2; }}
            .card-enviada {{ background-color: #EFF6FF; border: 1px solid #BFDBFE; text-align: right; }}
            .card-recibida {{ background-color: #FFFBEB; border: 1px solid #FDE68A; text-align: left; }}
            .card-hito {{ background-color: #FFF1F2; border: 1px solid #FCA5A5; border-left: 4px solid #9F1239; text-align: left; display: inline-block; width: 75%; margin: 0 auto; }}
            
            .tag {{ font-size: 8pt; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 4px; display: block; }}
            .tag-enviada {{ color: #1E3A8A; }} .tag-recibida {{ color: #D97706; }} .tag-hito {{ color: #9F1239; }}
            .fecha {{ font-size: 8.5pt; color: #6B7280; font-weight: 500; margin-bottom: 6px; display: block; }}
            .nro-doc {{ font-size: 9.5pt; font-weight: bold; color: #111827; margin-bottom: 4px; }}
            .asunto {{ font-size: 8.5pt; color: #4B5563; line-height: 1.4; }}
            
            .dot {{ position: absolute; top: 15px; width: 14px; height: 14px; border: 2px solid white; z-index: 5; border-radius: 50%; }}
            .dot-enviada {{ right: -8px; background-color: #1E3A8A; }}
            .dot-recibida {{ left: -8px; background-color: #D97706; }}
            .dot-hito {{ margin: 0 auto 10px auto; width: 14px; height: 14px; background-color: #9F1239; border: 2px solid white; transform: rotate(45deg); display: block; position: relative; z-index: 5; }}
        </style></head><body>
        
        <!-- EL ENCABEZADO FLOTANTE -->
        <div class="fixed-header">
            <h1>CHACHAPOYAS <span>/ Control Documentario</span></h1>
            <h2>Reporte de Línea de Tiempo: {componente} | {entregable}</h2>
        </div>
        
        <!-- LA ESTRUCTURA INQUEBRANTABLE -->
        <table class="ghost-table">
            <thead>
                <tr><th class="spacer"></th></tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 0; border: none;">
                        {filas_html}
                    </td>
                </tr>
            </tbody>
        </table>
        
        </body></html>
        """

        # 3. Opciones seguras sin depender de comandos bloqueados del servidor
        options = {
            'page-size': 'A4',
            'margin-top': '10mm',
            'margin-right': '15mm',
            'margin-bottom': '10mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
            'no-outline': None
        }

        pdf_bytes = pdfkit.from_string(html_completo, False, options=options)
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Linea_Tiempo_{componente}_{entregable}.pdf"'}
        )
    except Exception as e:
        return {"error": str(e)}
