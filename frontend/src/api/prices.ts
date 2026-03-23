import apiClient from './client';
import type { PriceMatrixRow, ProductSchema } from '@/types';

export interface UserMatrixResponse {
  users: { id: string; name: string; role: string; login_id: string }[];
  products: {
    id: number;
    matrix_key: string;
    name: string;
    code?: string;
    category?: string;
    base_price: number;
    campaign_type_variant?: 'traffic' | 'save' | null;
  }[];
  prices: Record<string, Record<string, number>>;
}

export interface RoleMatrixRow {
  product_id: number;
  product_name: string;
  base_price: number;
  cost_price: number | null;
  reduction_rate: number | null;
  prices: Record<string, number>;
}

export interface RoleMatrixResponse {
  rows: RoleMatrixRow[];
  sellers: { id: string; name: string }[];
}

export const pricesApi = {
  getProductSchema: async (productId: number): Promise<ProductSchema> => {
    const response = await apiClient.get(`/products/${productId}/schema`);
    return response.data;
  },

  getRoleMatrix: async (): Promise<RoleMatrixResponse> => {
    const response = await apiClient.get('/products/prices/matrix');
    return response.data;
  },

  getMatrix: async (): Promise<{ rows: PriceMatrixRow[]; sellers: { id: string; name: string }[] }> => {
    const response = await apiClient.get('/products/prices/matrix');
    return response.data;
  },

  getUserMatrix: async (): Promise<UserMatrixResponse> => {
    const response = await apiClient.get('/products/prices/user-matrix');
    return response.data;
  },

  updatePrice: async (
    productId: number,
    data: {
      user_id?: string;
      role?: string;
      price: number;
      campaign_type?: string;
    }
  ): Promise<void> => {
    const today = new Date().toISOString().split('T')[0];
    await apiClient.post(`/products/${productId}/prices`, {
      product_id: productId,
      role: data.role || undefined,
      user_id: data.user_id || undefined,
      campaign_type: data.campaign_type || undefined,
      unit_price: data.price,
      effective_from: today,
    });
  },

  getUserPrices: async (userId: string): Promise<Record<string, number>> => {
    const response = await apiClient.get('/products/prices/user-matrix');
    const data = response.data as UserMatrixResponse;
    return data.prices[userId] || {};
  },
};
