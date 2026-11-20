/**
 * Integration points for the visualization team.
 *
 * The data layer (contracts/, api/, state/) is final. Everything visual is a
 * replaceable slot. Provide your own components via <AutoRedUIProvider>; any
 * slot you omit falls back to the minimal unstyled default.
 *
 *   <AutoRedUIProvider components={{ Commander: AnimatedCommander, Specialist: AnimatedAgent }}>
 *     <MissionScreen ... />
 *   </AutoRedUIProvider>
 *
 * Colors: reference agents via CSS custom properties `var(--autored-agent-<id>)`
 * (see agentColorVar). Defaults live in defaults/tokens.css; override them freely.
 */
import { createContext, useContext, type ComponentType, type ReactNode } from "react";
import type { AgentId, AgentInfo, AutoRedEvent, CapabilityPayload, FindingPayload, MissionPhase, PlanPayload } from "../contracts/events";
import type { AgentView } from "../state/missionReducer";
import * as D from "./defaults";

export const agentColorVar = (id: AgentId) => `var(--autored-agent-${id})`;

export interface CommanderSlotProps {
  agent: AgentView;               // includes .cue (animation intent), .activity, .tasks
  phase: MissionPhase;
  message: string;
  capabilities: CapabilityPayload | null;
  plan: PlanPayload | null;
  selected: boolean;
  onSelect: () => void;
}

export interface SpecialistSlotProps {
  agent: AgentView;
  info: AgentInfo;                // name, stable slot 1..4
  findings: FindingPayload[];     // this agent's findings
  selected: boolean;
  onSelect: () => void;
}

export interface BrowserViewSlotProps {
  agentId: AgentId;
  frameSrc: string | null;        // object URL of the latest JPEG frame
  url: string | null;
  contextId: string | null;
  expanded: boolean;
  onToggleExpand: () => void;
}

export interface TimelineSlotProps {
  events: AutoRedEvent[];
  selectedAgent: AgentId | null;
  onSelectAgent: (id: AgentId) => void;
}

export interface FindingsSlotProps {
  findings: FindingPayload[];
  artifactUrl: (name: string) => string;
}

export interface AutoRedComponents {
  Commander: ComponentType<CommanderSlotProps>;
  Specialist: ComponentType<SpecialistSlotProps>;
  BrowserView: ComponentType<BrowserViewSlotProps>;
  Timeline: ComponentType<TimelineSlotProps>;
  Findings: ComponentType<FindingsSlotProps>;
}

const defaults: AutoRedComponents = {
  Commander: D.DefaultCommander,
  Specialist: D.DefaultSpecialist,
  BrowserView: D.DefaultBrowserView,
  Timeline: D.DefaultTimeline,
  Findings: D.DefaultFindings,
};

const SlotContext = createContext<AutoRedComponents>(defaults);

export function AutoRedUIProvider({ components, children }: { components?: Partial<AutoRedComponents>; children: ReactNode }) {
  return <SlotContext.Provider value={{ ...defaults, ...components }}>{children}</SlotContext.Provider>;
}

export const useSlots = () => useContext(SlotContext);
