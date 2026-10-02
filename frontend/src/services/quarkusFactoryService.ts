import apiClient from './apiClient';
import {
  FactoryOrder,
  CreateOrderRequest,
  ClarificationAnswerItem,
  ApproveContractRequest,
  SelectArchitectureRequest,
  ApproveDeliveryRequest,
  ArchitectureProposal
} from '../types/quarkusFactory';

export const quarkusFactoryService = {
  createOrder: async (request: CreateOrderRequest): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>('/quarkus/orders', request);
    return res.data;
  },

  listOrders: async (): Promise<FactoryOrder[]> => {
    const res = await apiClient.get<FactoryOrder[]>('/quarkus/orders');
    return res.data;
  },

  getOrder: async (orderId: string): Promise<FactoryOrder> => {
    const res = await apiClient.get<FactoryOrder>(`/quarkus/orders/${orderId}`);
    return res.data;
  },

  submitAnswers: async (orderId: string, answers: ClarificationAnswerItem[]): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/answers`, { answers });
    return res.data;
  },

  approveContract: async (orderId: string, request: ApproveContractRequest): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/approve-contract`, request);
    return res.data;
  },

  getArchitectureProposal: async (orderId: string): Promise<ArchitectureProposal> => {
    const res = await apiClient.get<ArchitectureProposal>(`/quarkus/orders/${orderId}/architecture-proposal`);
    return res.data;
  },

  selectArchitecture: async (orderId: string, request: SelectArchitectureRequest): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/select-architecture`, request);
    return res.data;
  },

  generateSkeleton: async (orderId: string): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/generate-skeleton`);
    return res.data;
  },

  buildAndTest: async (orderId: string): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/build-and-test`);
    return res.data;
  },

  approveDelivery: async (orderId: string, request: ApproveDeliveryRequest): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/approve-delivery`, request);
    return res.data;
  },

  generateArchetype: async (
    orderId: string,
    request: { selected_pattern: string; chosen_build_tool: string; extensions: any[] }
  ): Promise<FactoryOrder> => {
    const res = await apiClient.post<FactoryOrder>(`/quarkus/orders/${orderId}/generate-archetype`, request);
    return res.data;
  },

  suggestExtension: async (orderId: string, query: string): Promise<any> => {
    const res = await apiClient.post(`/quarkus/orders/${orderId}/suggest-extension`, { query });
    return res.data;
  },

  getExportZipUrl: (orderId: string): string => {
    return `/api/v1/quarkus/orders/${orderId}/export-zip`;
  }
};

