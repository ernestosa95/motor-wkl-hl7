import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2 } from 'lucide-react';
import { apiFetch } from './Login';

// En MSH el separador '|' cuenta como MSH-1, por eso el offset es distinto.
function parseSegmento(linea) {
  const partes = linea.split('|');
  const seg = partes[0];
  const campos = [];
  if (seg === 'MSH') {
    campos.push({ pos: 1, valor: '|' });
    campos.push({ pos: 2, valor: partes[1] ?? '' });
    for (let i = 2; i < partes.length; i++) campos.push({ pos: i + 1, valor: partes[i] });
  } else {
    for (let i = 1; i < partes.length; i++) campos.push({ pos: i, valor: partes[i] });
  }
  return { seg, campos };
}

function Segmento({ linea, mostrarNumeros }) {
  const { seg, campos } = parseSegmento(linea);
  const [marcado, setMarcado] = useState(null);
  return (
    <div className="flex flex-wrap items-stretch gap-1 py-1.5 border-b border-zinc-100 last:border-0">
      <span className="inline-flex items-center rounded bg-zinc-800 text-white font-mono text-xs font-semibold px-2 py-1 mr-1">
        {seg}
      </span>
      {campos.map((c, i) => {
        const activo = marcado === c.pos;
        return (
          <button
            key={i}
            onClick={() => setMarcado(activo ? null : c.pos)}
            title={`${seg}-${c.pos}`}
            className={`group relative inline-flex flex-col items-start rounded px-2 py-1 font-mono text-xs transition-colors ${
              activo ? 'bg-teal-100 ring-1 ring-teal-400' : 'bg-zinc-50 hover:bg-zinc-100'
            }`}
          >
            {(mostrarNumeros || activo) && (
              <span className="text-[9px] leading-none text-teal-600 font-semibold">{seg}-{c.pos}</span>
            )}
            <span className="text-zinc-800 leading-tight">{c.valor === '' ? '·' : c.valor}</span>
          </button>
        );
      })}
    </div>
  );
}

function Mensaje({ texto }) {
  const [mostrarNumeros, setMostrarNumeros] = useState(false);
  if (!texto) return <p className="text-sm text-zinc-400 py-4">Sin mensaje generado.</p>;
  const lineas = texto.split(/\r|\n/).filter(Boolean);
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-zinc-400">Clic en un campo para marcar su número de posición.</span>
        <label className="flex items-center gap-1.5 text-xs text-zinc-500 cursor-pointer select-none">
          <input type="checkbox" checked={mostrarNumeros} onChange={(e) => setMostrarNumeros(e.target.checked)} />
          Mostrar todos los números
        </label>
      </div>
      <div className="rounded-lg border border-zinc-200 bg-white px-3 py-1">
        {lineas.map((l, i) => <Segmento key={i} linea={l} mostrarNumeros={mostrarNumeros} />)}
      </div>
      <details className="mt-3">
        <summary className="text-xs text-zinc-400 cursor-pointer">Ver crudo</summary>
        <pre className="mt-2 rounded-lg bg-zinc-900 text-zinc-100 text-xs p-3 overflow-x-auto whitespace-pre-wrap font-mono">
          {lineas.join('\n')}
        </pre>
      </details>
    </div>
  );
}

export default function HL7Viewer({ registro, onClose }) {
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [tab, setTab] = useState('adt');

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/trazabilidad/${registro.id}/hl7`);
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error(e);
      } finally {
        setCargando(false);
      }
    })();
  }, [registro.id]);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-zinc-900/40 backdrop-blur-sm p-4 sm:py-10" onClick={onClose}>
      <div className="w-full max-w-3xl my-auto flex flex-col rounded-xl bg-white shadow-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-100">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">Mensajes HL7 emitidos</h3>
            <p className="text-xs text-zinc-400 font-mono">{registro.accession}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
            <X size={18} />
          </button>
        </div>
        <div className="flex gap-1 px-6 pt-4">
          {['adt', 'orm'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                tab === t ? 'bg-teal-600 text-white' : 'text-zinc-500 hover:bg-zinc-100'
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="px-6 py-4">
          {cargando ? (
            <div className="flex items-center gap-2 text-sm text-zinc-400 py-8 justify-center">
              <Loader2 size={16} className="animate-spin" /> Cargando…
            </div>
          ) : (
            <Mensaje texto={data?.hl7?.[tab]} />
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
