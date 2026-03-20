import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { IntegrationSettingsResponseType } from "./use-get-integration-settings";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IntegrationSettingsUpdateRequest {
  langflow_base_url: string;
  langflow_auth_token?: string;
  langflow_timeout_seconds: number;
  langflow_retry_count: number;
  langflow_retry_backoff_seconds: number;
  langflow_default_flow_id?: string;
  langflow_default_project_id?: string;
  owui_base_url: string;
  owui_auth_token?: string;
  owui_timeout_seconds: number;
  owui_retry_count: number;
  owui_retry_backoff_seconds: number;
  owui_failure_policy: string;
  owui_sync_enabled: boolean;
  owui_sync_dry_run: boolean;
  owui_sync_verbose_logs: boolean;
  allowed_origins_csv: string;
  enforce_host_allowlist: boolean;
  host_allowlist_csv: string;
}

export const usePutIntegrationSettings: useMutationFunctionType<
  undefined,
  IntegrationSettingsUpdateRequest,
  IntegrationSettingsResponseType
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function putIntegrationSettings(
    requestData: IntegrationSettingsUpdateRequest,
  ): Promise<IntegrationSettingsResponseType> {
    const res = await api.put(
      `${getURL("ADMIN_SETTINGS")}/integrations`,
      requestData,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    IntegrationSettingsResponseType,
    any,
    IntegrationSettingsUpdateRequest
  > = mutate(["usePutIntegrationSettings"], putIntegrationSettings, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetIntegrationSettings"] });
    },
    ...options,
  });

  return mutation;
};
