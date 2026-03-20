import { createBrowserRouter, Navigate } from 'react-router-dom';
import Layout from '@/components/layout/Layout';
import ProtectedRoute from './ProtectedRoute';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import OrdersPage from '@/pages/OrdersPage';
import OrderDetailPage from '@/pages/OrderDetailPage';
import OrderGridPage from '@/pages/OrderGridPage';
import CampaignsPage from '@/pages/CampaignsPage';
import CampaignDetailPage from '@/pages/CampaignDetailPage';
import CampaignAddPage from '@/pages/CampaignAddPage';
import CampaignUploadPage from '@/pages/CampaignUploadPage';
import SuperapAccountsPage from '@/pages/SuperapAccountsPage';
import CampaignTemplatesPage from '@/pages/CampaignTemplatesPage';

import UsersPage from '@/pages/UsersPage';
import CompaniesPage from '@/pages/CompaniesPage';
import ProductsPage from '@/pages/ProductsPage';
import PriceMatrixPage from '@/pages/PriceMatrixPage';
import CategoriesPage from '@/pages/CategoriesPage';
import RewardSettingsPage from '@/pages/RewardSettingsPage';
import SettingsPage from '@/pages/SettingsPage';
import SettlementPage from '@/pages/SettlementPage';
import SettlementSecretPage from '@/pages/SettlementSecretPage';
import CalendarPage from '@/pages/CalendarPage';
import NoticesPage from '@/pages/NoticesPage';
import SubAccountsPage from '@/pages/SubAccountsPage';
import DeadlineBatchPage from '@/pages/DeadlineBatchPage';
import NotFoundPage from '@/pages/NotFoundPage';

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
            path: '/orders/grid',
            element: <OrderGridPage />,
          },
          {
            path: '/orders/:id',
            element: <OrderDetailPage />,
          },
          {
            path: '/notices',
            element: <NoticesPage />,
          },
          // Order handler routes - system_admin, company_admin, order_handler
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin', 'order_handler']}
              />
            ),
            children: [
              {
                path: '/orders/deadline-batch',
                element: <DeadlineBatchPage />,
              },
            ],
          },
          // Campaign routes - system_admin, company_admin, order_handler
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin', 'order_handler']}
              />
            ),
            children: [
              {
                path: '/campaigns',
                element: <CampaignsPage />,
              },
              {
                path: '/campaigns/add',
                element: <CampaignAddPage />,
              },
              {
                path: '/campaigns/upload',
                element: <CampaignUploadPage />,
              },
              {
                path: '/campaigns/accounts',
                element: <SuperapAccountsPage />,
              },
              {
                path: '/campaigns/:id',
                element: <CampaignDetailPage />,
              },
              {
                path: '/assignments',
                element: <Navigate to="/orders" replace />,
              },
            ],
          },
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin', 'order_handler']}
              />
            ),
            children: [
              {
                path: '/users',
                element: <UsersPage />,
              },
            ],
          },
          // Admin routes - system_admin, company_admin
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin']}
              />
            ),
            children: [
              {
                path: '/campaigns/templates',
                element: <CampaignTemplatesPage />,
              },
              {
                path: '/products',
                element: <ProductsPage />,
              },
              {
                path: '/products/prices/matrix',
                element: <PriceMatrixPage />,
              },
              {
                path: '/products/categories',
                element: <CategoriesPage />,
              },
              {
                path: '/products/reward-settings',
                element: <RewardSettingsPage />,
              },
              {
                path: '/settlements',
                element: <SettlementPage />,
              },
            ],
          },
          // Calendar - all except sub_account
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin', 'order_handler', 'distributor']}
              />
            ),
            children: [
              {
                path: '/calendar',
                element: <CalendarPage />,
              },
            ],
          },
          // Distributor routes
          {
            element: (
              <ProtectedRoute
                allowedRoles={['system_admin', 'company_admin', 'distributor']}
              />
            ),
            children: [
              {
                path: '/sub-accounts',
                element: <SubAccountsPage />,
              },
            ],
          },
          // System admin only
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
              {
                path: '/settlements/secret',
                element: <SettlementSecretPage />,
              },
            ],
          },
          {
            path: '*',
            element: <NotFoundPage />,
          },
        ],
      },
    ],
  },
]);
