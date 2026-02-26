import apiClient from './client';
import type {
  Order,
  OrderItem,
  CreateOrderRequest,
  BulkStatusRequest,
  DeadlineUpdateRequest,
  ExcelUploadResponse,
  PaginatedResponse,
} from '@/types';

export const ordersApi = {
  list: async (params?: {
    page?: number;
    size?: number;
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

  reject: async (id: number, reason: string): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/reject`, { reason });
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

  // New endpoints for enhanced features

  approve: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/approve`);
    return response.data;
  },

  bulkStatus: async (data: BulkStatusRequest): Promise<{ updated: number }> => {
    const response = await apiClient.post('/orders/bulk-status', data);
    return response.data;
  },

  updateDeadline: async (id: number, data: DeadlineUpdateRequest): Promise<Order> => {
    const response = await apiClient.patch<Order>(`/orders/${id}/deadline`, data);
    return response.data;
  },

  downloadExcelTemplate: async (productId: number): Promise<Blob> => {
    const response = await apiClient.get(`/orders/excel-template/${productId}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  uploadExcel: async (file: File): Promise<ExcelUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/orders/excel-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  exportItems: async (orderId: number): Promise<Blob> => {
    const response = await apiClient.get(`/orders/${orderId}/items/export`, {
      responseType: 'blob',
    });
    return response.data;
  },

  exportList: async (params?: {
    status?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> => {
    const response = await apiClient.get('/orders/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};
