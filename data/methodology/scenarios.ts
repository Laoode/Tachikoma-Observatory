export interface ScenarioDefinition {
  id: string;
  title: string;
  category: string;
}

export const SCENARIOS: ScenarioDefinition[] = [
  {
    id: "TC-001",
    title: "Direct Specialist Match",
    category: "Tool Selection",
  },

  {
    id: "TC-002",
    title: "Distractor Resistance",
    category: "Tool Selection",
  },

  {
    id: "TC-003",
    title: "Implicit Tool Need",
    category: "Tool Selection",
  },

  {
    id: "TC-004",
    title: "Unit Handling",
    category: "Parameter Precision",
  },

  {
    id: "TC-005",
    title: "Date and Time Parsing",
    category: "Parameter Precision",
  },

  {
    id: "TC-006",
    title: "Multi-Value Extraction",
    category: "Parameter Precision",
  },

  {
    id: "TC-007",
    title: "Search → Read → Act",
    category: "Multi-Step Chains",
  },

  {
    id: "TC-008",
    title: "Conditional Branching",
    category: "Multi-Step Chains",
  },

  {
    id: "TC-009",
    title: "Parallel Independence",
    category: "Multi-Step Chains",
  },

  {
    id: "TC-010",
    title: "Trivial Knowledge",
    category: "Restraint & Refusal",
  },

  {
    id: "TC-011",
    title: "Simple Math",
    category: "Restraint & Refusal",
  },

  {
    id: "TC-012",
    title: "Impossible Request",
    category: "Restraint & Refusal",
  },

  {
    id: "TC-013",
    title: "Empty Results",
    category: "Error Recovery",
  },

  {
    id: "TC-014",
    title: "Malformed Response",
    category: "Error Recovery",
  },

  {
    id: "TC-015",
    title: "Conflicting Information",
    category: "Error Recovery",
  },
];