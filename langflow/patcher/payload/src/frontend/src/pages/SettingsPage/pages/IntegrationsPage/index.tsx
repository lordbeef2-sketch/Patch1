import * as Form from "@radix-ui/react-form";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  useGetIntegrationSettings,
  usePostIntegrationTest,
  usePutIntegrationSettings,
  type IntegrationSettingsUpdateRequest,
} from "@/controllers/API/queries/auth";
import useAlertStore from "@/stores/alertStore";

const DEFAULT_FORM: IntegrationSettingsUpdateRequest = {
  langflow_base_url: "http://127.0.0.1:7860",
  langflow_auth_token: "",
  langflow_timeout_seconds: 30,
  langflow_retry_count: 2,
  langflow_retry_backoff_seconds: 1,
  langflow_default_flow_id: "",
  langflow_default_project_id: "",
  owui_base_url: "http://127.0.0.1:8081",
  owui_auth_token: "",
  owui_timeout_seconds: 30,
  owui_retry_count: 2,
  owui_retry_backoff_seconds: 1,
  owui_failure_policy: "queue",
  owui_sync_enabled: true,
  owui_sync_dry_run: false,
  owui_sync_verbose_logs: false,
  allowed_origins_csv: "",
  enforce_host_allowlist: false,
  host_allowlist_csv: "127.0.0.1,localhost",
};

