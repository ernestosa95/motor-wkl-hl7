import React, { useState, useEffect, useMemo } from 'react';
import { FileCode2, RotateCcw, History, Search } from 'lucide-react';
import { apiFetch } from './Login';
import HL7Viewer from './HL7Viewer';
import AuditoriaModal from './AuditoriaModal';

const ESTADOS = ['', 'INGRESADO', 'TRANSFORMADO', 'COMPLETADO', 'ERROR_EMISION', 'ERROR_PERMANENTE'];

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

// Input de filtro para el encabezado de columna
function FiltroCol({ value, onChange, placeholder }) {
  return (
    <div className="relative mt-1.5">
      <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-300" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-zinc-200 py-1 pl-6 pr-2 text-xs font-normal normal-case text-zinc-700 focus:outline-none focus:ring-1 focus:ring-teal-400"
      />
    </div>
  );
}

export default function Monitor() {
  const [ordenes, setOrdenes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [verHl7, setVerHl7] = useState(null);
  const [verAuditoria, setVerAuditoria] = useState(null);
  const [reprocesando, setReprocesando] = useState({});

  // Filtros por columna
  const [fAccession, setFAccession] = useState('');
  const [fPaciente, setFPaciente] = useState('');
  const [fModalidad, setFModalidad] = useState('');
  const [fEstado, setFEstado] = useState('');

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

  useEffect(() => {
    fetchTrazabilidad();
    const intervalo = setInterval(fetchTrazabilidad, 3000);
    return () => clearInterval(intervalo);
  }, []);

  const reprocesar = async (orden) => {
    setReprocesando((s) => ({ ...s, [orden.id]: true }));
    try {
      await apiFetch(`/api/v1/trazabilidad/${orden.id}/reprocesar`, { method: 'POST' });
      await fetchTrazabilidad();
    } catch (e) {
      console.error('Error al reprocesar', e);
    } finally {
      setReprocesando((s) => ({ ...s, [orden.id]: false }));
    }
  };

  // Aplicación de filtros (case-insensitive, sobre los datos ya cargados)
  const filtradas = useMemo(() => {
    const inc = (v, f) => (v || '').toString().toLowerCase().includes(f.toLowerCase());
    return ordenes.filter((o) =>
      inc(o.accession, fAccession) &&
      inc(o.paciente, fPaciente) &&
      inc(o.modalidad, fModalidad) &&
      (fEstado === '' || o.estado === fEstado)
    );
  }, [ordenes, fAccession, fPaciente, fModalidad, fEstado]);

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
            <tr className="border-b border-zinc-100 text-left text-[11px] uppercase tracking-wider text-zinc-400 align-top">
              <th className="px-5 py-3 font-medium">
                Accession
                <FiltroCol value={fAccession} onChange={setFAccession} placeholder="Buscar…" />
              </th>
              <th className="px-5 py-3 font-medium">
                Paciente
                <FiltroCol value={fPaciente} onChange={setFPaciente} placeholder="Buscar…" />
              </th>
              <th className="px-5 py-3 font-medium">
                Modalidad
                <FiltroCol value={fModalidad} onChange={setFModalidad} placeholder="Buscar…" />
              </th>
              <th className="px-5 py-3 font-medium">
                Estado
                <select
                  value={fEstado}
                  onChange={(e) => setFEstado(e.target.value)}
                  className="mt-1.5 w-full rounded-md border border-zinc-200 py-1 px-2 text-xs font-normal normal-case text-zinc-700 focus:outline-none focus:ring-1 focus:ring-teal-400"
                >
                  {ESTADOS.map((e) => <option key={e} value={e}>{e === '' ? 'Todos' : e}</option>)}
                </select>
              </th>
              <th className="px-5 py-3 font-medium">Fecha</th>
              <th className="px-5 py-3 font-medium text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-50">
            {cargando ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-zinc-400"><span className="animate-pulse">Sincronizando…</span></td></tr>
            ) : filtradas.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-zinc-400">
                {ordenes.length === 0 ? 'Sin órdenes todavía. El SCU consultará la worklist en el próximo ciclo.' : 'Ninguna orden coincide con los filtros.'}
              </td></tr>
            ) : (
              filtradas.map((o) => {
                const esError = o.estado.startsWith('ERROR');
                return (
                  <tr key={o.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="px-5 py-3 font-mono text-[13px] text-zinc-900">{o.accession}</td>
                    <td className="px-5 py-3 text-zinc-700">{o.paciente}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-xs text-zinc-600">{o.modalidad}</span>
                    </td>
                    <td className="px-5 py-3"><Pill estado={o.estado} /></td>
                    <td className="px-5 py-3 font-mono text-xs text-zinc-400">{o.fecha}</td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-2">
                        {esError && (
                          <button
                            onClick={() => reprocesar(o)}
                            disabled={!!reprocesando[o.id]}
                            title="Reintentar el envío de esta orden"
                            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-colors"
                          >
                            <RotateCcw size={14} className={reprocesando[o.id] ? 'animate-spin' : ''} />
                            {reprocesando[o.id] ? 'Reintentando…' : 'Reprocesar'}
                          </button>
                        )}
                        <button
                          onClick={() => setVerAuditoria(o)}
                          title="Ver auditoría de la orden"
                          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 transition-colors"
                        >
                          <History size={14} /> Auditoría
                        </button>
                        <button
                          onClick={() => setVerHl7(o)}
                          disabled={!o.tiene_hl7}
                          title={o.tiene_hl7 ? 'Ver mensajes HL7' : 'Todavía sin HL7'}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                        >
                          <FileCode2 size={14} /> Ver
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {verHl7 && <HL7Viewer registro={verHl7} onClose={() => setVerHl7(null)} />}
      {verAuditoria && <AuditoriaModal orden={verAuditoria} onClose={() => setVerAuditoria(null)} />}
    </div>
  );
}
