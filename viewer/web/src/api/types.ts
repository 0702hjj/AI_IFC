export interface ModelInfo {
  id: string;
  name: string;
  size: number;
  status: "converting" | "ready" | "failed";
  createdAt: string;
  error: string;
}
