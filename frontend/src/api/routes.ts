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
    description: "Client cu care lucrezi în prezent.",
  },
  {
    id: "past_known_contact",
    label: "Tip 2",
    description: "Client cu care ai lucrat în trecut și știi persoana căreia îi trimiți emailul.",
  },
  {
    id: "past_unknown_contact",
    label: "Tip 3",
    description: "Client cu care ai lucrat în trecut și nu știi persoana căreia îi trimiți emailul.",
  },
  {
    id: "new_prospect",
    label: "Tip 4",
    description: "Client cu care nu ai mai lucrat.",
  },
];

export const campaignWorkflowSteps: CampaignWorkflowStep[] = [
  { id: "segment", label: "Împărțim baza de date în funcție de tip client" },
  { id: "copy_review", label: "Redactăm emailul și verificăm template-ul" },
  { id: "host_video", label: "Host film pe pagina Codruț cu video în R2" },
  { id: "template", label: "Template email cu prenumele completat automat" },
  { id: "send", label: "Trimitem emailul" },
  { id: "follow_up", label: "Setăm notificări Calendly și formular de contact" },
];

export const campaignMetrics = ["open rate", "click rate", "view rate"] as const;
export const campaignOutcomeFlags = ["intalnire", "ofertare", "contract"] as const;

export const accessRoutes: AudienceRoute[] = [
  {
    href: "/invite/demo-token",
    label: "Am invitație",
    description: "Pentru participanți care completează chestionarele direct din linkul primit pe email.",
    audience: "invitee",
  },
  {
    href: "/participant",
    label: "Cont leadership",
    description: "Pentru manageri și membri de leadership care urmăresc mai multe sarcini în timp.",
    audience: "leadership",
  },
  {
    href: "/trainer/login",
    label: "Trainer login",
    description: "Acces separat pentru Andrei, owner și echipa care gestionează livrarea.",
    audience: "trainer",
  },
];

export const trainerWorkflowRoutes: AudienceRoute[] = [
  {
    href: "/trainer",
    label: "Livrare și completare",
    description: "Primul ecran pentru status invitații, progres companii și următoarele acțiuni.",
    audience: "trainer",
  },
  {
    href: "/trainer/projects",
    label: "Proiecte",
    description: "Spațiul pentru companii, roster, echipe și configurarea intake-ului.",
    audience: "trainer",
  },
  {
    href: "/trainer/questionnaires",
    label: "Chestionare",
    description: "Catalogul PCM, Lencioni, 360 și driveri de distres.",
    audience: "trainer",
  },
  {
    href: "/trainer/email",
    label: "Șabloane email",
    description: "Texte reutilizabile și arhiva globală; invitațiile se trimit din workspace-ul proiectului.",
    audience: "trainer",
  },
];

export const participantWorkflowRoutes: AudienceRoute[] = [
  {
    href: "/invite/demo-token",
    label: "Link securizat",
    description: "Fără cont pentru membrii invitați: toate sarcinile proiectului într-un singur loc.",
    audience: "invitee",
  },
  {
    href: "/participant/questionnaires",
    label: "Chestionare",
    description: "Runner reutilizabil pentru formularul activ și progresul de completare.",
    audience: "leadership",
  },
  {
    href: "/participant/account",
    label: "Cont și progres",
    description: "Pentru leadership: sarcini recurente, progres și revenire în platformă.",
    audience: "leadership",
  },
];
