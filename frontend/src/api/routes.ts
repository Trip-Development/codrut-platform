export type AudienceRoute = {
  href: string;
  label: string;
  description: string;
  audience: "public" | "invitee" | "leadership" | "trainer";
};

export type CampaignClientType = {
  id: "current_client" | "past_known_contact" | "past_unknown_contact" | "new_prospect";
  label: string;
  description: string;
};

export type CampaignWorkflowStep = {
  id: string;
  label: string;
};

export const campaignClientTypes: CampaignClientType[] = [
  {
    id: "current_client",
    label: "Tip 1",
    description: "Client cu care lucrezi in prezent.",
  },
  {
    id: "past_known_contact",
    label: "Tip 2",
    description: "Client cu care ai lucrat in trecut si stii persoana careia ii trimiti emailul.",
  },
  {
    id: "past_unknown_contact",
    label: "Tip 3",
    description: "Client cu care ai lucrat in trecut si nu stii persoana careia ii trimiti emailul.",
  },
  {
    id: "new_prospect",
    label: "Tip 4",
    description: "Client cu care nu ai mai lucrat.",
  },
];

export const campaignWorkflowSteps: CampaignWorkflowStep[] = [
  { id: "segment", label: "Impartim baza de date in functie de tip client" },
  { id: "copy_review", label: "Redactam emailul si verificam template-ul" },
  { id: "host_video", label: "Host film pe pagina Codrut cu video in R2" },
  { id: "template", label: "Template email cu prenumele completat automat" },
  { id: "send", label: "Trimitem emailul" },
  { id: "follow_up", label: "Setam notificari Calendly si formular de contact" },
];

export const campaignMetrics = ["open rate", "click rate", "view rate"] as const;
export const campaignOutcomeFlags = ["intalnire", "ofertare", "contract"] as const;

export const accessRoutes: AudienceRoute[] = [
  {
    href: "/invite/demo-token",
    label: "Am invitatie",
    description: "Pentru participanti care completeaza chestionarele direct din linkul primit pe email.",
    audience: "invitee",
  },
  {
    href: "/participant",
    label: "Cont leadership",
    description: "Pentru manageri si membri de leadership care urmaresc mai multe sarcini in timp.",
    audience: "leadership",
  },
  {
    href: "/trainer/login",
    label: "Trainer login",
    description: "Acces separat pentru Andrei, owner si echipa care gestioneaza livrarea.",
    audience: "trainer",
  },
];

export const trainerWorkflowRoutes: AudienceRoute[] = [
  {
    href: "/trainer",
    label: "Livrare si completare",
    description: "Primul ecran pentru status invitatii, progres companii si urmatoarele actiuni.",
    audience: "trainer",
  },
  {
    href: "/trainer/projects",
    label: "Proiecte",
    description: "Spatiul pentru companii, roster, echipe si configurarea intake-ului.",
    audience: "trainer",
  },
  {
    href: "/trainer/questionnaires",
    label: "Chestionare",
    description: "Catalogul PCM, Lencioni, 360 si driveri de distres.",
    audience: "trainer",
  },
  {
    href: "/trainer/email",
    label: "Sabloane email",
    description: "Texte reutilizabile si arhiva globala; invitatiile se trimit din workspace-ul companiei.",
    audience: "trainer",
  },
];

export const participantWorkflowRoutes: AudienceRoute[] = [
  {
    href: "/invite/demo-token",
    label: "Link securizat",
    description: "Fara cont pentru membrii invitati: toate sarcinile proiectului intr-un singur loc.",
    audience: "invitee",
  },
  {
    href: "/participant/questionnaires",
    label: "Chestionare",
    description: "Runner reutilizabil pentru formularul activ si progresul de completare.",
    audience: "leadership",
  },
  {
    href: "/participant/account",
    label: "Cont si progres",
    description: "Pentru leadership: sarcini recurente, progres si revenire in platforma.",
    audience: "leadership",
  },
];
