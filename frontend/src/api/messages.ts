import { apiV1Request } from "@/api/client";
import type { MessagePurpose, MessageVersion } from "@/types/messages";

export async function fetchMessagePurposes(): Promise<{ purposes: MessagePurpose[] }> {
  return apiV1Request("/messages/");
}

export async function createMessagePurpose(data: {
  name: string;
}): Promise<{ purpose: MessagePurpose }> {
  return apiV1Request("/messages/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateMessagePurpose(
  purposeId: string,
  data: { name: string },
): Promise<{ purpose: MessagePurpose }> {
  return apiV1Request(`/messages/${purposeId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteMessagePurpose(purposeId: string): Promise<void> {
  await apiV1Request(`/messages/${purposeId}/`, { method: "DELETE" });
}

export async function updateMessageVersion(
  versionId: string,
  data: Partial<{ subject: string; html_content: string }>,
): Promise<{ version: MessageVersion }> {
  return apiV1Request(`/messages/versions/${versionId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
