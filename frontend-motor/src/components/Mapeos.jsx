import React, { useState, useEffect, useMemo } from 'react';
import { Save, Loader2, X, Plus, Settings2 } from 'lucide-react';
import { apiFetch } from './Login';

export default function Mapeos() {
  const [tipo, setTipo] = useState('ADT');
  const [data, setData] = useState(null);
  const [mapeos, setMapeos] = useState({});
  const [valoresFijos, setValoresFijos] = useState({});
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [avanzadas, setAvanzadas] = useState(false);

  const cargar = async (t) => {
    setAviso(null);
    const res = await apiFetch(`/api/v1/mapeos/${t}`);
    if (res.ok) {
      const d = await res.json();
      setData(d);
      setMapeos(d.mapeos || {});
      setValoresFijos(d.valores_fijos || {});
    }
  };

  useEffect(() => { cargar(tipo); }, [tipo]);

  // Campos HL7 agrupados por segmento, para los selectores y avanzadas.
  const gruposHl7 = useMemo(() => {
    const g = {};
    for (const c of data?.catalogo_hl7 || []) (g[c.segmento] ||= []).push(c);
    return g;
  }, [data]);

  const asignados = (tag) => mapeos[tag] || [];

  const agregar = (tag, campo) => {
    if (!campo) return;
    setAviso(null);
    setMapeos((prev) => {
      const actuales = prev[tag] || [];
      if (actuales.includes(campo)) return prev;
      return { ...prev, [tag]: [...actuales, campo] };
    });
  };

  const quitar = (tag, campo) => {
    setAviso(null);
    setMapeos((prev) => ({ ...prev, [tag]: (prev[tag] || []).filter((c) => c !== campo) }));
  };

  const setFijo = (campo, valor) => {
    setValoresFijos((prev) => ({ ...prev, [campo]: valor }));
  };

  const guardar = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      const limpio = Object.fromEntries(Object.entries(mapeos).filter(([, v]) => v && v.length));
      const fijosLimpio = Object.fromEntries(Object.entries(valoresFijos).filter(([, v]) => v && v !== ''));
      const res = await apiFetch(`/api/v1/mapeos/${tipo}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mapeos: limpio, valores_fijos: fijosLimpio }),
      });
      setAviso(res.ok ? { ok: true, texto: 'Mapeo guardado.' } : { ok: false, texto: 'No se pudo guardar.' });
    } catch {
      setAviso({ ok: false, texto: 'Error de conexión.' });
    } finally {
      setGuardando(false);
    }
  };

  if (!data) return <div className="text-sm text-zinc-400">Cargando mapeo…</div>;

  return (
    <div className="flex flex-col gap-4">
      {/* Barra superior: tipo + acciones */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-1 rounded-lg bg-zinc-100 p-1">
          {['ADT', 'ORM'].map((t) => (
            <button
              key={t}
              onClick={() => setTipo(t)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                tipo === t ? 'bg-white text-teal-700 shadow-sm' : 'text-zinc-500 hover:text-zinc-800'
              }`}
            >
              Mensaje {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAvanzadas((v) => !v)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
              avanzadas ? 'border-teal-500 text-teal-700 bg-teal-50' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            <Settings2 size={15} /> Opciones avanzadas
          </button>
          <button
            onClick={guardar}
            disabled={guardando}
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-60 transition-colors"
          >
            {guardando ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Guardar {tipo}
          </button>
        </div>
      </div>

      {aviso && <div className={`text-xs ${aviso.ok ? 'text-teal-700' : 'text-rose-700'}`}>{aviso.texto}</div>}

      {/* Tabla de mapeo: DICOM (izq) -> HL7 (der) */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <div className="grid grid-cols-2 border-b border-zinc-100 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          <div className="px-5 py-3">Tag DICOM</div>
          <div className="px-5 py-3 border-l border-zinc-100">Campos HL7 destino</div>
        </div>
        <div className="divide-y divide-zinc-50">
          {data.catalogo_dicom.map((t) => (
            <div key={t.tag} className="grid grid-cols-2 items-start">
              {/* Izquierda: tag DICOM */}
              <div className="px-5 py-3">
                <div className="font-mono text-xs text-zinc-400">{t.display}</div>
                <div className="text-sm text-zinc-800">{t.nombre}</div>
              </div>
              {/* Derecha: campos HL7 asignados + agregar */}
              <div className="px-5 py-3 border-l border-zinc-100 flex flex-wrap items-center gap-2 min-h-[56px]">
                {asignados(t.tag).map((campo) => (
                  <span key={campo} className="inline-flex items-center gap-1 rounded-full bg-teal-600 text-white text-xs font-medium pl-2.5 pr-1.5 py-1">
                    {campo}
                    <button onClick={() => quitar(t.tag, campo)} className="hover:bg-teal-700 rounded-full p-0.5"><X size={12} /></button>
                  </span>
                ))}
                <SelectorCampo gruposHl7={gruposHl7} yaAsignados={asignados(t.tag)} onAgregar={(campo) => agregar(t.tag, campo)} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Opciones avanzadas: valores fijos */}
      {avanzadas && (
        <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-100">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Valores fijos ({tipo})</h3>
            <p className="text-[11px] text-zinc-400 mt-0.5">Constantes que se escriben siempre en ese campo, sin depender de un tag DICOM. Sobrescriben lo mapeado.</p>
          </div>
          <div className="p-5 grid grid-cols-2 gap-x-6 gap-y-3">
            {(data.catalogo_hl7 || []).map((c) => (
              <div key={c.campo} className="flex items-center gap-3">
                <span className="w-16 shrink-0 font-mono text-xs text-zinc-600">{c.campo}</span>
                <input
                  value={valoresFijos[c.campo] || ''}
                  onChange={(e) => setFijo(c.campo, e.target.value)}
                  placeholder={c.descripcion}
                  className="flex-1 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Selector "+ campo": dropdown agrupado por segmento con los campos aún no asignados.
function SelectorCampo({ gruposHl7, yaAsignados, onAgregar }) {
  const [abierto, setAbierto] = useState(false);
  const disponibles = Object.entries(gruposHl7)
    .map(([seg, campos]) => [seg, campos.filter((c) => !yaAsignados.includes(c.campo))])
    .filter(([, campos]) => campos.length > 0);

  if (disponibles.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setAbierto((v) => !v)}
        className="inline-flex items-center gap-1 rounded-full border border-dashed border-zinc-300 text-zinc-500 text-xs font-medium px-2.5 py-1 hover:border-teal-400 hover:text-teal-600 transition-colors"
      >
        <Plus size={13} /> campo
      </button>
      {abierto && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setAbierto(false)} />
          <div className="absolute z-20 mt-1 w-56 max-h-64 overflow-y-auto rounded-lg border border-zinc-200 bg-white shadow-lg py-1">
            {disponibles.map(([seg, campos]) => (
              <div key={seg}>
                <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{seg}</div>
                {campos.map((c) => (
                  <button
                    key={c.campo}
                    onClick={() => { onAgregar(c.campo); setAbierto(false); }}
                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-50 flex items-baseline gap-2"
                  >
                    <span className="font-mono text-xs text-zinc-700">{c.campo}</span>
                    <span className="text-[11px] text-zinc-400 truncate">{c.descripcion}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
