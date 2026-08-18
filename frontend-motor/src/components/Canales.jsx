import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { ChevronDown, ChevronUp, Database, Network, UserPlus, FileText } from 'lucide-react';

export default function Canales() {
  // Estados independientes para optimizar el área de trabajo sobre el lienzo blanco
  const [wklColapsada, setWklColapsada] = useState(true);
  const [adtColapsada, setAdtColapsada] = useState(false);
  const [ormColapsada, setOrmColapsada] = useState(false);

  const scriptJinjaMock = `MSH|^~\\&|DICOM_WKL|TECNOIMAGEN|HIS|HOSPITAL|{{ fecha }}||ORM^O01|{{ msg_id }}|P|2.5\nPID|1||{{ pid_3 }}||{{ pid_5 }}||{{ pid_7 }}|{{ pid_8 }}\nORC|NW|{{ obr_2 }}\nOBR|1|{{ obr_2 }}|{{ obr_3 }}|{{ obr_4 }}||||||||||||{{ obr_16 }}||||||||{{ obr_24 }}|||{{ obr_27 }}`;

  return (
    <div className="flex flex-col gap-6 w-full">
      
      {/* Tarjeta Colapsable 1: Ingesta DICOM Worklist */}
      <div className="border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden transition-all duration-300">
        <div 
          className="bg-white px-6 py-4 flex justify-between items-center cursor-pointer border-b border-gray-100 hover:bg-gray-50 transition-colors"
          onClick={() => setWklColapsada(!wklColapsada)}
        >
          <div className="flex items-center gap-3">
            <Database size={18} className="text-blue-600" />
            <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Origen: Ingesta DICOM Worklist (C-FIND)</h3>
          </div>
          {wklColapsada ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronUp size={20} className="text-gray-400" />}
        </div>
        
        {!wklColapsada && (
          <div className="p-6 grid grid-cols-3 gap-6 bg-white">
            <div>
              <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">IP del Servidor (SCP)</label>
              <input 
                type="text" 
                defaultValue="192.168.1.100" 
                className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">AETitle Origen</label>
              <input 
                type="text" 
                defaultValue="MOTOR_WKL" 
                className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Puerto DICOM</label>
              <input 
                type="number" 
                defaultValue="104" 
                className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
              />
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Tarjeta Colapsable 2: Emisión MLLP (ADT) */}
        <div className="border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden transition-all duration-300">
          <div 
            className="bg-white px-6 py-4 flex justify-between items-center cursor-pointer border-b border-gray-100 hover:bg-gray-50 transition-colors"
            onClick={() => setAdtColapsada(!adtColapsada)}
          >
            <div className="flex items-center gap-3">
              <UserPlus size={18} className="text-purple-600" />
              <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Destino MLLP: Demográficos (ADT)</h3>
            </div>
            {adtColapsada ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronUp size={20} className="text-gray-400" />}
          </div>
          
          {!adtColapsada && (
            <div className="p-6 flex flex-col gap-4 bg-white">
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Host / IP (Ej. HIS / MPI)</label>
                <input 
                  type="text" 
                  defaultValue="10.0.0.50" 
                  className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Puerto TCP</label>
                <input 
                  type="number" 
                  defaultValue="2575" 
                  className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
                />
              </div>
            </div>
          )}
        </div>

        {/* Tarjeta Colapsable 3: Emisión MLLP (ORM) */}
        <div className="border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden transition-all duration-300">
          <div 
            className="bg-white px-6 py-4 flex justify-between items-center cursor-pointer border-b border-gray-100 hover:bg-gray-50 transition-colors"
            onClick={() => setOrmColapsada(!ormColapsada)}
          >
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-emerald-600" />
              <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Destino MLLP: Órdenes (ORM)</h3>
            </div>
            {ormColapsada ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronUp size={20} className="text-gray-400" />}
          </div>
          
          {!ormColapsada && (
            <div className="p-6 flex flex-col gap-4 bg-white">
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Host / IP (Ej. RIS)</label>
                <input 
                  type="text" 
                  defaultValue="10.0.0.51" 
                  className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Puerto TCP</label>
                <input 
                  type="number" 
                  defaultValue="2576" 
                  className="w-full border border-gray-200 rounded-md p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow shadow-sm" 
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tarjeta del Editor de Mapeo (Jinja2) - Fija para edición en caliente */}
      <div className="border border-gray-200 rounded-lg shadow-sm bg-white overflow-hidden flex-1 flex flex-col min-h-[500px]">
        <div className="bg-white px-6 py-4 border-b border-gray-100 flex justify-between items-center">
          <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">Editor en Caliente: Transformación DICOM a HL7</h3>
          <select className="text-sm border border-gray-200 rounded p-1 text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="orm">Plantilla ORM^O01</option>
            <option value="adt">Plantilla ADT^A01</option>
          </select>
        </div>
        <div className="flex-1 p-2 bg-gray-50 border-t border-gray-100">
          <Editor
            height="100%"
            defaultLanguage="plaintext"
            defaultValue={scriptJinjaMock}
            theme="vs-light"
            options={{ 
              minimap: { enabled: false }, 
              fontSize: 14,
              scrollBeyondLastLine: false,
              padding: { top: 16 }
            }}
          />
        </div>
      </div>

    </div>
  );
}