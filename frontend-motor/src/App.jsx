import React, { useState } from 'react';
import { Activity, Network, GitCompareArrows, LogOut } from 'lucide-react';
import Monitor from './components/Monitor';
import Canales from './components/Canales';
import Mapeos from './components/Mapeos';
import Login from './components/Login';

const SECCIONES = [
  { id: 'monitor', label: 'Monitor', icon: Activity,
    titulo: 'Trazabilidad', subtitulo: 'Ciclo de vida de los mensajes DICOM → HL7.' },
  { id: 'canales', label: 'Canales', icon: Network,
    titulo: 'Canales y conexiones', subtitulo: 'Endpoints DICOM y MLLP, con prueba de conectividad.' },
  { id: 'mapeo', label: 'Mapeo', icon: GitCompareArrows,
    titulo: 'Mapeo DICOM → HL7', subtitulo: 'Definí a qué campos HL7 se envía cada tag DICOM.' },
];

export default function App() {
  const [seccion, setSeccion] = useState('monitor');
  const [logueado, setLogueado] = useState(!!localStorage.getItem('token'));

  const cerrarSesion = () => {
    localStorage.removeItem('token');
    setLogueado(false);
  };

  if (!logueado) return <Login onLogin={() => setLogueado(true)} />;

  const actual = SECCIONES.find((s) => s.id === seccion);

  return (
    <div className="flex h-screen bg-zinc-50 text-zinc-900 font-sans">

      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-white border-r border-zinc-200 flex flex-col">
        <div className="px-6 py-6 border-b border-zinc-100">
          <div className="flex items-center gap-2.5">
            <span className="h-2 w-2 rounded-full bg-teal-500" />
            <h1 className="text-[15px] font-semibold tracking-tight text-zinc-900">Motor HL7</h1>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400 tracking-wide">
            Tecnoimagen · Integración clínica
          </p>
        </div>

        <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
          {SECCIONES.map(({ id, label, icon: Icon }) => {
            const activo = seccion === id;
            return (
              <button
                key={id}
                onClick={() => setSeccion(id)}
                className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  activo
                    ? 'bg-zinc-50 text-teal-700 font-medium'
                    : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800'
                }`}
              >
                <span
                  className={`absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-teal-500 transition-opacity ${
                    activo ? 'opacity-100' : 'opacity-0'
                  }`}
                />
                <Icon size={17} strokeWidth={2} />
                <span>{label}</span>
              </button>
            );
          })}
        </nav>

        <div className="px-3 py-4 border-t border-zinc-100">
          <div className="px-3 pb-3 flex items-center gap-2 text-[11px] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
            <span>Motor conectado</span>
          </div>
          <button
            onClick={cerrarSesion}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800 transition-colors"
          >
            <LogOut size={16} strokeWidth={2} />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>

      {/* Área principal */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 shrink-0 border-b border-zinc-200 bg-white/80 backdrop-blur px-8 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-zinc-900 leading-tight">{actual.titulo}</h2>
            <p className="text-xs text-zinc-400">{actual.subtitulo}</p>
          </div>
          {seccion === 'monitor' && (
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-500" />
              </span>
              En vivo
            </div>
          )}
        </header>

        <main className="flex-1 overflow-y-auto p-8">
          <div className="animate-fade-in max-w-6xl mx-auto">
            {seccion === 'monitor' && <Monitor />}
            {seccion === 'canales' && <Canales />}
            {seccion === 'mapeo' && <Mapeos />}
          </div>
        </main>
      </div>
    </div>
  );
}
