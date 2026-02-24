import React from 'react';

function Profile() {
  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* Header Profil */}
      <div className="bg-white dark:bg-gray-800 p-8 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col md:flex-row items-center gap-6 transition-colors duration-300">
        <div className="w-24 h-24 bg-gray-200 dark:bg-gray-700 rounded-full border-4 border-pertaminaBlue flex items-center justify-center text-3xl font-bold text-gray-500 dark:text-gray-300 shadow-md">
          DA
        </div>
        <div className="text-center md:text-left">
          <h2 className="text-2xl font-bold text-gray-800 dark:text-white">Dimas Akbar</h2>
          <p className="text-pertaminaBlue dark:text-blue-400 font-semibold">Super Admin IT PertaBOT</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Bergabung sejak: 10 Januari 2026</p>
        </div>
      </div>

      {/* Form Data Diri */}
      <div className="bg-white dark:bg-gray-800 p-8 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 transition-colors duration-300">
        <h3 className="text-lg font-bold text-gray-800 dark:text-white mb-6 border-b pb-2 dark:border-gray-700">Informasi Akun</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Nama Lengkap</label>
            <input type="text" value="Dimas Akbar" disabled className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">NIP (Nomor Induk Pegawai)</label>
            <input type="text" value="PTM-2026-8890" disabled className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Email Perusahaan</label>
            <input type="email" value="dimas.akbar@pertamina.com" disabled className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Hak Akses (Role)</label>
            <input type="text" value="Administrator" disabled className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-white" />
          </div>
        </div>

        <div className="mt-8 flex gap-4">
          <button className="bg-pertaminaBlue hover:bg-blue-800 text-white px-6 py-2 rounded-lg font-semibold transition-colors">
            Edit Profil
          </button>
          <button className="bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-white px-6 py-2 rounded-lg font-semibold transition-colors">
            Ganti Password
          </button>
        </div>
      </div>
    </div>
  );
}

export default Profile;