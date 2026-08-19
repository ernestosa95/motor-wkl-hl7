import React, { useState, useEffect } from 'react';
import { FileCode2 } from 'lucide-react';
import { apiFetch } from './Login';
import HL7Viewer from './HL7Viewer';

const ESTADO_STYLE = {
  INGRESADO:        'bg-zinc-100 text-zinc-600 ring-zinc-200',
  TRANSFORMADO:     'bg-blue-50 text-blue-700 ring-blue-200',
  COMPLETADO:       'bg-teal-50 text-teal-700 ring-teal-200',
  ERROR_EMISION:    'bg-rose-50 text-rose-700 ring-rose-200',
  ERROR_PERMANENTE: 'bg-rose-50 text-rose-700 ring-rose-200',
};

function Pill({ estado }) {
  const style = ESTADO_STYLE[estado] || 'bg-zinc-100 text-zinc-600 ring-zinc-200';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {estado}
    </span>
  );
}

function StatCard({ label, valor, tono }) {
  const color = { zinc: 'text-zinc-900', blue: 'text-blue-600', teal: 'text-teal-600', rose: 'text-rose-600' }[tono];
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-5 py-4">
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">{label}</p>
      <p className={`mt-1 font-mono text-3xl font-medium tabular-nums ${color}`}>{valor}</p>
    </div>
  );
}

export default function Monitor() {
  const [ordenes, setOrdenes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [verHl7, setVerHl7] = useState(null);

  useEffect(() => {
    const fetchTrazabilidad = async () => {
      try {
        const respuesta = await apiFetch('/api/v1/trazabilidad');
        if (respuesta.ok) setOrdenes(await respuesta.json());
      } catch (error) {
        console.error('[!] Error de red al obtener la trazabilidad:', error);
      } finally {
        setCargando(false);
      }
    };
    fetchTrazabilidad();
    const intervalo = setInterval(fetchTrazabilidad, 3000);
    return () => clearInterval(intervalo);
  }, []);

  const stats = {
    ingresados: ordenes.filter((o) => o.estado === 'INGRESADO').length,
    transformados: ordenes.filter((o) => o.estado === 'TRANSFORMADO').length,
    completados: ordenes.filter((o) => o.estado === 'COMPLETADO').length,
    errores: ordenes.filter((o) => o.estado.startsWith('ERROR')).length,
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Ingresados" valor={stats.ingresados} tono="zinc" />
        <StatCard label="Transformados" valor={stats.transformados} tono="blue" />
        <StatCard label="Completados" valor={stats.completados} tono="teal" />
        <StatCard label="Errores" valor={stats.errores} tono="rose" />
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 text-left text-[11px] uppercase tracking-wider text-zinc-400">
              <th className="px-5 py-3 font-medium">Accession</th>
              <th className="px-5 py-3 font-medium">Paciente</th>
              <th className="px-5 py-3 font-medium">Modalidad</th>
              <th className="px-5 py-3 font-medium">Estado</th>
              <th className="px-5 py-3 font-medium">Fecha</th>
              <th className="px-5 py-3 font-medium text-right">HL7</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-50">
            {cargando ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-zinc-400"><span className="animate-pulse">Sincronizando…</span></td></tr>
            ) : ordenes.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-zinc-400">Sin órdenes todavía. El SCU consultará la worklist en el próximo ciclo.</td></tr>
            ) : (
              ordenes.map((o) => (
                <tr key={o.id} className="hover:bg-zinc-50/60 transition-colors">
                  <td className="px-5 py-3 font-mono text-[13px] text-zinc-900">{o.accession}</td>
                  <td className="px-5 py-3 text-zinc-700">{o.paciente}</td>
                  <td className="px-5 py-3">
                    <span className="inline-flex rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-xs text-zinc-600">{o.modalidad}</span>
                  </td>
                  <td className="px-5 py-3"><Pill estado={o.estado} /></td>
                  <td className="px-5 py-3 font-mono text-xs text-zinc-400">{o.fecha}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => setVerHl7(o)}
                      disabled={!o.tiene_hl7}
                      title={o.tiene_hl7 ? 'Ver mensajes HL7' : 'Todavía sin HL7'}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      <FileCode2 size={14} /> Ver
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {verHl7 && <HL7Viewer registro={verHl7} onClose={() => setVerHl7(null)} />}
    </div>
  );
}
