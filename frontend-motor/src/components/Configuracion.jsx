import React, { useState, useRef } from 'react';
import { Download, Upload, AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';
import { apiFetch } from './Login';

const SECCIONES = [
  { id: 'mensajes', titulo: 'Mensajes ADT y ORM',
    detalle: 'Mapeos y valores fijos de las dos pestañas de Mapeo.', reutilizable: true },
  { id: 'equipos', titulo: 'Equipo por modalidad',
    detalle: 'Código de equipo, descripción y unidad de negocio de cada modalidad.', reutilizable: true },
  { id: 'canales', titulo: 'Canales',
    detalle: 'Host, puerto y AET del worklist y de Mirth. Son propios de cada hospital.', reutilizable: false },
  { id: 'equivalencias', titulo: 'Equivalencias de estudio',
    detalle: 'Estudio del worklist → código del RIS. Cada RIS tiene su propia numeración.', reutilizable: false },
];

const corto = (v, n = 70) => {
  const t = v === null || v === undefined ? '—' : typeof v === 'string' ? v : JSON.stringify(v);
  return t.length > n ? `${t.slice(0, n)}…` : t;
};

const fechaCorta = () => new Date().toISOString().slice(0, 10).replace(/-/g, '');

const descargarJson = (nombre, objeto) => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(objeto, null, 2)], { type: 'application/json;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
};

const errorDe = async (res) => {
  const d = await res.json().catch(() => ({}));
  if (d.detail && d.detail.errores) return d.detail.errores;
  return [typeof d.detail === 'string' ? d.detail : 'No se pudo completar la operación.'];
};

