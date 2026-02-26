import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { authApi } from '@/api/auth';
import type { LoginRequest } from '@/types';

export function useAuth() {
  const navigate = useNavigate();
  const { user, isAuthenticated, setAuth, setAccessToken, logout: storeLogout, hasRole, isAdmin } = useAuthStore();

  const login = useCallback(
    async (data: LoginRequest) => {
      const tokenResponse = await authApi.login(data);
      // Store tokens first so getMe() can use the access token via interceptor
      useAuthStore.setState({
        accessToken: tokenResponse.access_token,
        refreshToken: tokenResponse.refresh_token,
      });
      // Fetch full user profile
      const me = await authApi.getMe();
      setAuth(me, tokenResponse.access_token, tokenResponse.refresh_token);
      navigate('/');
    },
    [navigate, setAuth],
  );

  const logout = useCallback(async () => {
    try {
      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
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
