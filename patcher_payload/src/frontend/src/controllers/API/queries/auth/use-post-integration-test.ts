import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IntegrationConnectionCheck {
  target: string;
  status: string;
  http_status?: number;
  url: string;
  detail: string;
}

export interface IntegrationConnectionTestResponse {
  status: string;
  checks: IntegrationConnectionCheck[];
}

export const usePostIntegrationTest: useMutationFunctionType<
  undefined,
  undefined,
  IntegrationConnectionTestResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  async function postIntegrationTest(): Promise<IntegrationConnectionTestResponse> {
    const res = await api.post(`${getURL("ADMIN_SETTINGS")}/integrations/test`);
    return res.data;
  }

  const mutation: UseMutationResult<
    IntegrationConnectionTestResponse,
    any,
    undefined
  > = mutate(["usePostIntegrationTest"], postIntegrationTest, {
    ...options,
  });

  return mutation;
};
