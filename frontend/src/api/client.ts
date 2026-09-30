import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "";

export const http = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

export function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || JSON.stringify(item)).join(" ");
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
