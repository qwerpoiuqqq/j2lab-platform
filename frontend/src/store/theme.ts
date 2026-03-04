import { create } from 'zustand';

interface ThemeState {
  theme: 'light';
}

export const useThemeStore = create<ThemeState>()(() => ({
  theme: 'light',
}));
