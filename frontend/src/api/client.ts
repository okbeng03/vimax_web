import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.error?.message || error.message || "Unknown error";
    console.error(`[API Error] ${message}`);
    return Promise.reject(error);
  },
);

export default client;
