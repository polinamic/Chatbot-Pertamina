import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import AdminLayout from './components/AdminLayout';
import Dashboard from './pages/admin/Dashboard';
import KnowledgeBase from './pages/admin/KnowledgeBase';
import AiConfig from './pages/admin/AiConfig';
import Profile from './pages/admin/Profile'; // <-- IMPORT BARU

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="knowledge-base" element={<KnowledgeBase />} />
          <Route path="ai-config" element={<AiConfig />} />
          <Route path="profile" element={<Profile />} /> {/* <-- RUTE BARU */}
          
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;