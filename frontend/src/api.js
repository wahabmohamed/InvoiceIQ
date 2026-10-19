import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
});

export const uploadInvoice = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const listInvoices = () => api.get("/invoices");

export const getStats = () => api.get("/stats");

export const getInvoice = (id) => api.get(`/invoices/${id}`);

export const deleteInvoice = (id) => api.delete(`/invoices/${id}`);

export const extractInvoice = (id) => api.post(`/extract/${id}`);

export const exportInvoice = (id) => api.get(`/invoices/${id}/export`);

export const chat = (question, invoiceIds, history) =>
  api.post("/chat", { question, invoice_ids: invoiceIds, history });

export default api;
