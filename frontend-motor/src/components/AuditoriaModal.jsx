import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, LogIn, AlertTriangle, CheckCircle2, FileText, RotateCcw, Send } from 'lucide-react';
import { apiFetch } from './Login';

const ESTADO_COLOR = {
  INGRESADO: 'text-zinc-600',
  TRANSFORMADO: 'text-blue-600',
  COMPLETADO: 'text-teal-600',
  ERROR_EMISION: 'text-rose-600',
  ERROR_PERMANENTE: 'text-rose-600',
};

const ESTADO_MSG = {
  ENVIADO: { texto: 'Enviado y aceptado', clase: 'text-teal-700 bg-teal-50 ring-teal-200' },
  PENDIENTE: { texto: 'Pendiente / reintentando', clase: 'text-amber-700 bg-amber-50 ring-amber-200' },
  ERROR_PERMANENTE: { texto: 'Error: reintentos agotados', clase: 'text-rose-700 bg-rose-50 ring-rose-200' },
};

export default function AuditoriaModal({ orden, onClose }) {
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState(null); // 'adt' | 'orm' | 'todo'
  const [aviso, setAviso] = useState(null);

  const cargar = async () => {
    try {
      const res = await apiFetch(`/api/v1/trazabilidad/${orden.id}/auditoria`);
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error('Error al cargar auditoría', e);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => { cargar(); }, [orden.id]);

  // Mientras haya un mensaje enviándose o reintentando, se refresca solo.
  const enCurso = !!data && Object.values(data.mensajes || {}).some((m) => m.estado === 'PENDIENTE');
  useEffect(() => {
    if (!enCurso) return undefined;
    const t = setInterval(cargar, 3000);
    return () => clearInterval(t);
  }, [enCurso, orden.id]);

  // Cierra con Escape
  useEffect(() => {
    const f = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, [onClose]);

  const ejecutar = async (accion, tipo) => {
    const clave = tipo || 'todo';
    setOcupado(clave);
    setAviso(null);
    try {
      const url = `/api/v1/trazabilidad/${orden.id}/${accion}${tipo ? `?tipo=${tipo}` : ''}`;
      const res = await apiFetch(url, { method: 'POST' });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) setAviso({ ok: false, texto: d.detail || 'No se pudo completar la acción.' });
      else setAviso({ ok: true, texto: `${accion === 'reenviar' ? 'Reenviando' : 'Reprocesando'}: ${(d.reenviados || d.reprocesados || []).join(' y ')}.` });
      await cargar();
    } finally {
      setOcupado(null);
    }
  };

  const reprocesar = (tipo) => ejecutar('reprocesar', tipo);

  // Reenviar pide confirmación si el destino ya aceptó el mensaje
  const reenviar = (tipo) => {
    const ya = tipo
      ? data?.mensajes?.[tipo]?.estado === 'ENVIADO'
      : Object.values(data?.mensajes || {}).some((m) => m.estado === 'ENVIADO');
    if (ya && !window.confirm(
      `${tipo ? `El ${tipo.toUpperCase()} ya fue aceptado` : 'Esta orden ya tiene mensajes aceptados'} por el destino.\n\n` +
      'Reenviar manda un mensaje nuevo (con otro MSH-10) y puede duplicar o modificar datos en el RIS.\n\n¿Reenviar de todos modos?'
    )) return;
    ejecutar('reenviar', tipo);
  };

  const esError = data && data.estado.startsWith('ERROR');

  // Se dibuja en <body> (portal): dentro del Monitor la capa fija quedaba anclada a un
  // contenedor y no a la pantalla, y la ventana aparecía recortada y desplazada hacia abajo.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3 sm:p-5"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-6xl max-h-[calc(100vh-1.5rem)] flex-col rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Encabezado */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-zinc-100 px-5 py-3">
          <div className="flex items-baseline gap-3 min-w-0">
            <h3 className="text-sm font-semibold text-zinc-900">Auditoría de la orden</h3>
            <span className="font-mono text-xs text-zinc-400">{orden.accession}</span>
            {data && (
              <span className={`text-xs font-medium ${ESTADO_COLOR[data.estado] || 'text-zinc-600'}`}>{data.estado}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {data && (
              <button
                onClick={() => reenviar(null)}
                disabled={!!ocupado}
                title="Vuelve a enviar el ADT y el ORM de esta orden, aunque ya estén aceptados"
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
              >
                <Send size={13} className={ocupado === 'todo' ? 'animate-pulse' : ''} />
                Reenviar orden
              </button>
            )}
            <button onClick={onClose} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
              <X size={18} />
            </button>
          </div>
        </div>

        {cargando ? (
          <div className="px-5 py-12 text-center text-sm text-zinc-400 animate-pulse">Cargando…</div>
        ) : !data ? (
          <div className="px-5 py-12 text-center text-sm text-zinc-400">No se pudo cargar la auditoría.</div>
        ) : (
          // El desplazamiento solo aparece en pantallas muy bajas: lo normal es verlo todo junto.
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {aviso && (
              <div className={`mb-4 rounded-lg px-3 py-2 text-sm ${aviso.ok ? 'bg-teal-50 text-teal-800' : 'bg-rose-50 text-rose-700'}`}>
                {aviso.texto}
              </div>
            )}

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">

              {/* Columna izquierda: estado */}
              <div className="flex flex-col gap-4 lg:col-span-2">
                <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <Dato label="Paciente" valor={data.paciente} />
                  <Dato label="Modalidad" valor={data.modalidad} />
                  <Dato label="Estado actual" valor={data.estado} clase={ESTADO_COLOR[data.estado]} />
                  <Dato label="Reintentos" valor={data.reintentos} />
                </div>

                <div className="grid grid-cols-2 gap-3 border-y border-zinc-100 py-3">
                  <Evento icon={LogIn} color="text-zinc-500" titulo="Ingresó" hora={data.ingresado} />
                  <Evento
                    icon={esError ? AlertTriangle : CheckCircle2}
                    color={esError ? 'text-rose-500' : 'text-teal-500'}
                    titulo="Último cambio"
                    hora={data.actualizado}
                  />
                </div>

                <MensajesEstado
                  mensajes={data.mensajes}
                  ocupado={ocupado}
                  onReprocesar={reprocesar}
                  onReenviar={reenviar}
                />

                {data.detalles_error && (
                  <div className={`rounded-lg border p-3 ${esError ? 'border-rose-200 bg-rose-50' : 'border-amber-200 bg-amber-50'}`}>
                    <p className={`mb-1 text-[11px] font-medium uppercase tracking-wider ${esError ? 'text-rose-500' : 'text-amber-600'}`}>
                      {esError ? 'Detalle del error' : 'Error de un intento anterior (resuelto)'}
                    </p>
                    <p className={`text-xs break-words ${esError ? 'text-rose-800' : 'text-amber-800'}`}>{data.detalles_error.mensaje}</p>
                    {data.detalles_error.cuando && (
                      <p className={`mt-1 font-mono text-[11px] ${esError ? 'text-rose-400' : 'text-amber-500'}`}>{data.detalles_error.cuando}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Columna derecha: mensajes HL7 */}
              <div className="lg:col-span-3">
                <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  <FileText size={13} /> Mensajes HL7 generados
                </p>
                {data.hl7 && (data.hl7.adt || data.hl7.orm) ? (
                  <>
                    {data.hl7.adt && <Bloque titulo="ADT" contenido={data.hl7.adt} />}
                    {data.hl7.orm && <Bloque titulo="ORM" contenido={data.hl7.orm} />}
                  </>
                ) : (
                  <p className="text-sm text-zinc-400">Todavía no hay mensajes generados.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

function MensajesEstado({ mensajes, ocupado, onReprocesar, onReenviar }) {
  const tipos = ['adt', 'orm'];
  if (!mensajes || !tipos.some((t) => mensajes[t])) return null;
  return (
    <div>
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-zinc-400">Estado por mensaje</p>
      <div className="flex flex-col gap-2">
        {tipos.map((t) => {
          const m = mensajes[t];
          if (!m) return null;
          const est = ESTADO_MSG[m.estado] || { texto: m.estado, clase: 'text-zinc-600 bg-zinc-50 ring-zinc-200' };
          const enCurso = m.estado === 'PENDIENTE';
          return (
            <div key={t} className="rounded-lg border border-zinc-200 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-semibold text-zinc-800">{t.toUpperCase()}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${est.clase}`}>{est.texto}</span>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {m.estado === 'ERROR_PERMANENTE' && (
                    <button
                      onClick={() => onReprocesar(t)}
                      disabled={!!ocupado}
                      className="inline-flex items-center gap-1 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                    >
                      <RotateCcw size={12} className={ocupado === t ? 'animate-spin' : ''} />
                      Reprocesar
                    </button>
                  )}
                  <button
                    onClick={() => onReenviar(t)}
                    disabled={!!ocupado || enCurso}
                    title={enCurso ? 'Se está enviando o reintentando' : `Volver a enviar el ${t.toUpperCase()}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
                  >
                    <Send size={12} />
                    Reenviar
                  </button>
                </div>
              </div>
              {m.ok && m.destino && (
                <p className="mt-1 font-mono text-[11px] text-zinc-400">{m.destino} · {m.cuando}</p>
              )}
              {!m.ok && m.ultimo_error && (
                <p className="mt-1 break-words text-xs text-rose-700">
                  {m.ultimo_error}
                  {m.intentos_fallidos ? <span className="text-rose-400"> · {m.intentos_fallidos} intento(s) fallido(s)</span> : null}
                </p>
              )}
              {m.reenvios > 0 && (
                <p className="mt-1 text-[11px] text-zinc-400">
                  Reenviado {m.reenvios} {m.reenvios === 1 ? 'vez' : 'veces'}
                  {m.anterior?.cuando ? ` · aceptado antes: ${m.anterior.cuando}` : ''}
                </p>
              )}
            </div>
          );
        })}
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
    <div className="flex items-start gap-2">
      <Icon size={15} className={`mt-0.5 shrink-0 ${color}`} />
      <div>
        <p className="text-xs text-zinc-700">{titulo}</p>
        <p className="font-mono text-[11px] text-zinc-400">{hora || '—'}</p>
      </div>
    </div>
  );
}

// Un segmento HL7 por línea (el separador real es \r, que el navegador no muestra como salto).
function Bloque({ titulo, contenido }) {
  const texto = typeof contenido === 'string'
    ? contenido.split(/\r\n|\r|\n/).filter(Boolean).join('\n')
    : JSON.stringify(contenido, null, 2);
  return (
    <div className="mb-3">
      <p className="mb-1 text-xs font-semibold text-zinc-500">{titulo}</p>
      <pre className="max-h-[32vh] overflow-auto rounded-lg bg-zinc-900 p-3 text-[11px] leading-relaxed text-zinc-100 whitespace-pre-wrap break-all">
        {texto}
      </pre>
    </div>
  );
}
