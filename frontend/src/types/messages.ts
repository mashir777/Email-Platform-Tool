export type MessageVersionKey = "v1" | "v2" | "v3";

export interface MessageVersion {
  id: string;
  version: MessageVersionKey;
  subject: string;
  html_content: string;
  created_at: string;
  updated_at: string;
}

export interface MessagePurpose {
  id: string;
  name: string;
  versions: MessageVersion[];
  created_at: string;
  updated_at: string;
}
