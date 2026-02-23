import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { authApi } from '@/api/auth';
import type { LoginRequest } from '@/types';

export function useAuth() {
  const navigate = useNavigate();
  const { user, isAuthenticated, setAuth, logout: storeLogout, hasRole, isAdmin } = useAuthStore();

  const login = useCallback(
    async (data: LoginRequest) => {
      const response = await authApi.login(data);
      setAuth(response.user, response.access_token, response.refresh_token);
      navigate('/');
    },
    [navigate, setAuth],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore logout API errors
    } finally {
      storeLogout();
      navigate('/login');
    }
  }, [navigate, storeLogout]);

  return {
    user,
    isAuthenticated,
    login,
    logout,
    hasRole,
    isAdmin,
  };
}
