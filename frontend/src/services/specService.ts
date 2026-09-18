import apiClient from './apiClient';

export const specService = {
  async uploadFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/specifications/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async submitJson(payload: any) {
    const response = await apiClient.post('/specifications', payload);
    return response.data;
  },

  async getSpecification(specId: string) {
    const response = await apiClient.get(`/specifications/${specId}`);
    return response.data;
  },
};
