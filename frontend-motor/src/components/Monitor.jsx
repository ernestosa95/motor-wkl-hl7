import React, { useState, useEffect } from 'react';

export default function Monitor() {
  const [ordenes, setOrdenes] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const fetchTrazabilidad = async () => {
      try {
        const respuesta = await fetch('http://127.0.0.1:8000/api/v1/trazabilidad');
        if (respuesta.ok) {
          const datos = await respuesta.json();
          setOrdenes(datos);
        } else {
          console.error("[!] Error de conexión con el motor core.");
        }
      } catch (error) {
        console.error("[!] Error de red al intentar obtener la trazabilidad:", error);
      } finally {
        setCargando(false);
      }
    };

    fetchTrazabilidad();
    const intervalo = setInterval(fetchTrazabilidad, 3000);
    return () => clearInterval(intervalo);
  }, []);

  // Cálculo dinámico para la barra de resumen
  const stats = {
    ingresados: ordenes.filter(o => o.estado === 'INGRESADO').length,
    transformados: ordenes.filter(o => o.estado === 'TRANSFORMADO').length,
    completados: ordenes.filter(o => o.estado === 'COMPLETADO').length,
    errores: ordenes.filter(o => o.estado.startsWith('ERROR')).length
  };

  if (cargando) {
    return (
      <div className="border border-gray-200 p-8 rounded text-center text-gray-500 bg-gray-50">
        <span className="animate-pulse">Sincronizando con PostgreSQL...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      
      {/* Barra de Resumen Minimalista */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded p-4 flex flex-col items-center justify-center shadow-sm">
          <span className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Ingresados</span>
          <span className="text-2xl font-light text-gray-800">{stats.ingresados}</span>
        </div>
        <div className="bg-white border border-gray-200 rounded p-4 flex flex-col items-center justify-center shadow-sm">
          <span className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Transformados</span>
          <span className="text-2xl font-light text-blue-600">{stats.transformados}</span>
        </div>
        <div className="bg-white border border-gray-200 rounded p-4 flex flex-col items-center justify-center shadow-sm">
          <span className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Completados</span>
          <span className="text-2xl font-light text-green-600">{stats.completados}</span>
        </div>
        <div className="bg-white border border-gray-200 rounded p-4 flex flex-col items-center justify-center shadow-sm">
          <span className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-1">Errores</span>
          <span className="text-2xl font-light text-red-600">{stats.errores}</span>
        </div>
      </div>

      {/* Tabla de Trazabilidad */}
      <div className="bg-white rounded border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700">
              <th className="p-4">Correlation ID</th>
              <th className="p-4">Patient ID</th>
              <th className="p-4">Accession Number</th>
              <th className="p-4">Modalidad</th>
              <th className="p-4">Estado</th>
              <th className="p-4">Última Actualización</th>
            </tr>
          </thead>
          <tbody className="text-sm text-gray-600">
            {ordenes.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-8 text-center text-gray-400">
                  No hay órdenes registradas en el sistema.
                </td>
              </tr>
            ) : (
              ordenes.map((orden, index) => (
                <tr key={index} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                  <td className="p-4 font-mono text-xs">{orden.id.substring(0, 13)}...</td>
                  <td className="p-4 font-medium">{orden.paciente}</td>
                  <td className="p-4">{orden.accession}</td>
                  <td className="p-4 font-semibold text-gray-800">{orden.modalidad}</td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      orden.estado === 'COMPLETADO' ? 'bg-green-100 text-green-800' : 
                      orden.estado === 'INGRESADO' ? 'bg-yellow-100 text-yellow-800' :
                      orden.estado === 'TRANSFORMADO' ? 'bg-blue-100 text-blue-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {orden.estado}
                    </span>
                  </td>
                  <td className="p-4">{orden.fecha}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}