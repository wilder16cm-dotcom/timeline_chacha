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
        df = pd.read_sql("SELECT * FROM control_documentario ORDER BY \"FECHA_DOC\" ASC", engine)
        df.columns = df.columns.str.upper()
        
        if componente and componente != "Todos":
            df = df[df['COMPONENTE'] == componente]
        if entregable and entregable != "Todos":
            df = df[df['ENTREGABLE'] == entregable]

        df['FECHA_STR'] = pd.to_datetime(df['FECHA_DOC']).dt.strftime('%d/%m/%Y')
        cartas = df.to_dict(orient="records")

        # Invertimos el orden para que coincida con tu panel izquierdo (de más reciente a más antiguo)
        cartas.reverse()

        filas_html = ""
        for i, c in enumerate(cartas):
            es_enviada = 'ENV' in str(c.get('ORIGEN_DOC', '')).upper()
            es_hito = 'HITO' in str(c.get('TIPO_EVENTO', '')).upper()
            es_recibida = not es_enviada and not es_hito

            # Ocultamos la línea de continuación en el último elemento absoluto
            estilo_borde = 'border-right: 2px solid transparent;' if i == len(cartas) - 1 else 'border-right: 2px solid #E5E7EB;'

            if es_hito:
                filas_html += f"""
                <tr style="page-break-inside: avoid !important;">
                    <td colspan="2" style="padding: 20px 0; text-align: center; vertical-align: middle; position: relative;">
                        <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background-color: #E5E7EB; margin-left: -1px; z-index: 1;"></div>
                        <div style="position: relative; z-index: 5; width: 14px; height: 14px; background-color: #9F1239; border: 2px solid white; margin: 0 auto 15px auto; transform: rotate(45deg);"></div>
                        <div style="background-color: #FFF1F2; border: 1px solid #FCA5A5; border-left: 4px solid #9F1239; text-align: left; display: inline-block; width: 75%; margin: 0 auto; border-radius: 6px; padding: 14px 18px; position: relative; z-index: 2;">
                            <span style="font-size: 8pt; font-weight: bold; color: #9F1239; margin-bottom: 6px; display: block;">HITO CONTRACTUAL</span>
                            <span style="font-size: 9pt; color: #6B7280; font-weight: 500; margin-bottom: 8px; display: block;">{c['FECHA_STR']}</span>
                            <div style="font-weight: bold; color: #881337; font-size: 10pt;">{c['ASUNTO']}</div>
                        </div>
                    </td>
                </tr>
                """
            elif es_enviada:
                filas_html += f"""
                <tr style="page-break-inside: avoid !important;">
                    <td style="width: 50%; padding: 10px 30px 20px 20px; vertical-align: top; {estilo_borde} position: relative;">
                        <div style="position: absolute; top: 25px; right: -7px; width: 12px; height: 12px; background-color: #1E3A8A; border: 2px solid white; border-radius: 50%; z-index: 5;"></div>
                        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; text-align: right; border-radius: 6px; padding: 14px 18px; width: 100%; position: relative; z-index: 2;">
                            <span style="font-size: 8pt; font-weight: bold; color: #1E3A8A; margin-bottom: 6px; display: block;">ENVIADA</span>
                            <span style="font-size: 9pt; color: #6B7280; font-weight: 500; margin-bottom: 8px; display: block;">{c['FECHA_STR']}</span>
                            <div style="font-size: 10pt; font-weight: bold; color: #111827; margin-bottom: 6px;">{c.get('NRO_DOC', '')}</div>
                            <div style="font-size: 9pt; color: #4B5563; line-height: 1.4;">{c['ASUNTO']}</div>
                        </div>
                    </td>
                    <td style="width: 50%; padding: 10px 20px 20px 30px; vertical-align: top;"></td>
                </tr>
                """
            else:
                filas_html += f"""
                <tr style="page-break-inside: avoid !important;">
                    <td style="width: 50%; padding: 10px 30px 20px 20px; vertical-align: top; {estilo_borde}">
                        <div style="position: absolute; right: -2px; top: 0; height: 25px; width: 2px; background: #E5E7EB; z-index: 1; display: {'block' if i == len(cartas)-1 else 'none'};"></div>
                    </td>
                    <td style="width: 50%; padding: 10px 20px 20px 30px; vertical-align: top; position: relative;">
                        <div style="position: absolute; top: 25px; left: -7px; width: 12px; height: 12px; background-color: #D97706; border: 2px solid white; border-radius: 50%; z-index: 5;"></div>
                        <div style="background-color: #FFFBEB; border: 1px solid #FDE68A; text-align: left; border-radius: 6px; padding: 14px 18px; width: 100%; position: relative; z-index: 2;">
                            <span style="font-size: 8pt; font-weight: bold; color: #D97706; margin-bottom: 6px; display: block;">RECIBIDA</span>
                            <span style="font-size: 9pt; color: #6B7280; font-weight: 500; margin-bottom: 8px; display: block;">{c['FECHA_STR']}</span>
                            <div style="font-size: 10pt; font-weight: bold; color: #111827; margin-bottom: 6px;">{c.get('NRO_DOC', '')}</div>
                            <div style="font-size: 9pt; color: #4B5563; line-height: 1.4;">{c['ASUNTO']}</div>
                        </div>
                    </td>
                </tr>
                """

        html_completo = f"""
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 0; }}
            *, *::before, *::after {{ box-sizing: border-box; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #111827; background-color: white; }}
        </style></head><body>
        <table style="width: 100%; border-collapse: collapse;">
            <thead style="display: table-header-group;">
                <tr>
                    <td>
                        <div style="background-color: #1E293B; color: #F8FAFC; padding: 20px 25px; margin: 20px 20px 30px 20px; border-radius: 6px;">
                            <h1 style="margin: 0; font-size: 16pt; font-weight: bold; letter-spacing: 0.5px;">CHACHAPOYAS <span style="color: #94A3B8; font-weight: normal; font-size: 12pt;">/ Control Documentario</span></h1>
                            <h2 style="margin: 8px 0 0 0; font-size: 10pt; color: #CBD5E1; text-transform: uppercase; letter-spacing: 1px;">Reporte de Línea de Tiempo: {componente} | {entregable}</h2>
                        </div>
                    </td>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <table style="width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px;">
                            {filas_html}
                        </table>
                    </td>
                </tr>
            </tbody>
        </table>
        </body></html>
        """

        options = {{
            'page-size': 'A4',
            'margin-top': '0mm',
            'margin-right': '0mm',
            'margin-bottom': '10mm',
            'margin-left': '0mm',
            'encoding': "UTF-8",
            'no-outline': None
        }}
        
        pdf_bytes = pdfkit.from_string(html_completo, False, options=options)
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={{"Content-Disposition": f'attachment; filename="Linea_Tiempo_{componente}_{entregable}.pdf"'}}
        )
    except Exception as e:
        return {{"error": str(e)}}

