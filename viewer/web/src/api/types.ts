export interface ModelInfo {
  id: string;
  name: string;
  size: number;
  status: "converting" | "ready" | "failed";
  createdAt: string;
  error: string;
}

export interface IssueCamera {
  eye: [number, number, number];
  look: [number, number, number];
  up: [number, number, number];
}

export type IssueStatus = "open" | "checking" | "resolved";

export interface Issue {
  id: string;
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  status: IssueStatus;
  camera: IssueCamera;
  screenshot: string;
  createdAt: string;
  updatedAt: string;
}

export interface NewIssue {
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  camera: IssueCamera;
}
