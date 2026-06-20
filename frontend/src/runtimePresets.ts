import type { CameraSource, MovementTarget, RuntimeConfigRequest, RuntimeMode } from "./types";

export interface RuntimeRouting {
  runtime_mode: RuntimeMode;
  dry_run: boolean;
  robot_movement_target: MovementTarget;
  camera_source: CameraSource;
}

export function isPhysicalRuntime(runtime: Partial<RuntimeRouting> | null | undefined): boolean {
  if (!runtime) {
    return false;
  }
  return (
    runtime.runtime_mode === "live" &&
    runtime.dry_run === false &&
    runtime.robot_movement_target === "physical" &&
    runtime.camera_source === "robot"
  );
}

export function isSimulatedRuntime(runtime: Partial<RuntimeRouting> | null | undefined): boolean {
  return !isPhysicalRuntime(runtime);
}

export function physicalRuntimePreset(reason?: string): RuntimeConfigRequest {
  return {
    runtime_mode: "live",
    dry_run: false,
    robot_movement_target: "physical",
    camera_source: "robot",
    operator_confirmed: true,
    reason: reason ?? "Operator enabled physical mode: live robots and onboard cameras.",
  };
}

export function simulatedRuntimePreset(reason?: string): RuntimeConfigRequest {
  return {
    runtime_mode: "simulation",
    dry_run: true,
    robot_movement_target: "virtual",
    camera_source: "pc",
    operator_confirmed: true,
    reason: reason ?? "Operator enabled simulated mode: virtual twins and PC camera.",
  };
}

export function routingFromPreset(preset: RuntimeConfigRequest): RuntimeRouting {
  return {
    runtime_mode: preset.runtime_mode,
    dry_run: preset.dry_run,
    robot_movement_target: preset.robot_movement_target ?? "virtual",
    camera_source: preset.camera_source ?? "pc",
  };
}

export function syncRoutingWithRuntime(
  runtimeMode: RuntimeMode,
  dryRun: boolean,
  current: RuntimeRouting,
): RuntimeRouting {
  if (runtimeMode === "live" && !dryRun) {
    return {
      runtime_mode: "live",
      dry_run: false,
      robot_movement_target: "physical",
      camera_source: "robot",
    };
  }
  if (runtimeMode === "simulation" || dryRun) {
    return {
      runtime_mode: runtimeMode === "live" ? "simulation" : runtimeMode,
      dry_run: true,
      robot_movement_target: "virtual",
      camera_source: "pc",
    };
  }
  return {
    ...current,
    runtime_mode: runtimeMode,
    dry_run: dryRun,
  };
}
