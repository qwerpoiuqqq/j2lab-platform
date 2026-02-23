import { createBrowserRouter } from 'react-router-dom';
import Layout from '@/components/layout/Layout';
import ProtectedRoute from './ProtectedRoute';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import OrdersPage from '@/pages/OrdersPage';
import OrderDetailPage from '@/pages/OrderDetailPage';
import CampaignsPage from '@/pages/CampaignsPage';
import CampaignDetailPage from '@/pages/CampaignDetailPage';
import UsersPage from '@/pages/UsersPage';
import CompaniesPage from '@/pages/CompaniesPage';
import ProductsPage from '@/pages/ProductsPage';
import SettingsPage from '@/pages/SettingsPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          {
            path: '/',
            element: <DashboardPage />,
          },
          {
            path: '/orders',
            element: <OrdersPage />,
          },
          {
            path: '/orders/:id',
            element: <OrderDetailPage />,
          },
          {
            path: '/campaigns',
            element: <CampaignsPage />,
          },
          {
            path: '/campaigns/:id',
            element: <CampaignDetailPage />,
          },
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin']}
              />
            ),
            children: [
              {
                path: '/users',
                element: <UsersPage />,
              },
              {
                path: '/products',
                element: <ProductsPage />,
              },
            ],
          },
          {
            element: (
              <ProtectedRoute allowedRoles={['system_admin']} />
            ),
            children: [
              {
                path: '/companies',
                element: <CompaniesPage />,
              },
              {
                path: '/settings',
                element: <SettingsPage />,
              },
            ],
          },
        ],
      },
    ],
  },
]);
