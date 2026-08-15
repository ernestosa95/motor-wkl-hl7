import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Activity, Settings, Network, CheckCircle, AlertTriangle, XOctagon, ChevronDown, ChevronUp } from 'lucide-react';

export default function App() {
  // Estado inicial: Monitor por defecto y tarjetas agrupadas
  const [vistaActiva, setVistaActiva] = useState('monitor');
  const [tarjetaColapsada, setTarjetaColapsada] = useState(false);
  const [metricas, setMetricas] = useState({
    mensajes_procesados: 0,
    errores_emision: 0,
    errores_permanentes: 0
  });

  // Efecto para consultar el endpoint REST de salud del motor
  useEffect(() => {
    const obtenerDatos = async () => {
      try {
        const respuesta = await fetch('http://localhost:8000/api/v1/health/channels');
        if (respuesta.ok) {
          const datos = await respuesta.json();
          setMetricas(datos.metricas);
        }
      } catch (error) {
        console.error("Falla de red al consultar la API del Motor:", error);
      }
    };

    if (vistaActiva === 'monitor') {
      obtenerDatos();
      const intervalo = setInterval(obtenerDatos, 5000); // Polling cada 5 segundos
      return () => clearInterval(intervalo);
    }
  }, [vistaActiva]);

  // Plantilla Jinja2 por defecto con mapeos estándar DICOM a HL7 v2.5[cite: 2]
  const plantillaBase = `# Motor de Transformación (Mapper) Jinja2
# Segmento PID (Identificación del Paciente)
# (0010,0020) Patient ID -> PID-3[cite: 2]
# (0010,0010) Patient's Name -> PID-5[cite: 2]
# (0010,0030) Patient's Birth Date -> PID-7[cite: 2]
# (0010,0040) Patient's Sex -> PID-8[cite: 2]

def procesar_segmento_pid(dicom_data):
    paciente_id = dicom_data.get("00100020", "DESCONOCIDO")
    nombre = dicom_data.get("00100010", "SIN_NOMBRE")
    fecha_nac = dicom_data.get("00100030", "")
    sexo = dicom_data.get("00100040", "U")
    
    # Validación estricta de seguridad de datos
    if not nombre.strip():
        return f"PID|1||{paciente_id}||PACIENTE^NN||{fecha_nac}|{sexo}"
        
    return f"PID|1||{paciente_id}||{nombre}||{fecha_nac}|{sexo}"
`;

  const renderizarVista = () => {
    switch (vistaActiva) {
      case 'monitor':
        return (
          <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-3xl font-light text-slate-800 mb-2">Monitor en Tiempo Real</h2>
            <p className="text-sm text-slate-500 mb-8 border-b border-slate-200 pb-4">
              Dimensionado para procesar un flujo promedio de 250 órdenes diarias[cite: 2].
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md hover:border-cyan-200 transition-all flex items-center gap-5">
                <div className="p-4 bg-cyan-50 text-cyan-500 rounded-lg">
                  <CheckCircle size={32} strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Completados (ACK)</p>
                  <p className="text-4xl font-light text-slate-800">{metricas.mensajes_procesados}</p>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-all flex items-center gap-5">
                <div className="p-4 bg-amber-50 text-amber-500 rounded-lg">
                  <AlertTriangle size={32} strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Rechazos (NACK)</p>
                  <p className="text-4xl font-light text-slate-800">{metricas.errores_emision}</p>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-all flex items-center gap-5">
                <div className="p-4 bg-rose-50 text-rose-500 rounded-lg">
                  <XOctagon size={32} strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Fallas de Red</p>
                  <p className="text-4xl font-light text-slate-800">{metricas.errores_permanentes}</p>
                </div>
              </div>
            </div>
          </div>
        );
      case 'canales':
        return (
          <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-3xl font-light text-slate-800 mb-6">Gestión de Canales y Mapeos</h2>
            
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden mb-6">
              <div 
                className="flex justify-between items-center p-5 bg-slate-50 cursor-pointer hover:bg-slate-100 transition-colors border-b border-slate-200"
                onClick={() => setTarjetaColapsada(!tarjetaColapsada)}
              >
                <div>
                  <h3 className="font-semibold text-slate-800 text-lg">Mapeo DICOM a HL7 (ORM^O01)</h3>
                  <p className="text-sm text-slate-500">Motor Jinja2 para cruces estándar de tags DICOM a HL7[cite: 2].</p>
                </div>
                {tarjetaColapsada ? <ChevronDown size={24} className="text-slate-400" /> : <ChevronUp size={24} className="text-cyan-500" />}
              </div>
              
              {!tarjetaColapsada && (
                <div className="p-6 bg-white">
                  <p className="text-sm text-slate-600 mb-4">
                    Edición en caliente para modificaciones menores a los scripts (condicionales lógicos) que se compilarán en tiempo de ejecución[cite: 2].
                  </p>
                  
                  <div className="border border-slate-300 rounded-lg overflow-hidden shadow-inner">
                    <Editor
                      height="350px"
                      defaultLanguage="python"
                      theme="light"
                      options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }}
                      defaultValue={plantillaBase}
                    />
                  </div>
                  
                  <div className="mt-5 flex justify-end gap-3">
                    <button className="px-5 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors border border-slate-200">
                      Restaurar Valores
                    </button>
                    <button className="px-5 py-2.5 rounded-lg text-sm font-medium bg-[#0f172a] text-white hover:bg-slate-800 transition-colors shadow-sm">
                      Guardar y Compilar Mapeo
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      case 'ajustes':
        return (
          <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-3xl font-light text-slate-800 mb-6">Ajustes del Sistema</h2>
            <p className="text-slate-500">Configuración global del motor de integración.</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen bg-white font-sans selection:bg-cyan-100 selection:text-cyan-900">
      
      <aside className="w-72 bg-[#0f172a] flex flex-col shadow-xl z-10">
        <div className="p-8 border-b border-slate-800">
          <h1 className="text-3xl font-semibold tracking-tight text-white flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]"></span>
            MotorDICOM
          </h1>
          <p className="text-xs text-cyan-400/80 mt-2 uppercase tracking-[0.2em] font-semibold">Tecnoimagen SA</p>
        </div>
        
        <nav className="flex-1 px-4 py-8 space-y-2">
          <button 
            onClick={() => setVistaActiva('monitor')}
            className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm transition-all duration-300 font-medium ${vistaActiva === 'monitor' ? 'bg-cyan-500/10 text-cyan-400 border-l-4 border-cyan-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 border-l-4 border-transparent'}`}
          >
            <Activity size={20} /> Monitor Global
          </button>
          
          <button 
            onClick={() => setVistaActiva('canales')}
            className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm transition-all duration-300 font-medium ${vistaActiva === 'canales' ? 'bg-cyan-500/10 text-cyan-400 border-l-4 border-cyan-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 border-l-4 border-transparent'}`}
          >
            <Network size={20} /> Canales y Mapeos
          </button>
          
          <button 
            onClick={() => setVistaActiva('ajustes')}
            className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm transition-all duration-300 font-medium ${vistaActiva === 'ajustes' ? 'bg-cyan-500/10 text-cyan-400 border-l-4 border-cyan-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 border-l-4 border-transparent'}`}
          >
            <Settings size={20} /> Ajustes del Sistema
          </button>
        </nav>
      </aside>

      <main className="flex-1 overflow-auto bg-white">
        {renderizarVista()}
      </main>
    </div>
  );
}