export default function IntegrationsPage(): JSX.Element {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [formState, setFormState] =
    useState<IntegrationSettingsUpdateRequest>(DEFAULT_FORM);

  const { data, isLoading } = useGetIntegrationSettings({ retry: false });
  const { mutate: saveSettings, isPending: saving } = usePutIntegrationSettings();
  const { mutate: testConnections, isPending: testing } = usePostIntegrationTest();

  useEffect(() => {
    if (!data) return;

    setFormState({
      langflow_base_url: data.langflow_base_url,
      langflow_auth_token: "",
      langflow_timeout_seconds: data.langflow_timeout_seconds,
      langflow_retry_count: data.langflow_retry_count,
      langflow_retry_backoff_seconds: data.langflow_retry_backoff_seconds,
      langflow_default_flow_id: data.langflow_default_flow_id ?? "",
      langflow_default_project_id: data.langflow_default_project_id ?? "",
      owui_base_url: data.owui_base_url,
      owui_auth_token: "",
      owui_timeout_seconds: data.owui_timeout_seconds,
      owui_retry_count: data.owui_retry_count,
      owui_retry_backoff_seconds: data.owui_retry_backoff_seconds,
      owui_failure_policy: data.owui_failure_policy,
      owui_sync_enabled: data.owui_sync_enabled,
      owui_sync_dry_run: data.owui_sync_dry_run,
      owui_sync_verbose_logs: data.owui_sync_verbose_logs,
      allowed_origins_csv: data.allowed_origins_csv,
      enforce_host_allowlist: data.enforce_host_allowlist,
      host_allowlist_csv: data.host_allowlist_csv,
    });
  }, [data]);

  const onSave = () => {
    saveSettings(formState, {
      onSuccess: () => {
        setSuccessData({
          title: "Integration settings saved. Restart Langflow for runtime updates.",
        });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Integration settings save error",
          list: [error?.response?.data?.detail ?? "Unable to save integration settings."],
        });
      },
    });
  };

  const onTest = () => {
    testConnections(undefined, {
      onSuccess: (response) => {
        const failures = response.checks.filter((check) => check.status !== "PASS");
        if (failures.length === 0) {
          setSuccessData({ title: "Both Langflow and OWUI connectivity checks passed." });
          return;
        }

        setErrorData({
          title: "Connectivity test reported failures",
          list: failures.map((failure) => `${failure.target}: ${failure.detail}`),
        });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Connectivity test failed",
          list: [error?.response?.data?.detail ?? "Unable to test connectivity."],
        });
      },
    });
  };

  return (
    <Form.Root
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
        <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
          <div className="flex w-full flex-col">
            <h2
              className="flex items-center text-lg font-semibold tracking-tight"
              data-testid="settings_integrations_header"
            >
              Integrations
            </h2>
            <p className="text-sm text-muted-foreground">
              Configure OWUI and Langflow connectivity, retries, sync policy, and
              network allowlists in one place.
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>OWUI to Langflow</CardTitle>
            <CardDescription>
              Settings used by OWUI-side tools that call Langflow APIs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Form.Field name="langflow_base_url" className="md:col-span-2">
                <Form.Label>Langflow Base URL</Form.Label>
                <Input
                  value={formState.langflow_base_url}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_base_url: event.target.value,
                    }))
                  }
                  placeholder="http://127.0.0.1:7860"
                  required
                />
              </Form.Field>

              <Form.Field name="langflow_auth_token" className="md:col-span-2">
                <Form.Label>Langflow API Token</Form.Label>
                <Input
                  type="password"
                  value={formState.langflow_auth_token ?? ""}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_auth_token: event.target.value,
                    }))
                  }
                  placeholder={
                    data?.langflow_auth_token_configured
                      ? "Token configured (enter new token to rotate)"
                      : "Optional bearer token"
                  }
                />
              </Form.Field>

              <Form.Field name="langflow_timeout_seconds">
                <Form.Label>Timeout (seconds)</Form.Label>
                <Input
                  type="number"
                  min={1}
                  max={300}
                  value={formState.langflow_timeout_seconds}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_timeout_seconds: Number(event.target.value || 30),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="langflow_retry_count">
                <Form.Label>Retry Count</Form.Label>
                <Input
                  type="number"
                  min={0}
                  max={10}
                  value={formState.langflow_retry_count}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_retry_count: Number(event.target.value || 0),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="langflow_retry_backoff_seconds">
                <Form.Label>Retry Backoff (seconds)</Form.Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={formState.langflow_retry_backoff_seconds}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_retry_backoff_seconds: Number(event.target.value || 0),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="langflow_default_flow_id">
                <Form.Label>Default Flow ID</Form.Label>
                <Input
                  value={formState.langflow_default_flow_id ?? ""}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_default_flow_id: event.target.value,
                    }))
                  }
                  placeholder="Optional"
                />
              </Form.Field>

              <Form.Field name="langflow_default_project_id">
                <Form.Label>Default Project ID</Form.Label>
                <Input
                  value={formState.langflow_default_project_id ?? ""}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      langflow_default_project_id: event.target.value,
                    }))
                  }
                  placeholder="Optional"
                />
              </Form.Field>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Langflow to OWUI</CardTitle>
            <CardDescription>
              Settings for synchronization from Langflow events into OWUI.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Form.Field name="owui_base_url" className="md:col-span-2">
                <Form.Label>OWUI Base URL</Form.Label>
                <Input
                  value={formState.owui_base_url}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_base_url: event.target.value,
                    }))
                  }
                  placeholder="http://127.0.0.1:8081"
                  required
                />
              </Form.Field>

              <Form.Field name="owui_auth_token" className="md:col-span-2">
                <Form.Label>OWUI Admin Token</Form.Label>
                <Input
                  type="password"
                  value={formState.owui_auth_token ?? ""}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_auth_token: event.target.value,
                    }))
                  }
                  placeholder={
                    data?.owui_auth_token_configured
                      ? "Token configured (enter new token to rotate)"
                      : "Optional bearer token"
                  }
                />
              </Form.Field>

              <Form.Field name="owui_timeout_seconds">
                <Form.Label>Timeout (seconds)</Form.Label>
                <Input
                  type="number"
                  min={1}
                  max={300}
                  value={formState.owui_timeout_seconds}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_timeout_seconds: Number(event.target.value || 30),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="owui_retry_count">
                <Form.Label>Retry Count</Form.Label>
                <Input
                  type="number"
                  min={0}
                  max={10}
                  value={formState.owui_retry_count}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_retry_count: Number(event.target.value || 0),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="owui_retry_backoff_seconds">
                <Form.Label>Retry Backoff (seconds)</Form.Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={formState.owui_retry_backoff_seconds}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_retry_backoff_seconds: Number(event.target.value || 0),
                    }))
                  }
                />
              </Form.Field>

              <Form.Field name="owui_failure_policy">
                <Form.Label>Failure Policy</Form.Label>
                <Input
                  value={formState.owui_failure_policy}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      owui_failure_policy: event.target.value,
                    }))
                  }
                  placeholder="queue | skip | error"
                />
              </Form.Field>

              <div className="md:col-span-2 grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="flex items-center justify-between rounded-md border p-3">
                  <p className="text-sm">Enable Sync</p>
                  <Switch
                    checked={formState.owui_sync_enabled}
                    onCheckedChange={(checked) =>
                      setFormState((prev) => ({ ...prev, owui_sync_enabled: checked }))
                    }
                  />
                </div>
                <div className="flex items-center justify-between rounded-md border p-3">
                  <p className="text-sm">Dry Run</p>
                  <Switch
                    checked={formState.owui_sync_dry_run}
                    onCheckedChange={(checked) =>
                      setFormState((prev) => ({ ...prev, owui_sync_dry_run: checked }))
                    }
                  />
                </div>
                <div className="flex items-center justify-between rounded-md border p-3">
                  <p className="text-sm">Verbose Logs</p>
                  <Switch
                    checked={formState.owui_sync_verbose_logs}
                    onCheckedChange={(checked) =>
                      setFormState((prev) => ({ ...prev, owui_sync_verbose_logs: checked }))
                    }
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Network Policy</CardTitle>
            <CardDescription>
              Configure CORS-like origins and host allowlist controls used by
              integration logic.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4">
              <Form.Field name="allowed_origins_csv">
                <Form.Label>Allowed Origins (CSV)</Form.Label>
                <Input
                  value={formState.allowed_origins_csv}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      allowed_origins_csv: event.target.value,
                    }))
                  }
                  placeholder="https://owui.local,https://langflow.local"
                />
              </Form.Field>

              <div className="flex items-center justify-between rounded-md border p-3">
                <p className="text-sm">Enforce Host Allowlist</p>
                <Switch
                  checked={formState.enforce_host_allowlist}
                  onCheckedChange={(checked) =>
                    setFormState((prev) => ({
                      ...prev,
                      enforce_host_allowlist: checked,
                    }))
                  }
                />
              </div>

              <Form.Field name="host_allowlist_csv">
                <Form.Label>Host Allowlist (CSV)</Form.Label>
                <Input
                  value={formState.host_allowlist_csv}
                  onChange={(event) =>
                    setFormState((prev) => ({
                      ...prev,
                      host_allowlist_csv: event.target.value,
                    }))
                  }
                  placeholder="127.0.0.1,localhost"
                />
              </Form.Field>
            </div>
          </CardContent>
          <CardFooter className="border-t px-6 py-4 gap-3">
            <Button type="button" variant="outline" onClick={onTest} loading={testing}>
              Test Connectivity
            </Button>
            <Form.Submit asChild>
              <Button type="submit" loading={saving}>
                Save Integration Settings
              </Button>
            </Form.Submit>
            {isLoading && (
              <p className="text-xs text-muted-foreground">Loading integration settings...</p>
            )}
          </CardFooter>
        </Card>
      </div>
    </Form.Root>
  );
}
