import React from 'react';

function KnowledgeBase() {
  const dummyDocuments = [
    { id: 'DOC-001', title: 'SOP Troubleshooting Jaringan WiFi 2026.pdf', date: '2026-02-20', status: 'Active' },
    { id: 'DOC-002', title: 'Panduan Reset Password Akun Email Korporat.pdf', date: '2026-02-21', status: 'Active' },
    { id: 'DOC-003', title: 'Manual Instalasi Printer HP LaserJet.docx', date: '2026-02-22', status: 'Inactive' },
    { id: 'DOC-004', title: 'Kebijakan Keamanan Data Perusahaan.pdf', date: '2026-02-23', status: 'Active' },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div>
          <h3 className="text-lg font-bold text-gray-800">Daftar Dokumen SOP</h3>
          <p className="text-sm text-gray-500">Kelola dokumen referensi untuk kecerdasan buatan (PertaBOT).</p>
        </div>
        <button className="bg-pertaminaBlue hover:bg-blue-800 text-white px-5 py-2.5 rounded-lg font-semibold transition-colors shadow-md">
          + Upload SOP Baru
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 text-gray-600 text-sm uppercase tracking-wider border-b border-gray-200">
              <th className="px-6 py-4 font-semibold">ID Dokumen</th>
              <th className="px-6 py-4 font-semibold">Judul Dokumen</th>
              <th className="px-6 py-4 font-semibold">Tgl Upload</th>
              <th className="px-6 py-4 font-semibold">Status</th>
              <th className="px-6 py-4 font-semibold text-right">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {dummyDocuments.map((doc) => (
              <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 text-sm font-medium text-gray-900">{doc.id}</td>
                <td className="px-6 py-4 text-sm text-gray-700 flex items-center gap-3">
                  <div className="w-8 h-8 bg-red-100 text-pertaminaRed rounded flex items-center justify-center font-bold text-xs">PDF</div>
                  <span className="truncate max-w-xs md:max-w-md">{doc.title}</span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{doc.date}</td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    doc.status === 'Active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {doc.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-right space-x-3">
                  <button className="text-pertaminaBlue hover:text-blue-800 font-semibold transition-colors">Edit</button>
                  <button className="text-pertaminaRed hover:text-red-800 font-semibold transition-colors">Hapus</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default KnowledgeBase;