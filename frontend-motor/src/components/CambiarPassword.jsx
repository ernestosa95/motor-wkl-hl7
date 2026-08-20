import React, { useState } from 'react';

export default function CambiarPassword({ onListo }) {
  const [pass1, setPass1] = useState('');
  const [pass2, setPass2] = useState('');
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(false);

  const enviar = async () => {
    setError('');
    if (pass1.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (pass1 !== pass2) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setCargando(true);
    try {
      const resp = await fetch('/api/v1/auth/cambiar-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ password_nueva: pass1 }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'No se pudo cambiar la contraseña.');
      }
      onListo();
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-zinc-50">
      <div className="w-full max-w-sm rounded-xl border border-zinc-200 bg-white p-8 shadow-sm">
        <h1 className="text-[15px] font-semibold text-zinc-900">Motor de Integración DICOM-HL7</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Es tu primer inicio de sesión. Definí una contraseña nueva para continuar.
        </p>

        <div className="mt-6 flex flex-col gap-3">
          <input
            type="password"
            placeholder="Nueva contraseña"
            value={pass1}
            onChange={(e) => setPass1(e.target.value)}
            className="rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
          <input
            type="password"
            placeholder="Repetir contraseña"
            value={pass2}
            onChange={(e) => setPass2(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && enviar()}
            className="rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            onClick={enviar}
            disabled={cargando}
            className="mt-2 rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-60"
          >
            {cargando ? 'Guardando...' : 'Cambiar contraseña'}
          </button>
        </div>
      </div>
    </div>
  );
}
