import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, Link } from 'react-router-dom'; // Tambah Link

function AdminLayout() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  // STATE UNTUK DARK MODE
  const [isDarkMode, setIsDarkMode] = useState(false);

  // EFEK AJAIB: Mengubah class "dark" di tag HTML paling luar saat tombol diklik
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const menus = [
    { name: 'Dashboard', path: '/admin/dashboard' },
    { name: 'Knowledge Base (SOP)', path: '/admin/knowledge-base' },
    { name: 'Konfigurasi AI (LLM)', path: '/admin/ai-config' },
  ];

return (
    <div className="flex h-screen w-full font-sans text-gray-800 bg-gray-50 dark:bg-gray-900 transition-colors duration-300 overflow-hidden relative">
      {/* OVERLAY GELAP (HP) */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden" onClick={() => setIsMobileMenuOpen(false)}></div>
      )}

      {/* SIDEBAR */}
      <aside className={`fixed inset-y-0 left-0 transform ${isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"} md:relative md:translate-x-0 w-64 bg-pertaminaBlue dark:bg-blue-950 text-white flex flex-col shadow-xl z-50 transition-transform duration-300 ease-in-out`}>
        <div className="h-20 flex items-center justify-center border-b border-blue-800 relative">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-white text-pertaminaBlue rounded flex items-center justify-center font-bold">P</div>
            <h1 className="text-xl font-bold tracking-wider">PertaBOT</h1>
          </div>
          <button className="absolute right-4 md:hidden text-white text-2xl" onClick={() => setIsMobileMenuOpen(false)}>&times;</button>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2">
          {menus.map((menu) => (
            <NavLink
              key={menu.name} to={menu.path} onClick={() => setIsMobileMenuOpen(false)}
              className={({ isActive }) =>
                `w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors duration-200 ${
                  isActive ? 'bg-pertaminaRed text-white font-semibold shadow-md' : 'hover:bg-blue-800 text-blue-100'
                }`
              }
            >
              <div className="w-5 h-5 bg-white/20 rounded-full flex-shrink-0"></div>
              <span className="truncate">{menu.name}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* KONTEN KANAN */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        
        {/* HEADER */}
        <header className="h-20 bg-white dark:bg-gray-800 shadow-sm flex items-center justify-between px-4 md:px-8 z-30 relative transition-colors duration-300">
          
          <div className="flex items-center gap-4">
            <button className="md:hidden text-2xl text-pertaminaBlue dark:text-blue-400" onClick={() => setIsMobileMenuOpen(true)}>&#9776;</button>
            <h2 className="text-xl font-bold text-gray-800 dark:text-white hidden md:block">Portal Admin IT</h2>
          </div>

          <div className="flex items-center gap-6">
            
            {/* SAKLAR DARK MODE TAMPAN ☀️/🌙 */}
            <button 
              onClick={() => setIsDarkMode(!isDarkMode)}
              className="flex items-center bg-gray-100 dark:bg-gray-700 p-1.5 rounded-full w-14 h-8 relative transition-colors duration-300 focus:outline-none"
            >
              <div className={`w-6 h-6 rounded-full bg-white shadow-md transform transition-transform duration-300 flex items-center justify-center text-xs ${isDarkMode ? 'translate-x-6' : 'translate-x-0'}`}>
                {isDarkMode ? '🌙' : '☀️'}
              </div>
            </button>

            {/* BAGIAN PROFIL */}
            <div className="relative">
              <button onClick={() => setIsProfileOpen(!isProfileOpen)} className="flex items-center gap-3 focus:outline-none hover:bg-gray-100 dark:hover:bg-gray-700 p-2 rounded-lg transition-colors cursor-pointer">
                <div className="text-right hidden sm:block">
                  <p className="text-sm font-bold text-gray-700 dark:text-gray-200">Dimas Akbar</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Super Admin</p>
                </div>
                <div className="w-10 h-10 bg-gray-300 dark:bg-gray-600 rounded-full border-2 border-pertaminaBlue flex items-center justify-center text-sm font-bold text-gray-700 dark:text-white">
                  DA
                </div>
              </button>

              {/* KOTAK DROPDOWN */}
              {isProfileOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl py-2 z-50 transition-colors duration-300">
                  {/* Gunakan tag <Link> agar pindah halaman tidak loading */}
                  <Link 
                    to="/admin/profile" 
                    onClick={() => setIsProfileOpen(false)} // Tutup kotak setelah diklik
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    👤 Profil Saya
                  </Link>
                  <a href="#pengaturan" className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">⚙️ Pengaturan</a>
                  <hr className="my-1 border-gray-100 dark:border-gray-700" />
                  <a href="#logout" className="block px-4 py-2 text-sm text-pertaminaRed hover:bg-red-50 dark:hover:bg-gray-700 font-bold">🚪 Logout Keluar</a>
                </div>
              )}
            </div>

          </div>
        </header>

        {/* AREA HALAMAN */}
        <div className="flex-1 p-4 md:p-8 overflow-y-auto z-10 relative">
          <Outlet /> 
        </div>
      </main>

    </div>
  );
}

export default AdminLayout;