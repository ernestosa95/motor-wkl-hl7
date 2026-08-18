import React, { useState } from 'react';
import { Activity, Settings, Network } from 'lucide-react';
import Monitor from './components/Monitor';
import Canales from './components/Canales';

export default function App() {
  // Estado inicial fijado en la primera sección por defecto
  const [seccionActiva, setSeccionActiva] = useState('monitor');

  return (
    // Diseño estructurado sobre un fondo blanco plano, sin imágenes de fondo que generen ruido visual
    <div className="flex h-screen w-full bg-white text-gray-800 font-sans">
      
      {/* Barra Lateral de Navegación */}
      <nav className="w-64 border-r border-gray-200 bg-gray-50 flex flex-col p-4">
        <div className="mb-8 px-2">
          <h1 className="text-2xl font-bold text-blue-900 tracking-tight">Motor HL7</h1>
          <p className="text-xs text-gray-500 mt-1">Consola de Integración</p>
        </div>
        
        <div className="flex flex-col gap-2">
          <button 
            onClick={() => setSeccionActiva('monitor')}
            className={`flex items-center gap-3 p-3 rounded transition-all duration-200 ${
              seccionActiva === 'monitor' 
                ? 'bg-blue-100 text-blue-800 font-semibold shadow-sm' 
                : 'hover:bg-gray-200 text-gray-600'
            }`}
          >
            <Activity size={20} />
            <span>Monitor</span>
          </button>
          
          <button 
            onClick={() => setSeccionActiva('canales')}
            className={`flex items-center gap-3 p-3 rounded transition-all duration-200 ${
              seccionActiva === 'canales' 
                ? 'bg-blue-100 text-blue-800 font-semibold shadow-sm' 
                : 'hover:bg-gray-200 text-gray-600'
            }`}
          >
            <Network size={20} />
            <span>Canales</span>
          </button>

          <button 
            onClick={() => setSeccionActiva('ajustes')}
            className={`flex items-center gap-3 p-3 rounded transition-all duration-200 ${
              seccionActiva === 'ajustes' 
                ? 'bg-blue-100 text-blue-800 font-semibold shadow-sm' 
                : 'hover:bg-gray-200 text-gray-600'
            }`}
          >
            <Settings size={20} />
            <span>Ajustes Generales</span>
          </button>
        </div>
      </nav>

      {/* Área Principal de Renderizado Dinámico */}
      <main className="flex-1 p-8 overflow-y-auto bg-white">
        
        {seccionActiva === 'monitor' && (
          <div className="h-full flex flex-col animate-fade-in">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-800">Monitor en Tiempo Real de Trazabilidad</h2>
              <p className="text-sm text-gray-500 mt-1">Auditoría del ciclo de vida de los mensajes DICOM/HL7.</p>
            </div>
            <Monitor />
          </div>
        )}

        {seccionActiva === 'canales' && (
          <div className="h-full flex flex-col animate-fade-in">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-800">Gestión de Canales y Scripts</h2>
              <p className="text-sm text-gray-500 mt-1">Configuración de endpoints MLLP y reglas de mapeo en caliente.</p>
            </div>
            {/* El componente Canales maneja internamente sus tarjetas de configuración colapsables */}
            <Canales />
          </div>
        )}

        {seccionActiva === 'ajustes' && (
          <div className="h-full flex flex-col animate-fade-in">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-800">Ajustes Generales</h2>
              <p className="text-sm text-gray-500 mt-1">Configuración global del motor de integración.</p>
            </div>
            <div className="border border-gray-200 rounded p-8 text-center text-gray-500 bg-gray-50">
              Módulo de ajustes en desarrollo.
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
