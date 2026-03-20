import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IntegrationSettingsResponseType {
  langflow_base_url: string;
  langflow_auth_token_configured: boolean;
  langflow_timeout_seconds: number;
  langflow_retry_count: number;
  langflow_retry_backoff_seconds: number;
  langflow_default_flow_id: string | null;
  langflow_default_project_id: string | null;
  owui_base_url: string;
  owui_auth_token_configured: boolean;
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
  restart_required: boolean;
}

export const useGetIntegrationSettings: useQueryFunctionType<
  undefined,
  IntegrationSettingsResponseType
> = (options) => {
  const { query } = UseRequestProcessor();

  const getIntegrationSettingsFn = async () => {
    const response = await api.get<IntegrationSettingsResponseType>(
      `${getURL("ADMIN_SETTINGS")}/integrations`,
    );
    return response.data;
  };

  return query(["useGetIntegrationSettings"], getIntegrationSettingsFn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
