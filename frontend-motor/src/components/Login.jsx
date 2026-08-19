import React, { useState } from 'react';

const API = '';

// Helper: hace fetch inyectando el token JWT y redirige a login si expira (401).
export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.reload();
  }
  return res;
}

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(false);

  const submit = async () => {
    setError('');
    setCargando(true);
    try {
      const body = new URLSearchParams({ username, password });
      const res = await fetch(`${API}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      if (!res.ok) {
        setError('Usuario o contraseña incorrectos.');
        return;
      }
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      onLogin();
    } catch {
      setError('No se pudo conectar con el servidor.');
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white border border-gray-200 rounded-lg shadow-sm p-8 flex flex-col gap-4">
        <h1 className="text-lg font-semibold text-gray-800">Motor de Integración DICOM-HL7</h1>
        <p className="text-sm text-gray-500 -mt-2">Iniciar sesión</p>

        <input
          className="border border-gray-200 rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Usuario"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <input
          type="password"
          className="border border-gray-200 rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          onClick={submit}
          disabled={cargando}
          className="bg-blue-600 text-white rounded-md p-3 text-sm font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors"
        >
          {cargando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </div>
    </div>
  );
}
