import React, { useState, useEffect } from 'react';
import { X, LogIn, RefreshCw, AlertTriangle, CheckCircle2, FileText } from 'lucide-react';
import { apiFetch } from './Login';

const ESTADO_COLOR = {
  INGRESADO: 'text-zinc-600',
  TRANSFORMADO: 'text-blue-600',
  COMPLETADO: 'text-teal-600',
  ERROR_EMISION: 'text-rose-600',
  ERROR_PERMANENTE: 'text-rose-600',
};

export default function AuditoriaModal({ orden, onClose }) {
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/trazabilidad/${orden.id}/auditoria`);
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error('Error al cargar auditoría', e);
      } finally {
        setCargando(false);
      }
    })();
  }, [orden.id]);

  const esError = data && data.estado.startsWith('ERROR');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">Auditoría de la orden</h3>
            <p className="font-mono text-xs text-zinc-400">{orden.accession}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
            <X size={18} />
          </button>
        </div>

        {cargando ? (
          <div className="px-5 py-12 text-center text-sm text-zinc-400 animate-pulse">Cargando…</div>
        ) : !data ? (
          <div className="px-5 py-12 text-center text-sm text-zinc-400">No se pudo cargar la auditoría.</div>
        ) : (
          <div className="p-5 flex flex-col gap-5">

            {/* Datos del paciente / orden */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Dato label="Paciente" valor={data.paciente} />
              <Dato label="Modalidad" valor={data.modalidad} />
              <Dato label="Estado actual" valor={data.estado} clase={ESTADO_COLOR[data.estado]} />
              <Dato label="Reintentos" valor={data.reintentos} />
            </div>

            {/* Línea de tiempo */}
            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-zinc-400">Línea de tiempo</p>
              <div className="flex flex-col gap-3">
                <Evento icon={LogIn} color="text-zinc-500"
                        titulo="Ingresó desde la worklist" hora={data.ingresado} />
                <Evento
                  icon={esError ? AlertTriangle : CheckCircle2}
                  color={esError ? 'text-rose-500' : 'text-teal-500'}
                  titulo={`Estado actual: ${data.estado}`}
                  hora={data.actualizado}
                />
              </div>
              <p className="mt-2 text-[11px] text-zinc-400">
                Se muestran el ingreso y el último cambio de estado. El detalle paso a paso
                estará disponible con el registro de eventos.
              </p>
            </div>

            {/* Detalle del error, si hay */}
            {data.detalles_error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-rose-500">Detalle del error</p>
                <p className="text-sm text-rose-800">{data.detalles_error.mensaje}</p>
                {data.detalles_error.cuando && (
                  <p className="mt-1 font-mono text-xs text-rose-400">{data.detalles_error.cuando}</p>
                )}
              </div>
            )}

            {/* HL7 generados */}
            {data.hl7 && (data.hl7.adt || data.hl7.orm) && (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  <FileText size={13} /> Mensajes HL7 generados
                </p>
                {data.hl7.adt && <Bloque titulo="ADT" contenido={data.hl7.adt} />}
                {data.hl7.orm && <Bloque titulo="ORM" contenido={data.hl7.orm} />}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Dato({ label, valor, clase = 'text-zinc-800' }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-zinc-400">{label}</p>
      <p className={`font-medium ${clase}`}>{valor ?? '—'}</p>
    </div>
  );
}

function Evento({ icon: Icon, color, titulo, hora }) {
  return (
    <div className="flex items-start gap-3">
      <Icon size={16} className={`mt-0.5 shrink-0 ${color}`} />
      <div>
        <p className="text-sm text-zinc-800">{titulo}</p>
        <p className="font-mono text-xs text-zinc-400">{hora || '—'}</p>
      </div>
    </div>
  );
}

function Bloque({ titulo, contenido }) {
  return (
    <div className="mb-2">
      <p className="mb-1 text-xs font-semibold text-zinc-500">{titulo}</p>
      <pre className="overflow-x-auto rounded-lg bg-zinc-900 p-3 text-[11px] leading-relaxed text-zinc-100 whitespace-pre-wrap break-all">
        {typeof contenido === 'string' ? contenido : JSON.stringify(contenido, null, 2)}
      </pre>
    </div>
  );
}
