import React, { useState, useEffect, useRef } from 'react';
import { Save, Loader2, Trash2, Upload, Download, AlertTriangle, Search } from 'lucide-react';
import { apiFetch } from './Login';

const input =
  'w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500';

// Celda CSV: se entrecomilla si lleva separador, comillas o saltos de línea.
const celda = (v) => {
  const t = String(v ?? '');
  return /[;"\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
};

// CSV con BOM UTF-8 y ';' como separador: Excel en español lo abre bien (tildes incluidas).
const descargarCsv = (nombre, filas) => {
  const texto = '\ufeff' + filas.map((f) => f.map(celda).join(';')).join('\r\n') + '\r\n';
  const url = URL.createObjectURL(new Blob([texto], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
};

const hoy = () => new Date().toISOString().slice(0, 10).replace(/-/g, '');

export default function Estudios() {
  const [data, setData] = useState(null);
  const [borrador, setBorrador] = useState({}); // por descripcion pendiente: {codigo, destino}
  const [filtro, setFiltro] = useState('');
  const [aviso, setAviso] = useState(null);
  const [ocupado, setOcupado] = useState(null);
  const archivo = useRef(null);

  const cargar = async () => {
    const res = await apiFetch('/api/v1/equivalencias');
    if (res.ok) setData(await res.json());
  };
  useEffect(() => { cargar(); }, []);

  const guardar = async (origen, codigo, destino) => {
    if (!codigo.trim()) {
      setAviso({ ok: false, texto: 'Falta el código de destino.' });
      return;
    }
    setOcupado(origen);
    setAviso(null);
    try {
      const res = await apiFetch('/api/v1/equivalencias', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ descripcion_origen: origen, codigo_destino: codigo, descripcion_destino: destino || '' }),
      });
      if (res.ok) {
        setAviso({ ok: true, texto: `Guardado: ${origen} → ${codigo}.` });
        setBorrador((b) => { const n = { ...b }; delete n[origen]; return n; });
        await cargar();
      } else {
        const d = await res.json().catch(() => ({}));
        setAviso({ ok: false, texto: d.detail || 'No se pudo guardar.' });
      }
    } catch {
      setAviso({ ok: false, texto: 'Error de conexión.' });
    } finally {
      setOcupado(null);
    }
  };

  const exportarPendientes = () =>
    descargarCsv(`estudios_pendientes_${hoy()}.csv`, [
      ['descripcion_origen', 'codigo', 'descripcion_destino', 'ordenes'],
      ...data.pendientes.map((p) => [p.descripcion, '', '', p.cantidad]),
    ]);

  const exportarEquivalencias = () =>
    descargarCsv(`estudios_equivalencias_${hoy()}.csv`, [
      ['descripcion_origen', 'codigo', 'descripcion_destino'],
      ...data.equivalencias.map((e) => [e.descripcion_origen, e.codigo_destino, e.descripcion_destino]),
    ]);

  const eliminar = async (e) => {
    if (!window.confirm(`¿Eliminar la equivalencia de "${e.descripcion_origen}"?`)) return;
    const res = await apiFetch(`/api/v1/equivalencias/${e.id}`, { method: 'DELETE' });
    if (res.ok) await cargar();
    else setAviso({ ok: false, texto: 'No se pudo eliminar.' });
  };

  const importar = async (ev) => {
    const f = ev.target.files?.[0];
    ev.target.value = '';
    if (!f) return;
    setAviso(null);
    // Excel puede guardar en Windows-1252: si no es UTF-8 válido se decodifica así.
    const buf = await f.arrayBuffer();
    let texto;
    try {
      texto = new TextDecoder('utf-8', { fatal: true }).decode(buf);
    } catch {
      texto = new TextDecoder('windows-1252').decode(buf);
    }
    const res = await apiFetch('/api/v1/equivalencias/importar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv: texto }),
    });
    if (res.ok) {
      const r = await res.json();
      const errs = r.errores?.length ? ` ${r.errores.length} fila(s) con error: ${r.errores.slice(0, 3).join(' ')}` : '';
      setAviso({ ok: !r.errores?.length, texto: `Importado: ${r.nuevos} nuevas, ${r.actualizados} actualizadas, ${r.omitidas || 0} sin código (omitidas).${errs}` });
      await cargar();
    } else {
      setAviso({ ok: false, texto: 'No se pudo importar el archivo.' });
    }
  };

  if (!data) return <div className="text-sm text-zinc-400">Cargando estudios…</div>;

  const q = filtro.trim().toLowerCase();
  const lista = data.equivalencias.filter(
    (e) => !q || e.descripcion_origen.toLowerCase().includes(q) || e.codigo_destino.toLowerCase().includes(q)
      || e.descripcion_destino.toLowerCase().includes(q)
  );

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-zinc-500">
        Traduce el texto del estudio que llega del worklist al código del sistema destino. Úsalo en el mensaje ORM con
        <span className="font-mono"> {'{codigo_estudio}'}</span> y <span className="font-mono">{'{descripcion_estudio}'}</span> en
        Mapeo → Valores fijos (ej. OBR-4). Si un estudio no tiene equivalencia, su ORM no se envía y la orden queda con error
        hasta que lo cargues y reprocese.
      </p>

      {aviso && (
        <div className={`rounded-lg px-3 py-2 text-sm ${aviso.ok ? 'bg-teal-50 text-teal-800' : 'bg-rose-50 text-rose-700'}`}>
          {aviso.texto}
        </div>
      )}

      {/* Pendientes */}
      {data.pendientes.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-white overflow-hidden">
          <div className="px-5 py-3 border-b border-amber-100 bg-amber-50 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={15} className="text-amber-600" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-700">
                Sin código ({data.pendientes.length})
              </h3>
            </div>
            <button
              onClick={exportarPendientes}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
              title="Descarga un CSV con los pendientes para completar el código y volver a importarlo"
            >
              <Download size={14} /> Exportar pendientes (CSV)
            </button>
          </div>
          <div className="divide-y divide-zinc-100">
            {data.pendientes.map((p) => {
              const b = borrador[p.descripcion] || { codigo: '', destino: '' };
              const set = (campo, v) => setBorrador((x) => ({ ...x, [p.descripcion]: { ...b, [campo]: v } }));
              return (
                <div key={p.descripcion} className="px-5 py-3 grid grid-cols-12 gap-3 items-center">
                  <div className="col-span-5 text-sm text-zinc-800">
                    {p.descripcion}
                    <span className="ml-2 text-[11px] text-zinc-400">{p.cantidad} orden(es)</span>
                  </div>
                  <input className={`${input} col-span-2 font-mono`} placeholder="Código destino" value={b.codigo}
                    onChange={(e) => set('codigo', e.target.value)} />
                  <input className={`${input} col-span-4`} placeholder="Descripción destino (opcional)" value={b.destino}
                    onChange={(e) => set('destino', e.target.value)} />
                  <button
                    onClick={() => guardar(p.descripcion, b.codigo, b.destino)}
                    disabled={ocupado === p.descripcion}
                    className="col-span-1 inline-flex items-center justify-center gap-1 rounded-lg bg-teal-600 text-white text-sm font-medium py-1.5 hover:bg-teal-700 disabled:opacity-50"
                  >
                    {ocupado === p.descripcion ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Equivalencias cargadas */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-zinc-100 flex items-center justify-between gap-3 flex-wrap">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Equivalencias ({data.equivalencias.length})
          </h3>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-2.5 text-zinc-400" />
              <input className={`${input} pl-8 w-56`} placeholder="Buscar…" value={filtro}
                onChange={(e) => setFiltro(e.target.value)} />
            </div>
            <button
              onClick={exportarEquivalencias}
              disabled={data.equivalencias.length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
              title="Descarga las equivalencias cargadas (respaldo o edición masiva)"
            >
              <Download size={15} /> Exportar CSV
            </button>
            <input ref={archivo} type="file" accept=".csv,.txt" className="hidden" onChange={importar} />
            <button
              onClick={() => archivo.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-50"
              title="CSV con columnas: descripción de origen ; código ; descripción de destino (opcional)"
            >
              <Upload size={15} /> Importar CSV
            </button>
          </div>
        </div>
        {lista.length === 0 ? (
          <div className="px-5 py-6 text-sm text-zinc-400">
            {data.equivalencias.length === 0 ? 'Aún no hay equivalencias cargadas.' : 'Sin resultados.'}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-400 border-b border-zinc-100">
                <th className="px-5 py-2 font-medium">Texto del worklist</th>
                <th className="px-3 py-2 font-medium">Código</th>
                <th className="px-3 py-2 font-medium">Descripción destino</th>
                <th className="px-5 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {lista.map((e) => (
                <tr key={e.id}>
                  <td className="px-5 py-2 text-zinc-800">{e.descripcion_origen}</td>
                  <td className="px-3 py-2 font-mono text-zinc-700">{e.codigo_destino}</td>
                  <td className="px-3 py-2 text-zinc-600">{e.descripcion_destino}</td>
                  <td className="px-5 py-2 text-right">
                    <button onClick={() => eliminar(e)} className="text-zinc-400 hover:text-rose-600" title="Eliminar">
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
