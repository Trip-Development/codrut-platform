import type {
  QuestionnaireDefinition,
  QuestionnaireDefinitionStub,
  QuestionnaireScaleOption,
} from "./questionnaires";

const agreementScale: QuestionnaireScaleOption[] = [
  { value: 1, label: "Deloc" },
  { value: 2, label: "Parțial" },
  { value: 3, label: "În mare măsură" },
];

const frequencyScale: QuestionnaireScaleOption[] = [
  { value: 1, label: "Rar" },
  { value: 2, label: "Uneori" },
  { value: 3, label: "Des" },
  { value: 4, label: "Foarte des" },
];

export const SYNTHETIC_QUESTIONNAIRE_STUBS: QuestionnaireDefinitionStub[] = [
  {
    id: "lencioni",
    name: "Mostră sintetică: colaborare în echipă",
    description: "Două întrebări fictive pentru verificarea fluxului de echipă.",
    status: "active",
    version: 1,
    audience: "team",
    estimatedItems: 2,
  },
  {
    id: "distress_drivers",
    name: "Mostră sintetică: stil de lucru",
    description: "Două afirmații fictive pentru verificarea unei autoevaluări.",
    status: "active",
    version: 1,
    audience: "leadership",
    estimatedItems: 2,
  },
  {
    id: "pcm_base",
    name: "Mostră sintetică: profil participant",
    description: "O alegere fictivă pentru verificarea întrebărilor cu opțiune unică.",
    status: "active",
    version: 1,
    audience: "participant",
    estimatedItems: 1,
  },
  {
    id: "boss_360",
    name: "Mostră sintetică: feedback 360",
    description: "Două afirmații fictive pentru verificarea feedbackului despre o persoană.",
    status: "active",
    version: 1,
    audience: "participant",
    estimatedItems: 2,
  },
];

export const SYNTHETIC_QUESTIONNAIRE_DEFINITIONS: Record<string, QuestionnaireDefinition> = {
  lencioni: {
    key: "lencioni",
    version: 1,
    title: "Mostră sintetică: colaborare în echipă",
    description: "Conținut fictiv, fără material sau metodologie protejată.",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "team",
      sections: [
        {
          id: "sample_team_section",
          title: "Colaborare",
          questions: [
            {
              id: "sample_team_q1",
              code: "SYN-T1",
              type: "likert",
              label: "Echipa stabilește clar următorul pas după o discuție.",
              required: true,
              scale: agreementScale,
            },
            {
              id: "sample_team_q2",
              code: "SYN-T2",
              type: "likert",
              label: "Membrii echipei cer clarificări când informația este incompletă.",
              required: true,
              scale: agreementScale,
            },
          ],
        },
      ],
    },
  },
  distress_drivers: {
    key: "distress_drivers",
    version: 1,
    title: "Mostră sintetică: stil de lucru",
    description: "Conținut fictiv, fără material sau metodologie protejată.",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "leadership",
      sections: [
        {
          id: "sample_work_section",
          title: "Preferințe de lucru",
          questions: [
            {
              id: "sample_work_q1",
              code: "SYN-W1",
              type: "statement_score_set",
              label: "Afirmații demonstrative",
              required: true,
              scale: frequencyScale,
              statements: [
                {
                  id: "sample_work_s1",
                  code: "S1",
                  label: "Îmi rezerv timp pentru a verifica dacă am înțeles cerința.",
                },
                {
                  id: "sample_work_s2",
                  code: "S2",
                  label: "Cer ajutor când o sarcină depășește informațiile disponibile.",
                },
              ],
            },
          ],
        },
      ],
    },
  },
  pcm_base: {
    key: "pcm_base",
    version: 1,
    title: "Mostră sintetică: profil participant",
    description: "Conținut fictiv pentru verificarea unei alegeri unice.",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "participant",
      sections: [
        {
          id: "sample_profile_section",
          title: "Profil demonstrativ",
          questions: [
            {
              id: "sample_profile_q1",
              code: "SYN-P1",
              type: "single_choice",
              label: "Alege varianta de demonstrație.",
              required: true,
              scale: [
                { value: "sample_a", label: "Varianta A" },
                { value: "sample_b", label: "Varianta B" },
              ],
            },
          ],
        },
      ],
    },
  },
  boss_360: {
    key: "boss_360",
    version: 1,
    title: "Mostră sintetică: feedback 360",
    description: "Conținut fictiv pentru verificarea evaluării unei persoane.",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "participant",
      sections: [
        {
          id: "sample_feedback_section",
          title: "Feedback demonstrativ",
          questions: [
            {
              id: "sample_feedback_q1",
              code: "SYN-F1",
              type: "likert",
              label: "Persoana clarifică rezultatul așteptat al unei activități.",
              required: true,
              scale: frequencyScale,
            },
            {
              id: "sample_feedback_q2",
              code: "SYN-F2",
              type: "likert",
              label: "Persoana solicită perspective înainte de o decizie importantă.",
              required: true,
              scale: frequencyScale,
            },
          ],
        },
      ],
    },
  },
};
