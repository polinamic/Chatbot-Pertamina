import React, { useState } from 'react';

function AiConfig() {
  const [temperature, setTemperature] = useState(0.2);
  const [systemPrompt, setSystemPrompt] = useState(
    "Anda adalah PertaBOT, asisten IT support internal untuk PT Pertamina. Jawablah pertanyaan karyawan HANYA berdasarkan dokumen SOP yang diberikan. Gunakan bahasa Indonesia yang profesional dan sopan."
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div>
          <h3 className="text-lg font-bold text-gray-800">Pengaturan Otak AI (LLM Config)</h3>
          <p className="text-sm text-gray-500">Sesuaikan perilaku, tingkat kreativitas, dan aturan dasar operasi PertaBOT.</p>
        </div>
        <button className="bg-pertaminaGreen hover:bg-green-700 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors shadow-md flex items-center gap-2">
          <span>💾</span> Simpan Konfigurasi
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 space-y-8">
        
        {/* Pilihan Model */}
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">Pilihan Model AI Aktif</label>
          <select className="w-full md:w-1/2 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pertaminaBlue bg-gray-50 text-gray-700 font-medium">
            <option>Llama 3 (8B Parameters) - Local On-Premise</option>
            <option>OpenAI GPT-4o Mini - Cloud (Fallback)</option>
          </select>
          <p className="text-xs text-pertaminaBlue mt-2 font-medium">
            ✓ Rekomendasi: Gunakan Llama 3 On-Premise untuk kedaulatan data internal Pertamina.
          </p>
        </div>

        <hr className="border-gray-100" />

        {/* Temperature Slider */}
        <div>
          <div className="flex justify-between items-end mb-3 md:w-1/2">
            <div>
              <label className="block text-sm font-bold text-gray-700">Temperature (Tingkat Halusinasi / Kreativitas)</label>
              <p className="text-xs text-gray-500 mt-1">Mengontrol seberapa kaku bot berpegang pada teks asli SOP.</p>
            </div>
            <span className="text-pertaminaBlue font-extrabold text-lg bg-blue-50 px-4 py-1 rounded-lg border border-blue-100">
              {temperature}
            </span>
          </div>
          
          <input
            type="range" min="0" max="1" step="0.1"
            value={temperature} onChange={(e) => setTemperature(e.target.value)}
            className="w-full md:w-1/2 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-pertaminaRed"
          />
          <div className="flex justify-between w-full md:w-1/2 text-xs text-gray-500 mt-2 font-semibold">
            <span>0.0 (Kaku / Strict SOP)</span>
            <span>1.0 (Sangat Kreatif)</span>
          </div>
        </div>

        <hr className="border-gray-100" />

        {/* System Prompt Editor */}
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">System Prompt (Instruksi Dasar Bot)</label>
          <p className="text-xs text-gray-500 mb-3">Teks ini akan disisipkan di awal percakapan untuk memberikan "kepribadian" pada bot.</p>
          
          <textarea
            rows="5"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="w-full p-4 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-pertaminaBlue bg-gray-50 leading-relaxed text-gray-700 font-mono text-sm"
          ></textarea>
        </div>

      </div>
    </div>
  );
}

export default AiConfig;