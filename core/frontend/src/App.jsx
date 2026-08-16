import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Activity, Settings, Network, CheckCircle, AlertTriangle, XOctagon, ChevronDown, ChevronUp, Database, Search, Plus, Trash2, Lock, User, LogOut } from 'lucide-react';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('motordicom_token') || null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorLogin, setErrorLogin] = useState('');

  const [vistaActiva, setVistaActiva] = useState('monitor');
  const [tarjetaWlColapsada, setTarjetaWlColapsada] = useState(true); 
  const [tarjetaMapeoColapsada, setTarjetaMapeoColapsada] = useState(true);
  const [tarjetaScriptColapsada, setTarjetaScriptColapsada] = useState(true);

  const [filtroAccession, setFiltroAccession] = useState('');
  const [filtroPaciente, setFiltroPaciente] = useState('');

  const [metricas, setMetricas] = useState({ mensajes_procesados: 0, errores_emision: 0, errores_permanentes: 0 });
  const [ordenesWorklist, setOrdenesWorklist] = useState([]);
  const [configNodo, setConfigNodo] = useState({ ip: '192.168.1.100', aetitle: 'HIS_WORKLIST', puerto: 104 });
  const [mapeosVisuales, setMapeosVisuales] = useState([]);

  // --- LÓGICA DE AUTENTICACIÓN ---
  const manejarLogin = async (e) => {
    e.preventDefault();
    setErrorLogin('');
    try {
      const form = new URLSearchParams();
      form.append('username', username);
      form.append('password', password);

      const res = await fetch('http://localhost:8000/api/v1/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form
      });
      
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        localStorage.setItem('motordicom_token', data.access_token);
      } else {
        setErrorLogin('Credenciales inválidas');
      }
    } catch (error) {
      setErrorLogin('Error de conexión con el motor Core');
    }
  };

  const cerrarSesion = () => {
    setToken(null);
    localStorage.removeItem('motordicom_token');
  };

  const headersAuth = { 'Authorization': `Bearer ${token}` };

  // --- LÓGICA DE DATOS ---
  useEffect(() => {
    if (!token) return;

    const obtenerDatos = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/health/channels', { headers: headersAuth });
        if (res.ok) setMetricas((await res.json()).metricas);
        else if (res.status === 401) cerrarSesion();
      } catch (error) {}
    };

    const cargarWorklist = async () => {
      try {
        const queryParams = new URLSearchParams();
        if (filtroAccession) queryParams.append("accession", filtroAccession);
        if (filtroPaciente) queryParams.append("paciente", filtroPaciente);
        
        const res = await fetch(`http://localhost:8000/api/v1/worklist/activas?${queryParams.toString()}`, { headers: headersAuth });
        if (res.ok) setOrdenesWorklist(await res.json());
      } catch (error) {}
    };

    const cargarConfig = async () => {
      try {
        const [resConf, resMap] = await Promise.all([
          fetch('http://localhost:8000/api/v1/config/nodo', { headers: headersAuth }),
          fetch('http://localhost:8000/api/v1/mapeos', { headers: headersAuth })
        ]);
        if (resConf.ok) setConfigNodo(await resConf.json());
        if (resMap.ok) setMapeosVisuales(await resMap.json());
      } catch (error) {}
    };

    if (vistaActiva === 'monitor') {
      obtenerDatos();
      const int = setInterval(obtenerDatos, 5000);
      return () => clearInterval(int);
    } else if (vistaActiva === 'canales') {
      cargarWorklist();
      cargarConfig();
      const int = setInterval(cargarWorklist, 5000);
      return () => clearInterval(int);
    }
  }, [vistaActiva, filtroAccession, filtroPaciente, token]);

  const guardarConfiguracion = async () => {
    await fetch('http://localhost:8000/api/v1/config/nodo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headersAuth },
      body: JSON.stringify(configNodo)
    });
    alert("Configuración asegurada.");
  };

  const guardarMapeosVisuales = async () => {
    await fetch('http://localhost:8000/api/v1/mapeos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headersAuth },
      body: JSON.stringify(mapeosVisuales)
    });
    alert("Reglas de mapeo guardadas.");
  };

  const agregarReglaMapeo = () => setMapeosVisuales([...mapeosVisuales, { tag_dicom: '', nombre_dicom: '', campo_hl7: '' }]);
  const actualizarRegla = (index, c, v) => { const n = [...mapeosVisuales]; n[index][c] = v; setMapeosVisuales(n); };
  const eliminarRegla = (index) => setMapeosVisuales(mapeosVisuales.filter((_, i) => i !== index));

  // --- VISTA DE LOGIN (Lienzo Blanco, Plano y Minimalista) ---
  if (!token) {
    return (
      <div className="flex h-screen bg-white items-center justify-center font-sans selection:bg-cyan-100 selection:text-cyan-900">
        <div className="w-full max-w-md p-8 bg-white border border-slate-200 rounded-none shadow-sm">
          <div className="text-center mb-10">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900 mb-2">MotorDICOM</h1>
            <p className="text-xs text-cyan-600 uppercase tracking-widest font-semibold">Tecnoimagen SA</p>
          </div>
          
          <form onSubmit={manejarLogin} className="space-y-6">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Usuario</label>
              <div className="relative">
                <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="text" value={username} onChange={e => setUsername(e.target.value)} className="w-full border border-slate-300 rounded pl-10 pr-4 py-2 text-slate-700 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500" required />
              </div>
            </div>
            
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Contraseña</label>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full border border-slate-300 rounded pl-10 pr-4 py-2 text-slate-700 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500" required />
              </div>
            </div>

            {errorLogin && <p className="text-rose-500 text-sm font-medium text-center">{errorLogin}</p>}

            <button type="submit" className="w-full bg-[#0f172a] hover:bg-slate-800 text-white font-medium py-3 rounded text-sm transition-colors">
              Iniciar Sesión
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- VISTA PRINCIPAL PROTEGIDA ---
  const renderizarVista = () => {
    switch (vistaActiva) {
      case 'monitor':
        return (
          <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-3xl font-light text-slate-800 mb-2">Monitor en Tiempo Real</h2>
            <p className="text-sm text-slate-500 mb-8 border-b border-slate-200 pb-4">Dimensionado para procesar un flujo promedio de 250 órdenes diarias[cite: 2].</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex items-center gap-5"><div className="p-4 bg-cyan-50 text-cyan-500 rounded-lg"><CheckCircle size={32} /></div><div><p className="text-xs text-slate-400 font-bold uppercase mb-1">Completados (ACK)</p><p className="text-4xl font-light">{metricas.mensajes_procesados}</p></div></div>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex items-center gap-5"><div className="p-4 bg-amber-50 text-amber-500 rounded-lg"><AlertTriangle size={32} /></div><div><p className="text-xs text-slate-400 font-bold uppercase mb-1">Rechazos (NACK)</p><p className="text-4xl font-light">{metricas.errores_emision}</p></div></div>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex items-center gap-5"><div className="p-4 bg-rose-50 text-rose-500 rounded-lg"><XOctagon size={32} /></div><div><p className="text-xs text-slate-400 font-bold uppercase mb-1">Fallas de Red</p><p className="text-4xl font-light">{metricas.errores_permanentes}</p></div></div>
            </div>
          </div>
        );

      case 'canales':
        return (
          <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-3xl font-light text-slate-800 mb-6">Gestión de Canales y Worklist</h2>
            
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden mb-6">
              <div className="flex justify-between items-center p-5 bg-slate-50 cursor-pointer border-b border-slate-200" onClick={() => setTarjetaWlColapsada(!tarjetaWlColapsada)}>
                <div className="flex items-center gap-3"><Database size={20} className="text-slate-500" /><div><h3 className="font-semibold text-slate-800">Configuración del Nodo SCU</h3></div></div>
                {tarjetaWlColapsada ? <ChevronDown size={24} className="text-slate-400" /> : <ChevronUp size={24} className="text-cyan-500" />}
              </div>
              {!tarjetaWlColapsada && (
                <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div><label className="block text-xs font-bold text-slate-500 uppercase mb-2">Dirección IP</label><input type="text" value={configNodo.ip} onChange={e => setConfigNodo({...configNodo, ip: e.target.value})} className="w-full border border-slate-300 rounded px-4 py-2" /></div>
                  <div><label className="block text-xs font-bold text-slate-500 uppercase mb-2">AE Title</label><input type="text" value={configNodo.aetitle} onChange={e => setConfigNodo({...configNodo, aetitle: e.target.value})} className="w-full border border-slate-300 rounded px-4 py-2" /></div>
                  <div><label className="block text-xs font-bold text-slate-500 uppercase mb-2">Puerto</label><input type="number" value={configNodo.puerto} onChange={e => setConfigNodo({...configNodo, puerto: parseInt(e.target.value)})} className="w-full border border-slate-300 rounded px-4 py-2" /></div>
                  <div className="md:col-span-3 flex justify-end"><button onClick={guardarConfiguracion} className="px-6 py-2.5 rounded text-sm font-medium bg-[#0f172a] text-white">Guardar</button></div>
                </div>
              )}
            </div>

            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden mb-6">
              <div className="flex justify-between items-center p-5 bg-slate-50 cursor-pointer border-b border-slate-200" onClick={() => setTarjetaMapeoColapsada(!tarjetaMapeoColapsada)}>
                <div className="flex items-center gap-3"><Network size={20} className="text-slate-500" /><div><h3 className="font-semibold text-slate-800">Constructor Visual de Mapeos</h3></div></div>
                {tarjetaMapeoColapsada ? <ChevronDown size={24} className="text-slate-400" /> : <ChevronUp size={24} className="text-cyan-500" />}
              </div>
              {!tarjetaMapeoColapsada && (
                <div className="p-6">
                  <table className="w-full text-left text-sm mb-4">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-xs font-bold"><tr><th className="px-4 py-3">Tag DICOM</th><th className="px-4 py-3">Nombre del Atributo</th><th className="px-4 py-3">Campo HL7 Destino</th><th className="px-4 py-3 text-center">Acción</th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {mapeosVisuales.map((regla, idx) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="px-4 py-2"><input type="text" value={regla.tag_dicom} onChange={e => actualizarRegla(idx, 'tag_dicom', e.target.value)} className="w-full border border-slate-300 rounded px-2 py-1" /></td>
                          <td className="px-4 py-2"><input type="text" value={regla.nombre_dicom} onChange={e => actualizarRegla(idx, 'nombre_dicom', e.target.value)} className="w-full border border-slate-300 rounded px-2 py-1" /></td>
                          <td className="px-4 py-2"><input type="text" value={regla.campo_hl7} onChange={e => actualizarRegla(idx, 'campo_hl7', e.target.value)} className="w-full border border-slate-300 rounded px-2 py-1" /></td>
                          <td className="px-4 py-2 text-center"><button onClick={() => eliminarRegla(idx)} className="text-rose-500 hover:text-rose-700 p-1"><Trash2 size={18} /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="flex justify-between">
                    <button onClick={agregarReglaMapeo} className="flex items-center gap-2 px-4 py-2 rounded text-sm text-cyan-600 bg-cyan-50 border border-cyan-200"><Plus size={16} /> Agregar Regla</button>
                    <button onClick={guardarMapeosVisuales} className="px-6 py-2.5 rounded text-sm font-medium bg-[#0f172a] text-white">Guardar Mapeos</button>
                  </div>
                </div>
              )}
            </div>
            
            {/* Tabla Worklist (Resto del código idéntico al bloque anterior) */}
             <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-200 flex justify-between items-center">
                <h3 className="font-semibold text-slate-800">Órdenes Activas</h3>
                <div className="flex gap-3">
                  <div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="text" placeholder="Accession Number..." value={filtroAccession} onChange={(e) => setFiltroAccession(e.target.value)} className="pl-9 pr-4 py-2 border rounded text-sm" /></div>
                  <div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="text" placeholder="Paciente..." value={filtroPaciente} onChange={(e) => setFiltroPaciente(e.target.value)} className="pl-9 pr-4 py-2 border rounded text-sm" /></div>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200"><tr><th className="px-6 py-4">Accession Number</th><th className="px-6 py-4">ID Paciente</th><th className="px-6 py-4">Nombre Completo</th><th className="px-6 py-4">Estudio Agendado</th><th className="px-6 py-4">Estado</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {ordenesWorklist.map((orden, index) => (
                      <tr key={index} className="hover:bg-slate-50">
                        <td className="px-6 py-4 font-medium text-slate-900">{orden.accession_number}</td><td className="px-6 py-4">{orden.patient_id}</td><td className="px-6 py-4">{orden.paciente}</td><td className="px-6 py-4">{orden.estudio}</td>
                        <td className="px-6 py-4"><span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">{orden.estado}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );
      case 'ajustes': return <div className="p-8 max-w-7xl mx-auto"><h2 className="text-3xl font-light text-slate-800">Ajustes del Sistema</h2></div>;
      default: return null;
    }
  };

  return (
    <div className="flex h-screen bg-white font-sans text-slate-800 selection:bg-cyan-100 selection:text-cyan-900">
      <aside className="w-72 bg-[#0f172a] flex flex-col shadow-xl z-10">
        <div className="p-8 border-b border-slate-800">
          <h1 className="text-3xl font-semibold text-white flex items-center gap-3"><span className="w-3 h-3 rounded-full bg-cyan-400"></span>MotorDICOM</h1>
          <p className="text-xs text-cyan-400 mt-2 uppercase tracking-widest">Tecnoimagen SA</p>
        </div>
        <nav className="flex-1 px-4 py-8 space-y-2">
          <button onClick={() => setVistaActiva('monitor')} className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm font-medium ${vistaActiva === 'monitor' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400'}`}><Activity size={20} /> Monitor Global</button>
          <button onClick={() => setVistaActiva('canales')} className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm font-medium ${vistaActiva === 'canales' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400'}`}><Network size={20} /> Canales y Mapeos</button>
          <button onClick={() => setVistaActiva('ajustes')} className={`w-full flex items-center gap-4 px-5 py-3.5 rounded-lg text-sm font-medium ${vistaActiva === 'ajustes' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400'}`}><Settings size={20} /> Ajustes</button>
        </nav>
        <div className="p-4 border-t border-slate-800">
          <button onClick={cerrarSesion} className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
            <LogOut size={16} /> Cerrar Sesión
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-white">{renderizarVista()}</main>
    </div>
  );
}