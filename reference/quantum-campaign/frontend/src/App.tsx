import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/common/Layout';
import DashboardPage from './pages/Dashboard';
import UploadPage from './pages/Upload';
import CampaignAddPage from './pages/CampaignAdd';
import AccountManagementPage from './pages/AccountManagement';
import TemplateSettingsPage from './pages/TemplateSettings';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/campaigns/add" element={<CampaignAddPage />} />
          <Route path="/settings/accounts" element={<AccountManagementPage />} />
          <Route path="/settings/templates" element={<TemplateSettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
