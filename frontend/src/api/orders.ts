import apiClient from './client';
import type { Order, OrderItem, CreateOrderRequest, PaginatedResponse } from '@/types';

export const ordersApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    company_id?: number;
    search?: string;
  }): Promise<PaginatedResponse<Order>> => {
    const response = await apiClient.get<PaginatedResponse<Order>>('/orders', { params });
    return response.data;
  },

  get: async (id: number): Promise<Order> => {
    const response = await apiClient.get<Order>(`/orders/${id}`);
    return response.data;
  },

  getItems: async (orderId: number): Promise<OrderItem[]> => {
    const response = await apiClient.get<OrderItem[]>(`/orders/${orderId}/items`);
    return response.data;
  },

  create: async (data: CreateOrderRequest): Promise<Order> => {
    const response = await apiClient.post<Order>('/orders', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Order>): Promise<Order> => {
    const response = await apiClient.patch<Order>(`/orders/${id}`, data);
    return response.data;
  },

  submit: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/submit`);
    return response.data;
  },

  confirmPayment: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/confirm-payment`);
    return response.data;
  },

  reject: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/reject`);
    return response.data;
  },

  cancel: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/cancel`);
    return response.data;
  },

  getDeadlineStatus: async (): Promise<{ product_id: number; product_name: string; deadline: string; remaining: string }[]> => {
    const response = await apiClient.get('/orders/deadline-status');
    return response.data;
  },
};
