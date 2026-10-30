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
        # 1. Conexión segura para evitar el error de base de datos
        with engine.connect() as conn:
            df = pd.read_sql('SELECT * FROM control_documentario ORDER BY "FECHA_DOC" DESC', conn)
            
        df.columns = df.columns.str.upper()
        
        if componente and componente != "Todos":
            df = df[df['COMPONENTE'] == componente]
        if entregable and entregable != "Todos":
            df = df[df['ENTREGABLE'] == entregable]

        df['FECHA_STR'] = pd.to_datetime(df['FECHA_DOC']).dt.strftime('%d/%m/%Y')
        cartas = df.to_dict(orient="records")

        # 2. Arquitectura blindada: Mini-tablas dentro de contenedores inquebrables
        filas_html = ""
        total_cartas = len(cartas)
        
        for i, c in enumerate(cartas):
            es_enviada = 'ENV' in str(c.get('ORIGEN_DOC', '')).upper()
            es_hito = 'HITO' in str(c.get('TIPO_EVENTO', '')).upper()
            es_ultimo = (i == total_cartas - 1)
            
            # Si es el último registro, borramos la línea para que no caiga al vacío
            color_borde = "transparent" if es_ultimo else "#E5E7EB"
            
            nro_doc = str(c.get('NRO_DOC', ''))
            if nro_doc.lower() in ['none', 'nan', '']: nro_doc = ""
            asunto = str(c.get('ASUNTO', ''))
            if asunto.lower() in ['none', 'nan']: asunto = ""

            if es_hito:
                linea_fondo = "" if es_ultimo else '<div class="center-line-bg"></div>'
                filas_html += f"""
                <tr>
                    <td style="padding: 0; border: none;">
                        <div style="page-break-inside: avoid; break-inside: avoid; width: 100%;">
                            <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                                <tr>
                                    <td colspan="2" class="td-center">
                                        {linea_fondo}
                                        <div class="dot-hito"></div>
                                        <div class="card card-hito">
                                            <span class="tag tag-hito">HITO CONTRACTUAL</span><span class="fecha">{c['FECHA_STR']}</span>
                                            <div class="asunto" style="font-weight: bold; color: #881337; font-size: 10pt;">{asunto}</div>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
                """
            elif es_enviada:
                filas_html += f"""
                <tr>
                    <td style="padding: 0; border: none;">
                        <div style="page-break-inside: avoid; break-inside: avoid; width: 100%;">
                            <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                                <tr>
                                    <td class="td-left" style="border-right: 2px solid {color_borde};">
                                        <div class="dot dot-enviada"></div>
                                        <div class="card card-enviada">
                                            <span class="tag tag-enviada">ENVIADA</span><span class="fecha">{c['FECHA_STR']}</span>
                                            <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                                        </div>
                                    </td>
                                    <td class="td-right"></td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
                """
            else:
                filas_html += f"""
                <tr>
                    <td style="padding: 0; border: none;">
                        <div style="page-break-inside: avoid; break-inside: avoid; width: 100%;">
                            <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                                <tr>
                                    <td class="td-left" style="border-right: 2px solid {color_borde};">
                                        <div class="dot dot-recibida"></div>
                                    </td>
                                    <td class="td-right">
                                        <div class="card card-recibida">
                                            <span class="tag tag-recibida">RECIBIDA</span><span class="fecha">{c['FECHA_STR']}</span>
                                            <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
                """

        # 3. Ensamblar HTML Maestro
        html_completo = f"""
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <style>
            *, *::before, *::after {{ box-sizing: border-box; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #111827; background-color: #F9FAFB; }}
            
            .main-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
            thead {{ display: table-header-group; }}
            
            .header {{ background-color: #1E293B; color: #F8FAFC; padding: 15px 20px; border-radius: 6px; text-align: left; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; font-size: 16pt; font-weight: bold; letter-spacing: 0.5px; }}
            .header h1 span {{ color: #94A3B8; font-weight: normal; font-size: 12pt; }}
            .header h2 {{ margin: 6px 0 0 0; font-size: 10pt; color: #CBD5E1; text-transform: uppercase; letter-spacing: 1px; }}
            
            .card {{ border-radius: 6px; padding: 12px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); width: 100%; position: relative; z-index: 2; }}
            .card-enviada {{ background-color: #EFF6FF; border: 1px solid #BFDBFE; text-align: right; }}
            .card-recibida {{ background-color: #FFFBEB; border: 1px solid #FDE68A; text-align: left; }}
            .card-hito {{ background-color: #FFF1F2; border: 1px solid #FCA5A5; border-left: 4px solid #9F1239; text-align: left; width: 85%; margin: 0 auto; }}
            
            .tag {{ font-size: 8pt; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 4px; display: block; }}
            .tag-enviada {{ color: #1E3A8A; }} .tag-recibida {{ color: #D97706; }} .tag-hito {{ color: #9F1239; }}
            .fecha {{ font-size: 8.5pt; color: #6B7280; font-weight: 500; margin-bottom: 6px; display: block; }}
            .nro-doc {{ font-size: 9.5pt; font-weight: bold; color: #111827; margin-bottom: 4px; }}
            .asunto {{ font-size: 8.5pt; color: #4B5563; line-height: 1.4; }}
            
            .td-left {{ width: 50%; padding: 15px 35px 15px 0; vertical-align: top; position: relative; }}
            .td-right {{ width: 50%; padding: 15px 0 15px 35px; vertical-align: top; position: relative; }}
            .td-center {{ width: 100%; padding: 25px 0; text-align: center; vertical-align: top; position: relative; }}
            
            .dot {{ position: absolute; top: 30px; width: 14px; height: 14px; border: 2px solid white; z-index: 5; }}
            /* Ambos puntos van anclados al borde de la columna izquierda para una simetría perfecta */
            .dot-enviada {{ right: -8px; background-color: #1E3A8A; border-radius: 50%; }}
            .dot-recibida {{ right: -8px; background-color: #D97706; border-radius: 50%; }}
            
            .center-line-bg {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background-color: #E5E7EB; margin-left: -1px; z-index: 1; }}
            .dot-hito {{ position: absolute; left: 50%; top: 30px; margin-left: -7px; width: 14px; height: 14px; background-color: #9F1239; border: 2px solid white; transform: rotate(45deg); z-index: 5; }}
        </style></head><body>
        
        <table class="main-table">
            <thead>
                <tr>
                    <th>
                        <div class="header">
                            <h1>CHACHAPOYAS <span>/ Control Documentario</span></h1>
                            <h2>Reporte de Línea de Tiempo: {componente} | {entregable}</h2>
                        </div>
                    </th>
                </tr>
            </thead>
            <tbody>
                {filas_html}
            </tbody>
        </table>
        
        </body></html>
        """

        # 4. Opciones simples y seguras para pdfkit
        options = {
            'page-size': 'A4',
            'margin-top': '12mm',
            'margin-right': '15mm',
            'margin-bottom': '12mm',
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
