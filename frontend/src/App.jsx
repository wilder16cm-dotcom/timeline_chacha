import { useState, useEffect } from 'react'

function App() {
  const [cartas, setCartas] = useState([])
  const [links, setLinks] = useState([])
  const [filtrosOpciones, setFiltrosOpciones] = useState({ componentes: [], entregables: [] })
  
  // Filtros por defecto activados
  const [componente, setComponente] = useState('PGV')
  const [entregable, setEntregable] = useState('Segundo Informe')
  const [busqueda, setBusqueda] = useState('')
  
  const [docSeleccionado, setDocSeleccionado] = useState(null)
  const [pdfActual, setPdfActual] = useState(null)
  const [anexos, setAnexos] = useState([])

  useEffect(() => {
    fetch(`https://timeline-chacha.onrender.com/filtros?componente=${componente}`)
      .then(res => res.json())
      .then(data => setFiltrosOpciones(data))
      
    fetch('https://timeline-chacha.onrender.com/links')
      .then(res => res.json())
      .then(data => setLinks(data))
  }, [componente])

  useEffect(() => {
    const url = new URL('https://timeline-chacha.onrender.com/cartas');
    if (componente && componente !== 'Todos') url.searchParams.append('componente', componente);
    if (entregable && entregable !== 'Todos') url.searchParams.append('entregable', entregable);
    if (busqueda) url.searchParams.append('busqueda', busqueda);

    fetch(url)
      .then(res => res.json())
      .then(data => setCartas(data))
  }, [componente, entregable, busqueda])

  const parseDate = (dStr) => {
    if (!dStr) return new Date().getTime();
    const parts = dStr.split('/');
    if (parts.length === 3) return new Date(parts[2], parts[1] - 1, parts[0]).getTime();
    return new Date().getTime();
  };

  const cartasConTs = cartas.map(c => ({ ...c, ts: parseDate(c.FECHA_STR) }));
  const minTs = cartasConTs.length > 0 ? Math.min(...cartasConTs.map(c => c.ts)) : 0;
  const maxTs = cartasConTs.length > 0 ? Math.max(...cartasConTs.map(c => c.ts)) : 0;
  const timeRange = maxTs - minTs || 1; 

  const nodosPlanoLlave = {};
  cartasConTs.forEach(c => {
    if (!nodosPlanoLlave[c.FECHA_STR]) {
      nodosPlanoLlave[c.FECHA_STR] = { ts: c.ts, hasHito: false, hasEnv: false, hasRec: false, fechaStr: c.FECHA_STR, docs: [] };
    }
    // Guardamos el nombre del documento para el tooltip
    nodosPlanoLlave[c.FECHA_STR].docs.push(c.NRO_DOC);
    
    if (c.TIPO_EVENTO?.toUpperCase().includes('HITO')) nodosPlanoLlave[c.FECHA_STR].hasHito = true;
    else if (c.ORIGEN_DOC?.toUpperCase().includes('ENV')) nodosPlanoLlave[c.FECHA_STR].hasEnv = true;
    else nodosPlanoLlave[c.FECHA_STR].hasRec = true;
  });
  const nodosUnicos = Object.values(nodosPlanoLlave);

  const tituloContexto = componente !== 'Todos' ? `${componente} ${entregable !== 'Todos' ? `| ${entregable}` : ''}` : 'Visión General de Proyecto';

  const handleSeleccionarDocumento = (carta) => {
    setDocSeleccionado(carta);
    const nroDocLimpiado = carta.NRO_DOC.trim().toUpperCase();
    const nombrePdfEsperado = `${nroDocLimpiado}.PDF`;

    const matchPrincipal = links.find(l => 
      (l.Nombre || '').trim().toUpperCase() === nombrePdfEsperado || 
      (l.Nombre || '').trim().toUpperCase() === nroDocLimpiado
    );

    const matchAnexos = links.filter(l => 
      (l.Carpeta || '').trim().toUpperCase() === nroDocLimpiado && 
      (l.Nombre || '').trim().toUpperCase() !== nombrePdfEsperado &&
      (l.Nombre || '').trim().toUpperCase() !== nroDocLimpiado
    );

    if (matchPrincipal && matchPrincipal.URL) {
      let urlLimpia = matchPrincipal.URL.trim();
      if (urlLimpia.includes("drive.google.com") && urlLimpia.includes("/view")) {
        urlLimpia = urlLimpia.split("/view")[0] + "/preview";
      }
      setPdfActual({ nombre: 'Documento Principal', url: urlLimpia, esPrincipal: true, urlPrincipal: urlLimpia });
    } else {
      setPdfActual(null);
    }
    setAnexos(matchAnexos);
  };

  const handleDescargarPDF = () => {
    // Apuntamos al backend para que nos genere el PDF
    const url = `https://timeline-chacha.onrender.com/reporte-pdf?componente=${encodeURIComponent(componente)}&entregable=${encodeURIComponent(entregable)}`;
    window.open(url, '_blank');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', backgroundColor: '#F3F4F6', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      
      {/* NAVBAR */}
      <div style={{ backgroundColor: '#1E293B', padding: '12px 24px', display: 'flex', alignItems: 'center', flexShrink: 0, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h2 style={{ margin: 0, color: '#F8FAFC', fontSize: '1.15rem', whiteSpace: 'nowrap', marginRight: 'auto', letterSpacing: '0.5px' }}>
          CHACHAPOYAS <span style={{ color: '#94A3B8', fontSize: '0.9rem', fontWeight: '400' }}>/ Control Documentario</span>
        </h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <input type="text" placeholder="Búsqueda por asunto..." value={busqueda} onChange={(e) => setBusqueda(e.target.value)} style={{ width: '220px', padding: '6px 12px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#0F172A', color: 'white', outline: 'none', fontSize: '0.85rem' }} />
          <select value={componente} onChange={(e) => { setComponente(e.target.value); setEntregable('Todos'); }} style={{ width: '160px', padding: '6px 12px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#0F172A', color: 'white', outline: 'none', fontSize: '0.85rem' }}>
            {filtrosOpciones.componentes?.map(comp => <option key={comp} value={comp}>{comp}</option>)}
          </select>
          <select value={entregable} onChange={(e) => setEntregable(e.target.value)} style={{ width: '160px', padding: '6px 12px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#0F172A', color: 'white', outline: 'none', fontSize: '0.85rem' }}>
            {filtrosOpciones.entregables?.map(ent => <option key={ent} value={ent}>{ent}</option>)}
          </select>
          <button 
            onClick={handleDescargarPDF}
            style={{ backgroundColor: '#2563EB', color: 'white', border: 'none', padding: '7px 14px', borderRadius: '4px', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.1)', transition: 'background-color 0.2s' }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#1D4ED8'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2563EB'}
          >
            📄 Generar PDF
          </button>
        </div>
      </div>

      {/* PLANO LLAVE */}
      <div style={{ backgroundColor: 'white', borderBottom: '1px solid #E5E7EB', padding: '16px 32px', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ margin: 0, fontSize: '0.75rem', color: '#6B7280', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '600' }}>{tituloContexto}</h3>
          
          {/* LEYENDA ACTUALIZADA */}
          <div style={{ display: 'flex', gap: '16px', fontSize: '0.7rem', fontWeight: '600', color: '#6B7280' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '6px solid #1E3A8A' }}></div> ENVIADAS</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '6px solid #D97706' }}></div> RECIBIDAS</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '8px', height: '8px', backgroundColor: '#9F1239', transform: 'rotate(45deg)' }}></div> HITOS</div>
          </div>
        </div>
        
        {/* LÍNEA DE TIEMPO CON GEOMETRÍA Y TOOLTIPS */}
        <div style={{ position: 'relative', height: '80px', margin: '0 20px' }}>
          <div style={{ position: 'absolute', top: '40px', left: 0, right: 0, height: '2px', backgroundColor: '#E5E7EB' }}></div>
          
          {nodosUnicos.map((nodo, index) => {
            const leftPercent = ((nodo.ts - minTs) / timeRange) * 100;
            const tooltipText = nodo.docs.join('\n');
            
            return (
              <div key={`keyplan-${index}`} style={{ position: 'absolute', left: `${leftPercent}%`, top: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2 }}>
                
                {/* ENVIADAS (Triángulo apuntando abajo) */}
                {nodo.hasEnv && (
                  <div style={{ position: 'absolute', bottom: '2px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: '#1E3A8A', fontWeight: '600', marginBottom: '2px', whiteSpace: 'nowrap' }}>{nodo.fechaStr.substring(0,5)}</div>
                    <div title={tooltipText} style={{ width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderTop: '8px solid #1E3A8A', cursor: 'pointer' }}></div>
                  </div>
                )}

                {/* HITOS (Rombo central) */}
                {nodo.hasHito && (
                  <div style={{ position: 'absolute', top: '-6px', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 3 }}>
                    <div title={tooltipText} style={{ width: '12px', height: '12px', backgroundColor: '#9F1239', transform: 'rotate(45deg)', cursor: 'pointer', border: '1px solid white' }}></div>
                    {(!nodo.hasEnv && !nodo.hasRec) && <div style={{ marginTop: '14px', fontSize: '0.65rem', color: '#9F1239', fontWeight: '700', whiteSpace: 'nowrap' }}>{nodo.fechaStr.substring(0,5)}</div>}
                  </div>
                )}

                {/* RECIBIDAS (Triángulo apuntando arriba) */}
                {nodo.hasRec && (
                  <div style={{ position: 'absolute', top: '4px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div title={tooltipText} style={{ width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderBottom: '8px solid #D97706', cursor: 'pointer' }}></div>
                    <div style={{ marginTop: '2px', fontSize: '0.65rem', color: '#D97706', fontWeight: '600', whiteSpace: 'nowrap' }}>{nodo.fechaStr.substring(0,5)}</div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ÁREA DE TRABAJO */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* PANEL VERTICAL (Invertido: de más nuevo a más viejo) */}
        <div style={{ width: '35%', minWidth: '420px', backgroundColor: '#FAFAFA', borderRight: '1px solid #E5E7EB', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
            {[...cartasConTs].sort((a, b) => b.ts - a.ts).map((carta, index) => {
              const esEnviada = carta.ORIGEN_DOC?.toUpperCase().includes('ENV');
              const esHito = carta.TIPO_EVENTO?.toUpperCase().includes('HITO');
              const isActive = docSeleccionado && docSeleccionado.NRO_DOC === carta.NRO_DOC;
              
              if (esHito) {
                return (
                  <div key={index} onClick={() => handleSeleccionarDocumento(carta)} style={{ marginBottom: '24px', padding: '16px', backgroundColor: isActive ? '#FFE4E6' : '#FFF1F2', border: '1px solid #FCA5A5', borderLeft: '4px solid #9F1239', borderRadius: '6px', boxShadow: isActive ? '0 0 0 2px #9F1239' : '0 1px 2px rgba(0,0,0,0.02)', cursor: 'pointer', transition: 'all 0.2s' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: '#9F1239', letterSpacing: '0.5px' }}>HITO CONTRACTUAL</span>
                      <span style={{ fontSize: '0.7rem', color: '#9F1239', fontWeight: '500' }}>{carta.FECHA_STR}</span>
                    </div>
                    <div style={{ fontWeight: '600', color: '#881337', fontSize: '0.9rem', marginBottom: '4px' }}>{carta.NRO_DOC}</div>
                    <div style={{ fontSize: '0.75rem', color: '#9F1239' }}>{carta.ASUNTO}</div>
                  </div>
                );
              }

              let mainColor = esEnviada ? '#1E3A8A' : '#D97706';
              let bgColor = esEnviada ? (isActive ? '#DBEAFE' : '#EFF6FF') : (isActive ? '#FEF3C7' : '#FFFBEB');
              let borderColor = esEnviada ? '#BFDBFE' : '#FDE68A';
              let tagText = esEnviada ? 'ENVIADA' : 'RECIBIDA';

              return (
                <div key={index} onClick={() => handleSeleccionarDocumento(carta)} style={{ position: 'relative', paddingLeft: '24px', marginBottom: '20px' }}>
                  <div style={{ position: 'absolute', left: '5px', top: '16px', bottom: '-20px', width: '1px', backgroundColor: '#E5E7EB', zIndex: 1 }}></div>
                  <div style={{ position: 'absolute', left: '0', top: '10px', width: '9px', height: '9px', borderRadius: '50%', backgroundColor: mainColor, border: '2px solid #FAFAFA', zIndex: 2 }}></div>

                  <div style={{ backgroundColor: bgColor, border: `1px solid ${borderColor}`, borderRadius: '6px', padding: '14px 16px', cursor: 'pointer', transition: 'all 0.15s ease-in-out', boxShadow: isActive ? `0 0 0 2px ${mainColor}` : '0 1px 2px rgba(0,0,0,0.02)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '600', color: mainColor, letterSpacing: '0.5px' }}>{tagText}</span>
                      <span style={{ fontSize: '0.7rem', color: '#6B7280', fontWeight: '500' }}>{carta.FECHA_STR}</span>
                    </div>
                    <div style={{ fontWeight: '600', color: '#111827', fontSize: '0.85rem', marginBottom: '6px', wordBreak: 'break-word', lineHeight: '1.3' }}>{carta.NRO_DOC}</div>
                    <div style={{ fontSize: '0.75rem', color: '#4B5563', lineHeight: '1.4', wordBreak: 'break-word' }}>{carta.ASUNTO}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* VISOR PDF */}
        <div style={{ flex: 1, minWidth: 0, backgroundColor: '#E5E7EB', display: 'flex', flexDirection: 'column', padding: '24px' }}>
          {docSeleccionado ? (
            <div style={{ flex: 1, minHeight: 0, backgroundColor: 'white', borderRadius: '8px', border: '1px solid #D1D5DB', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              
              {/* Cabecera del Visor */}
              <div style={{ padding: '12px 20px', borderBottom: '1px solid #E5E7EB', backgroundColor: '#F9FAFB', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: '600', color: '#111827', fontSize: '0.9rem' }}>{docSeleccionado.NRO_DOC}</span>
                  {pdfActual && !pdfActual.esPrincipal && (
                    <span style={{ fontSize: '0.75rem', color: '#6B7280', backgroundColor: '#E5E7EB', padding: '2px 8px', borderRadius: '12px' }}>
                      Anexo seleccionado
                    </span>
                  )}
                </div>
                
                {pdfActual && !pdfActual.esPrincipal && pdfActual.urlPrincipal && (
                  <button onClick={() => setPdfActual({ ...pdfActual, url: pdfActual.urlPrincipal, nombre: 'Documento Principal', esPrincipal: true })} style={{ padding: '6px 12px', fontSize: '0.75rem', backgroundColor: '#EFF6FF', color: '#1E3A8A', border: '1px solid #BFDBFE', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', transition: 'all 0.2s' }}>
                    🏠 Volver al Principal
                  </button>
                )}
              </div>

              {/* Contenedor del Iframe */}
              <div style={{ flex: 1, minHeight: 0, width: '100%', backgroundColor: '#525659' }}>
                {pdfActual ? (
                  <iframe src={pdfActual.url} style={{ display: 'block', width: '100%', height: '100%', border: 'none' }} title={pdfActual.nombre} />
                ) : (
                  <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', backgroundColor: 'white' }}>
                    <div style={{ fontSize: '2rem', marginBottom: '12px' }}>⚠️</div>
                    <p style={{ margin: 0, fontSize: '0.9rem' }}>No se encontró el enlace en Drive para este documento.</p>
                  </div>
                )}
              </div>

              {/* Barra Inferior de Anexos */}
              {anexos.length > 0 && (
                <div style={{ padding: '12px 20px', borderTop: '1px solid #E5E7EB', backgroundColor: '#F9FAFB', flexShrink: 0 }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#6B7280', marginBottom: '10px', letterSpacing: '0.5px' }}>
                    📎 ANEXOS DISPONIBLES ({anexos.length})
                  </div>
                  <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '6px' }}>
                    {anexos.map((anx, i) => {
                      let anURL = anx.URL;
                      if (anURL.includes("drive.google.com") && anURL.includes("/view")) anURL = anURL.split("/view")[0] + "/preview";
                      const isSelected = pdfActual && pdfActual.url === anURL;
                      
                      return (
                        <button 
                          key={i} 
                          onClick={() => setPdfActual({ nombre: anx.Nombre, url: anURL, esPrincipal: false, urlPrincipal: pdfActual?.urlPrincipal })} 
                          style={{ flexShrink: 0, whiteSpace: 'nowrap', padding: '8px 16px', fontSize: '0.75rem', backgroundColor: isSelected ? '#1E3A8A' : 'white', color: isSelected ? 'white' : '#475569', border: `1px solid ${isSelected ? '#1E3A8A' : '#CBD5E1'}`, borderRadius: '6px', cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 1px 2px rgba(0,0,0,0.02)' }}
                        >
                          {anx.Nombre}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '8px', border: '1px solid #D1D5DB', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <div style={{ textAlign: 'center', color: '#9CA3AF' }}>
                <div style={{ fontSize: '2rem', marginBottom: '12px' }}>📄</div>
                <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: '500' }}>Selecciona un registro para visualizar el documento</p>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

export default App
