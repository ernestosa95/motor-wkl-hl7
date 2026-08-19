import React, { useState, useEffect } from 'react';
import { Database, UserPlus, FileText, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { apiFetch } from './Login';

const META = {
  worklist_scu: { icon: Database, color: 'text-blue-600', dicom: true },
  destino_adt:  { icon: UserPlus, color: 'text-violet-600', dicom: false },
  destino_orm:  { icon: FileText, color: 'text-teal-600', dicom: false },
};

function CanalCard({ canal, onChange, onGuardar, onProbar, guardando, prueba, probando }) {
  const meta = META[canal.clave] || {};
  const Icon = meta.icon || Database;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-100">
        <Icon size={17} className={meta.color} />
        <h3 className="text-sm font-semibold text-zinc-800">{canal.nombre}</h3>
      </div>

      <div className="p-5 grid gap-4" style={{ gridTemplateColumns: meta.dicom ? '1fr 1fr' : '1fr' }}>
        <Field label="Host / IP" value={canal.host}
               onChange={(v) => onChange('host', v)} />
        <Field label="Puerto" type="number" value={canal.puerto}
               onChange={(v) => onChange('puerto', parseInt(v || '0', 10))} />
        {meta.dicom && (
          <>
            <Field label="AE Title destino" value={canal.aet || ''}
                   onChange={(v) => onChange('aet', v)} />
            <Field label="AE Title propio" value={canal.aet_local || ''}
                   onChange={(v) => onChange('aet_local', v)} />
          </>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-zinc-100 bg-zinc-50/50">
        <div className="min-h-[20px] text-xs">
          {prueba && (
            <span className={`inline-flex items-center gap-1.5 ${prueba.ok ? 'text-teal-700' : 'text-rose-700'}`}>
              {prueba.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              {prueba.mensaje}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onProbar}
            disabled={probando}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-60 transition-colors"
          >
            {probando ? <Loader2 size={14} className="animate-spin" /> : null}
            Probar conexión
          </button>
          <button
            onClick={onGuardar}
            disabled={guardando}
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-60 transition-colors"
          >
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text' }) {
  return (
    <div>
      <label className="block text-[11px] font-medium uppercase tracking-wider text-zinc-400 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm font-mono text-zinc-800 focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-shadow"
      />
    </div>
  );
}

export default function Canales() {
  const [canales, setCanales] = useState([]);
  const [guardando, setGuardando] = useState({});
  const [probando, setProbando] = useState({});
  const [pruebas, setPruebas] = useState({});

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch('/api/v1/canales');
        if (res.ok) setCanales(await res.json());
      } catch (e) {
        console.error('Error al cargar canales', e);
      }
    })();
  }, []);

  const editar = (clave, campo, valor) => {
    setCanales((prev) => prev.map((c) => (c.clave === clave ? { ...c, [campo]: valor } : c)));
  };

  const guardar = async (canal) => {
    setGuardando((s) => ({ ...s, [canal.clave]: true }));
    try {
      await apiFetch(`/api/v1/canales/${canal.clave}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: canal.host, puerto: canal.puerto,
          aet: canal.aet, aet_local: canal.aet_local,
        }),
      });
      setPruebas((p) => ({ ...p, [canal.clave]: { ok: true, mensaje: 'Configuración guardada.' } }));
    } catch {
      setPruebas((p) => ({ ...p, [canal.clave]: { ok: false, mensaje: 'No se pudo guardar.' } }));
    } finally {
      setGuardando((s) => ({ ...s, [canal.clave]: false }));
    }
  };

  const probar = async (canal) => {
    setProbando((s) => ({ ...s, [canal.clave]: true }));
    setPruebas((p) => ({ ...p, [canal.clave]: null }));
    try {
      const res = await apiFetch(`/api/v1/canales/${canal.clave}/test`, { method: 'POST' });
      const data = await res.json();
      setPruebas((p) => ({ ...p, [canal.clave]: data }));
    } catch {
      setPruebas((p) => ({ ...p, [canal.clave]: { ok: false, mensaje: 'Error al ejecutar la prueba.' } }));
    } finally {
      setProbando((s) => ({ ...s, [canal.clave]: false }));
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {canales.map((canal) => (
        <CanalCard
          key={canal.clave}
          canal={canal}
          onChange={(campo, valor) => editar(canal.clave, campo, valor)}
          onGuardar={() => guardar(canal)}
          onProbar={() => probar(canal)}
          guardando={!!guardando[canal.clave]}
          probando={!!probando[canal.clave]}
          prueba={pruebas[canal.clave]}
        />
      ))}
    </div>
  );
}