export default function Configuracion() {
  // ---- exportar ----
  const [hospital, setHospital] = useState('');
  const [comentario, setComentario] = useState('');
  const [aExportar, setAExportar] = useState({ mensajes: true, equipos: true, canales: false, equivalencias: false });
  const [exportando, setExportando] = useState(false);
  // ---- importar ----
  const archivo = useRef(null);
  const [config, setConfig] = useState(null);
  const [nombre, setNombre] = useState('');
  const [analisis, setAnalisis] = useState(null);
  const [aImportar, setAImportar] = useState({});
  const [errores, setErrores] = useState([]);
  const [analizando, setAnalizando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [aviso, setAviso] = useState(null);

  const exportar = async () => {
    const secciones = SECCIONES.filter((s) => aExportar[s.id]).map((s) => s.id);
    if (!secciones.length) { setAviso({ ok: false, texto: 'Elegí al menos una sección para exportar.' }); return; }
    setExportando(true);
    setAviso(null);
    try {
      const q = new URLSearchParams({ secciones: secciones.join(','), hospital, comentario });
      const res = await apiFetch(`/api/v1/configuracion/exportar?${q}`);
      if (!res.ok) { setAviso({ ok: false, texto: (await errorDe(res)).join(' ') }); return; }
      const slug = hospital.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'motor';
      descargarJson(`configuracion_${slug}_${fechaCorta()}.json`, await res.json());
      setAviso({ ok: true, texto: `Configuración exportada (${secciones.join(', ')}).` });
    } catch {
      setAviso({ ok: false, texto: 'Error de conexión.' });
    } finally {
      setExportando(false);
    }
  };

  const limpiar = () => {
    setConfig(null); setNombre(''); setAnalisis(null); setErrores([]); setAImportar({});
  };

  const elegirArchivo = async (ev) => {
    const f = ev.target.files?.[0];
    ev.target.value = '';
    if (!f) return;
    limpiar();
    setResultado(null);
    setAviso(null);
    let cfg;
    try {
      cfg = JSON.parse(await f.text());
    } catch {
      setNombre(f.name);
      setErrores(['El archivo no es un JSON válido.']);
      return;
    }
    setNombre(f.name);
    setConfig(cfg);
    setAnalizando(true);
    try {
      const res = await apiFetch('/api/v1/configuracion/importar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ configuracion: cfg, aplicar: false }),
      });
      if (!res.ok) { setErrores(await errorDe(res)); return; }
      const a = await res.json();
      setAnalisis(a);
      setErrores(a.errores || []);
      // Por defecto solo lo reutilizable entre hospitales; canales y equivalencias hay que elegirlos a propósito.
      setAImportar(Object.fromEntries((a.secciones_en_archivo || []).map((s) => [s, SECCIONES.find((x) => x.id === s)?.reutilizable ?? false])));
    } catch {
      setErrores(['Error de conexión.']);
    } finally {
      setAnalizando(false);
    }
  };

  const elegidas = Object.keys(aImportar).filter((s) => aImportar[s]);

  const aplicar = async () => {
    const resumen = elegidas.map((s) => SECCIONES.find((x) => x.id === s)?.titulo).join(', ');
    if (!window.confirm(
      `Se va a aplicar: ${resumen}.\n\n` +
      (aImportar.mensajes ? 'Los mapeos y valores fijos de los mensajes del archivo REEMPLAZAN a los actuales.\n' : '') +
      'Antes se guarda un respaldo de la configuración actual, que se puede volver a importar para revertir.\n\n¿Aplicar?'
    )) return;
    setAplicando(true);
    setAviso(null);
    try {
      const res = await apiFetch('/api/v1/configuracion/importar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ configuracion: config, secciones: elegidas, aplicar: true }),
      });
      if (!res.ok) { setErrores(await errorDe(res)); return; }
      setResultado(await res.json());
      limpiar();
    } catch {
      setErrores(['Error de conexión.']);
    } finally {
      setAplicando(false);
    }
  };

  const check = 'h-4 w-4 rounded border-zinc-300 text-teal-600 focus:ring-teal-500';
  const entrada = 'w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500';

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-zinc-500">
        Exporta la configuración del motor a un archivo para <strong>replicarla en otro hospital</strong> o guardarla como respaldo.
        Al importar se muestra primero una <strong>vista previa</strong> de lo que cambia y, antes de aplicar, se guarda un respaldo de la configuración actual.
      </p>

      {aviso && (
        <div className={`rounded-lg px-3 py-2 text-sm ${aviso.ok ? 'bg-teal-50 text-teal-800' : 'bg-rose-50 text-rose-700'}`}>{aviso.texto}</div>
      )}

      {resultado && (
        <div className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-900">
          <p className="flex items-center gap-2 font-medium"><CheckCircle2 size={16} /> Configuración aplicada: {resultado.secciones.join(', ')}.</p>
          <p className="mt-1 flex items-start gap-2 text-xs text-teal-800">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" />
            <span>Respaldo de la configuración anterior (para revertir, volvé a importarlo): <span className="font-mono break-all">{resultado.respaldo}</span></span>
          </p>
          {resultado.avisos?.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-amber-800">{resultado.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Exportar */}
        <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-100">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Exportar</h3>
          </div>
          <div className="p-5 flex flex-col gap-3">
            <label className="text-[11px] text-zinc-400">Hospital (se guarda en el archivo y en su nombre)
              <input className={entrada} value={hospital} onChange={(e) => setHospital(e.target.value)} placeholder="Ej. Hospital Central" />
            </label>
            <label className="text-[11px] text-zinc-400">Comentario (opcional)
              <input className={entrada} value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Ej. Configuración validada en producción" />
            </label>
            <div className="flex flex-col gap-2">
              {SECCIONES.map((s) => (
                <label key={s.id} className="flex items-start gap-2.5 cursor-pointer">
                  <input type="checkbox" className={`${check} mt-0.5`} checked={aExportar[s.id]}
                    onChange={(e) => setAExportar({ ...aExportar, [s.id]: e.target.checked })} />
                  <span className="text-sm text-zinc-800">{s.titulo}
                    {!s.reutilizable && <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">propio de cada hospital</span>}
                    <span className="block text-[11px] text-zinc-400">{s.detalle}</span>
                  </span>
                </label>
              ))}
            </div>
            <button onClick={exportar} disabled={exportando}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50">
              {exportando ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Descargar configuración
            </button>
          </div>
        </div>

        {/* Importar */}
        <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-100">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Importar</h3>
          </div>
          <div className="p-5 flex flex-col gap-3">
            <input ref={archivo} type="file" accept=".json,application/json" className="hidden" onChange={elegirArchivo} />
            <button onClick={() => archivo.current?.click()} disabled={analizando || aplicando}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50">
              {analizando ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Elegir archivo de configuración…
            </button>
            {nombre && <p className="font-mono text-xs text-zinc-500">{nombre}</p>}
            {!nombre && <p className="text-xs text-zinc-400">Elegí un archivo exportado desde otro motor. Todavía no se cambia nada: primero verás qué cambiaría.</p>}

            {errores.length > 0 && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-rose-700"><AlertTriangle size={13} /> No se puede importar</p>
                <ul className="list-disc pl-5 text-xs text-rose-800 space-y-0.5">{errores.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </div>
            )}
            {analisis && analisis.avisos?.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <ul className="list-disc pl-5 text-xs text-amber-900 space-y-0.5">{analisis.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Vista previa */}
      {analisis && errores.length === 0 && (
        <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-100 flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Vista previa de la importación</h3>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Archivo de <strong>{analisis.origen?.hospital || 'origen no indicado'}</strong>
                {analisis.exportado ? ` · exportado ${analisis.exportado}` : ''}
                {analisis.origen?.comentario ? ` · ${analisis.origen.comentario}` : ''}
              </p>
            </div>
            <button onClick={aplicar} disabled={aplicando || elegidas.length === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-40">
              {aplicando ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />} Aplicar configuración
            </button>
          </div>

          <div className="divide-y divide-zinc-100">
            {(analisis.secciones_en_archivo || []).map((id) => {
              const s = SECCIONES.find((x) => x.id === id);
              const c = analisis.cambios?.[id];
              return (
                <div key={id} className="px-5 py-3">
                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <input type="checkbox" className={`${check} mt-0.5`} checked={!!aImportar[id]}
                      onChange={(e) => setAImportar({ ...aImportar, [id]: e.target.checked })} />
                    <span className="flex-1 text-sm text-zinc-800">
                      {s?.titulo || id}
                      {s && !s.reutilizable && <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">propio de cada hospital</span>}
                      {c && (
                        <span className="ml-3 text-xs text-zinc-500">
                          <span className="text-teal-700">{c.agregar} nuevos</span> · <span className="text-blue-700">{c.cambiar} modificados</span>
                          {id === 'mensajes' && <> · <span className="text-rose-700">{c.quitar} quitados</span></>} · {c.igual} sin cambios
                        </span>
                      )}
                    </span>
                  </label>
                  {id === 'mensajes' && aImportar[id] && (
                    <p className="ml-6 mt-1 text-[11px] text-amber-700">Reemplaza por completo los mapeos y valores fijos de los mensajes que trae el archivo.</p>
                  )}
                  {c && c.detalle.length > 0 && (
                    <details className="ml-6 mt-2">
                      <summary className="cursor-pointer text-xs text-zinc-500">Ver diferencias ({c.detalle.length}{c.recortado ? '+' : ''})</summary>
                      <table className="mt-2 w-full text-xs">
                        <thead>
                          <tr className="text-left text-[10px] uppercase tracking-wider text-zinc-400">
                            <th className="py-1 pr-3 font-medium">Qué</th><th className="py-1 pr-3 font-medium">Acción</th>
                            <th className="py-1 pr-3 font-medium">Antes</th><th className="py-1 font-medium">Después</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-50">
                          {c.detalle.map((d, i) => (
                            <tr key={i}>
                              <td className="py-1 pr-3 font-mono text-zinc-700">{corto(d.clave, 40)}</td>
                              <td className={`py-1 pr-3 ${d.accion === 'quitar' ? 'text-rose-700' : d.accion === 'agregar' ? 'text-teal-700' : 'text-blue-700'}`}>{d.accion}</td>
                              <td className="py-1 pr-3 font-mono text-zinc-500">{corto(d.antes)}</td>
                              <td className="py-1 font-mono text-zinc-800">{corto(d.despues)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {c.recortado && <p className="mt-1 text-[11px] text-zinc-400">Se muestran las primeras diferencias; se aplican todas.</p>}
                    </details>
                  )}
                </div>
              );
            })}
          </div>

          {analisis.valores_del_hospital?.length > 0 && (
            <div className="border-t border-amber-100 bg-amber-50/50 px-5 py-3">
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                <AlertTriangle size={13} /> Revisá estos valores: suelen ser distintos en cada hospital
              </p>
              <div className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3 text-xs">
                {analisis.valores_del_hospital.map((v, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="w-24 shrink-0 font-mono text-zinc-500">{v.mensaje} {v.campo}</span>
                    <span className="font-mono text-zinc-800 break-all">{v.valor}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-zinc-500">
                Por ejemplo, <span className="font-mono">MSH-4</span> identifica al hospital y <span className="font-mono">MSH-5/6</span> es lo que acepta su Mirth.
                Después de importar, ajustalos en <em>Mapeo</em> si hace falta.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
