import React from 'react';

function Dashboard() {
  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* Kartu Statistik */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 border-l-4 border-l-pertaminaBlue hover:shadow-md transition-colors duration-300">
          <p className="text-sm text-gray-500 dark:text-gray-400 font-semibold mb-1">Total Chat Hari Ini</p>
          <h3 className="text-3xl font-bold text-gray-800 dark:text-white">1,284</h3>
          <p className="text-xs text-green-600 dark:text-green-400 mt-2 font-medium">↑ 12% dari kemarin</p>
        </div>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 border-l-4 border-l-pertaminaRed hover:shadow-md transition-colors duration-300">
          <p className="text-sm text-gray-500 dark:text-gray-400 font-semibold mb-1">Eskalasi ke Manusia (WA)</p>
          <h3 className="text-3xl font-bold text-gray-800 dark:text-white">45 <span className="text-lg text-gray-400 font-normal">tiket</span></h3>
          <p className="text-xs text-red-500 dark:text-red-400 mt-2 font-medium">Butuh perhatian CS IT segera</p>
        </div>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 border-l-4 border-l-pertaminaGreen hover:shadow-md transition-colors duration-300">
          <p className="text-sm text-gray-500 dark:text-gray-400 font-semibold mb-1">Dokumen SOP Aktif (RAG)</p>
          <h3 className="text-3xl font-bold text-gray-800 dark:text-white">86 <span className="text-lg text-gray-400 font-normal">PDF</span></h3>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 font-medium">Sinkronisasi terakhir: 1 jam lalu</p>
        </div>

      </div>

      {/* Area Grafik */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 mt-8 min-h-[300px] flex flex-col items-center justify-center border-dashed border-2 transition-colors duration-300">
        <div className="w-16 h-16 bg-blue-50 dark:bg-gray-700 text-pertaminaBlue dark:text-blue-400 rounded-full flex items-center justify-center text-2xl mb-3 shadow-sm">📊</div>
        <h4 className="text-lg font-bold text-gray-700 dark:text-gray-200">Grafik Kategori Keluhan IT</h4>
        <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">Area ini akan diisi dengan Chart.js / Recharts untuk memvisualisasikan data.</p>
      </div>

    </div>
  );
}

export default Dashboard;