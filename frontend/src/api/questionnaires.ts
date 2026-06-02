export type QuestionnaireDefinitionStub = {
  id: string;
  name: string;
  status: "planned" | "draft" | "active";
};

export async function listQuestionnaireDefinitionStubs(): Promise<QuestionnaireDefinitionStub[]> {
  return [
    { id: "pcm-baseline", name: "PCM baseline", status: "planned" },
    { id: "phase-a", name: "Phase A", status: "planned" },
    { id: "distress-drivers", name: "Distress drivers", status: "planned" },
  ];
}
