import { TrainerRouteLoading } from "@/components/shell/route-loading";

export default function TrainerQuestionnairesLoading() {
  return (
    <TrainerRouteLoading
      title="Chestionare"
      activeHref="/trainer/questionnaires"
      kind="editor"
      loadingLabel="Pregătim catalogul de chestionare"
    />
  );
}
