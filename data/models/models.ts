export interface ModelDefinition {
  id: string;
  name: string;
  provider: string;
  logo: string;
}

export const MODELS: ModelDefinition[] = [
  {
    id: "minicpm5-1b",
    name: "MiniCPM5-1B",
    provider: "OpenBMB",
    logo: "/models/minicpm.png",
  },

  {
    id: "lfm2.5-8b-a1b",
    name: "LFM2.5-8B-A1B",
    provider: "Liquid AI",
    logo: "/models/liquid.png",
  },

  {
    id: "qwen3.5-0.8b",
    name: "Qwen3.5-0.8B",
    provider: "Alibaba",
    logo: "/models/qwen.png",
  },

  {
    id: "qwen3.5-2b",
    name: "Qwen3.5-2B",
    provider: "Alibaba",
    logo: "/models/qwen.png",
  },

  {
    id: "qwen3.5-4b",
    name: "Qwen3.5-4B",
    provider: "Alibaba",
    logo: "/models/qwen.png",
  },

  {
    id: "gemma4-e2b",
    name: "Gemma 4 E2B",
    provider: "Google",
    logo: "/models/gemma.png",
  },
];