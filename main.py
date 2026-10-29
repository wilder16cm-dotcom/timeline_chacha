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
        # 1. Traer y filtrar datos ordenados del más reciente al más antiguo (DESC)
        df = pd.read_sql('SELECT * FROM control_documentario ORDER BY "FECHA_DOC" DESC', engine)
        df.columns = df.columns.str.upper()
        
        if componente and componente != "Todos":
            df = df[df['COMPONENTE'] == componente]
        if entregable and entregable != "Todos":
            df = df[df['ENTREGABLE'] == entregable]

        df['FECHA_STR'] = pd.to_datetime(df['FECHA_DOC']).dt.strftime('%d/%m/%Y')
        cartas = df.to_dict(orient="records")

        # 2. Construir las filas dinámicamente usando múltiples TBODY para evitar cortes
        filas_html = ""
        for c in cartas:
            es_enviada = 'ENV' in str(c.get('ORIGEN_DOC', '')).upper()
            es_hito = 'HITO' in str(c.get('TIPO_EVENTO', '')).upper()
            
            nro_doc = str(c.get('NRO_DOC', ''))
            if nro_doc.lower() in ['none', 'nan', '']:
                nro_doc = ""
                
            asunto = str(c.get('ASUNTO', ''))
            if asunto.lower() in ['none', 'nan']:
                asunto = ""

            if es_hito:
                filas_html += f"""
                <tbody style="page-break-inside: avoid;">
                    <tr>
                        <td colspan="2" class="td-center">
                            <div class="center-line-bg"></div><div class="dot-hito"></div>
                            <div class="card card-hito">
                                <span class="tag tag-hito">HITO CONTRACTUAL</span><span class="fecha">{c['FECHA_STR']}</span>
                                <div class="asunto" style="font-weight: bold; color: #881337; font-size: 10pt;">{asunto}</div>
                            </div>
                        </td>
                    </tr>
                </tbody>
                """
            elif es_enviada:
                filas_html += f"""
                <tbody style="page-break-inside: avoid;">
                    <tr>
                        <td class="td-left">
                            <div class="dot dot-enviada"></div>
                            <div class="card card-enviada">
                                <span class="tag tag-enviada">ENVIADA</span><span class="fecha">{c['FECHA_STR']}</span>
                                <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                            </div>
                        </td>
                        <td class="td-right"></td>
                    </tr>
                </tbody>
                """
            else:
                filas_html += f"""
                <tbody style="page-break-inside: avoid;">
                    <tr>
                        <td class="td-left"></td>
                        <td class="td-right">
                            <div class="dot dot-recibida"></div>
                            <div class="card card-recibida">
                                <span class="tag tag-recibida">RECIBIDA</span><span class="fecha">{c['FECHA_STR']}</span>
                                <div class="nro-doc">{nro_doc}</div><div class="asunto">{asunto}</div>
                            </div>
                        </td>
                    </tr>
                </tbody>
                """

        # 3. Ensamblar el HTML general
        html_completo = f"""
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <style>
            *, *::before, *::after {{ box-sizing: border-box; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #111827; background-color: #F9FAFB; }}
            .timeline-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
            
            thead {{ display: table-header-group; }}
            
            .header {{ background-color: #1E293B; color: #F8FAFC; padding: 15px 20px; border-radius: 6px; text-align: left; }}
            .header h1 {{ margin: 0; font-size: 16pt; font-weight: bold; letter-spacing: 0.5px; }}
            .header h1 span {{ color: #94A3B8; font-weight: normal; font-size: 12pt; }}
            .header h2 {{ margin: 6px 0 0 0; font-size: 10pt; color: #CBD5E1; text-transform: uppercase; letter-spacing: 1px; }}
            
            .card {{ border-radius: 6px; padding: 12px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); width: 100%; position: relative; z-index: 2; }}
            .card-enviada {{ background-color: #EFF6FF; border: 1px solid #BFDBFE; text-align: right; }}
            .card-recibida {{ background-color: #FFFBEB; border: 1px solid #FDE68A; text-align: left; }}
            .card-hito {{ background-color: #FFF1F2; border: 1px solid #FCA5A5; border-left: 4px solid #9F1239; text-align: left; display: inline-block; width: 75%; margin: 0 auto; }}
            
            .tag {{ font-size: 8pt; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 4px; display: block; }}
            .tag-enviada {{ color: #1E3A8A; }} .tag-recibida {{ color: #D97706; }} .tag-hito {{ color: #9F1239; }}
            .fecha {{ font-size: 8.5pt; color: #6B7280; font-weight: 500; margin-bottom: 6px; display: block; }}
            .nro-doc {{ font-size: 9.5pt; font-weight: bold; color: #111827; margin-bottom: 4px; }}
            .asunto {{ font-size: 8.5pt; color: #4B5563; line-height: 1.3; }}
            
            .td-left {{ width: 50%; padding: 8px 25px 15px 0; vertical-align: top; border-right: 2px solid #E5E7EB; position: relative; }}
            .td-right {{ width: 50%; padding: 8px 0 15px 25px; vertical-align: top; position: relative; }}
            .dot {{ position: absolute; top: 20px; width: 12px; height: 12px; border: 2px solid white; z-index: 5; }}
            .dot-enviada {{ right: -7px; background-color: #1E3A8A; border-radius: 50%; }}
            .dot-recibida {{ left: -7px; background-color: #D97706; border-radius: 50%; }}
            .td-center {{ padding: 15px 0; text-align: center; vertical-align: middle; position: relative; }}
            .center-line-bg {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background-color: #E5E7EB; margin-left: -1px; z-index: 1; }}
            .dot-hito {{ position: relative; z-index: 5; width: 14px; height: 14px; background-color: #9F1239; border: 2px solid white; margin: 0 auto 10px auto; transform: rotate(45deg); }}
        </style></head><body>
        
        <table class="timeline-table">
            <thead>
                <tr>
                    <th colspan="2" style="padding-bottom: 20px; font-weight: normal;">
                        <div class="header">
                            <h1>CHACHAPOYAS <span>/ Control Documentario</span></h1>
                            <h2>Reporte de Línea de Tiempo: {componente} | {entregable}</h2>
                        </div>
                    </th>
                </tr>
            </thead>
            <!-- El string de filas_html ahora inyecta directamente bloques TBODY independientes -->
            {filas_html}
        </table>
        
        </body></html>
        """

        # 4. Generar y devolver el PDF
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
