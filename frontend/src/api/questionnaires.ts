export type QuestionnaireDefinitionStub = {
  id: string;
  name: string;
  description: string;
  status: "planned" | "draft" | "active";
  version?: number;
  source?: string;
  audience: "leadership" | "team" | "participant";
  estimatedItems?: number;
};

export async function listQuestionnaireDefinitionStubs(): Promise<QuestionnaireDefinitionStub[]> {
  return [
    {
      id: "lencioni",
      name: "Lencioni team assessment",
      description: "15 item team assessment with five dysfunction scoring groups.",
      status: "active",
      version: 1,
      source: "docs/questionnaires/lencioni.pdf",
      audience: "team",
      estimatedItems: 15,
    },
    {
      id: "distress-drivers",
      name: "Distress drivers",
      description: "10 scored statement sets for TA driver self-assessment.",
      status: "active",
      version: 1,
      source: "docs/questionnaires/distress_drivers.pdf",
      audience: "leadership",
      estimatedItems: 50,
    },
    {
      id: "pcm-baseline",
      name: "PCM baseline",
      description: "Source pending. Will use the same versioned definition format.",
      status: "planned",
      audience: "leadership",
    },
    {
      id: "phase-a",
      name: "Phase",
      description: "Source pending. Will use the same reusable questionnaire renderer.",
      status: "planned",
      audience: "leadership",
    },
    {
      id: "boss-360",
      name: "Boss / manager 360",
      description: "Source pending. Assignment targets remain many-to-many capable.",
      status: "planned",
      audience: "participant",
    },
  ];
}
