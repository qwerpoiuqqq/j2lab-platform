import apiClient from './client';
import type { PriceMatrixRow, ProductSchema } from '@/types';

export const pricesApi = {
  getProductSchema: async (productId: number): Promise<ProductSchema> => {
    const response = await apiClient.get(`/products/${productId}/schema`);
    return response.data;
  },

  getMatrix: async (): Promise<{ rows: PriceMatrixRow[]; sellers: { id: string; name: string }[] }> => {
    const response = await apiClient.get('/products/prices/matrix');
    return response.data;
  },

  updatePrice: async (productId: number, data: {
    user_id?: string;
    role?: string;
    price: number;
  }): Promise<void> => {
    const today = new Date().toISOString().split('T')[0];
    await apiClient.post(`/products/${productId}/prices`, {
      product_id: productId,
      role: data.role || undefined,
      user_id: data.user_id || undefined,
      unit_price: data.price,
      effective_from: today,
    });
  },
};
