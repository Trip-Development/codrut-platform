import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";

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

export type QuestionnaireScaleOption = {
  value: number | string;
  label: string;
  description?: string;
};

export type QuestionnaireStatement = {
  id: string;
  code: string;
  label: string;
  scoring?: Record<string, string>;
  scale?: QuestionnaireScaleOption[];
};

export type QuestionnaireQuestion = {
  id: string;
  code: string;
  type: "likert" | "statement_score_set" | "single_choice";
  label: string;
  required: boolean;
  instructions?: string;
  scale: QuestionnaireScaleOption[];
  statements?: QuestionnaireStatement[];
};

export type QuestionnaireAnswerValue = number | string;

export type QuestionnaireSection = {
  id: string;
  title: string;
  questions: QuestionnaireQuestion[];
};

export type QuestionnaireDefinition = {
  key: string;
  version: number;
  title: string;
  description: string;
  active?: boolean;
  schema: {
    schema_version: string;
    source?: {
      path?: string;
      status?: string;
      type?: string;
    };
    audience?: "leadership" | "team" | "participant";
    instructions?: string;
    sections: QuestionnaireSection[];
    scoring?: Record<string, unknown>;
  };
};

export type QuestionnaireResponseRecord = {
  id: string;
  assignment_id: string;
  questionnaire_key: string;
  questionnaire_version: number;
  status: "draft" | "submitted";
  answers: Record<string, QuestionnaireAnswerValue>;
};

const seededAssignmentQuestionnaires: Record<string, string> = {
  "11111111-1111-4111-8111-111111111111": "lencioni",
  "22222222-2222-4222-8222-222222222222": "boss_360",
  "33333333-3333-4333-8333-333333333333": "lencioni",
};

const legacyHiddenQuestionnaireKeys = new Set(["icare", "phase", "boss_360_en"]);

function stubFromDefinition(definition: QuestionnaireDefinition): QuestionnaireDefinitionStub {
  const questions = definition.schema.sections.flatMap((section) => section.questions);
  const estimatedItems = questions.reduce((count, question) => {
    return count + (question.statements?.length ?? 1);
  }, 0);
  const audience =
    definition.schema.audience ??
    (definition.key === "distress_drivers" ? "leadership" : "team");

  return {
    id: definition.key,
    name: definition.title,
    description: definition.description,
    status: definition.active === false ? "draft" : "active",
    version: definition.version,
    source: definition.schema.source?.path,
    audience,
    estimatedItems,
  };
}

function latestDefinitionStubs(
  stubs: QuestionnaireDefinitionStub[],
): QuestionnaireDefinitionStub[] {
  const latestByKey = new Map<string, QuestionnaireDefinitionStub>();
  for (const stub of stubs) {
    const current = latestByKey.get(stub.id);
    if ((stub.version ?? 1) > (current?.version ?? 0)) {
      latestByKey.set(stub.id, stub);
    }
  }
  return Array.from(latestByKey.values()).sort((a, b) => a.name.localeCompare(b.name));
}

const fallbackDefinitions: QuestionnaireDefinitionStub[] = [
  {
    id: "lencioni",
    name: "Lencioni - evaluare echipă (RO)",
    description: "15 itemi pentru evaluarea echipei pe cele cinci disfuncții Lencioni.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/lencioni.pdf",
    audience: "team",
    estimatedItems: 15,
  },
  {
    id: "lencioni_en",
    name: "Lencioni Team Assessment (EN)",
    description: "15 items for assessing the team against Lencioni's five dysfunctions.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/lencioni.pdf",
    audience: "team",
    estimatedItems: 15,
  },
  {
    id: "distress_drivers",
    name: "Driveri de stres TA (RO)",
    description: "10 seturi de afirmații pentru autoevaluarea driverilor de stres TA.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/distress_drivers.pdf",
    audience: "leadership",
    estimatedItems: 50,
  },
  {
    id: "distress_drivers_en",
    name: "TA Distress Drivers (EN)",
    description: "10 scored statement sets for TA driver self-assessment.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/distress_drivers.pdf",
    audience: "leadership",
    estimatedItems: 50,
  },
  {
    id: "pcm_base",
    name: "Baza și faza PCM",
    description: "Alegere ghidată pentru baza și faza PCM din profilul participantului.",
    status: "active",
    version: 1,
    audience: "leadership",
    estimatedItems: 2,
  },
  {
    id: "boss_360",
    name: "iCARE 360 pentru manager",
    description: "Feedback comportamental iCARE pentru manager din autoevaluare, colegi și raportori direcți.",
    status: "active",
    version: 1,
    audience: "participant",
    estimatedItems: 48,
  },
];

const icareFourPointScale: QuestionnaireScaleOption[] = [
  { value: 1, label: "Rar" },
  { value: 2, label: "Uneori" },
  { value: 3, label: "Frecvent" },
  { value: 4, label: "Întotdeauna" },
];

const fallbackDefinitionDetails: Record<string, QuestionnaireDefinition> = {
  icare: {
    key: "icare",
    version: 1,
    title: "Comportamente de leadership ICARE",
    description:
      "Evaluare comportamentală pe atributele ICARE. Versiune provizorie cu scală în 4 trepte, pregătită pentru ajustarea scalei finale.",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "leadership",
      source: {
        type: "xlsx",
        path: "docs/questionnaires/ICARE_scala.xlsx",
        status: "provisional",
      },
      instructions:
        "Alege frecvența care descrie cel mai bine comportamentul observat. Scala curentă are 4 opțiuni și poate fi modificată fără rescrierea itemilor.",
      scoring: {
        scale_status: "provisional_4_point",
        source_columns_used: ["2; Rar / 25%", "3; Uneori / 50%", "4; Frecvent / 75%", "5; Întotdeauna / 100%"],
        source_column_excluded_for_now: "1; Niciodată / 0%",
      },
      sections: [
        {
          id: "inspiring",
          title: "Inspirație",
          questions: [
            {
              id: "icare_inspiring_developing_people",
              code: "ICARE-1.1",
              type: "statement_score_set",
              label: "Dezvoltarea oamenilor",
              required: true,
              instructions: "Dezvoltare continuă prin feedback constructiv, încurajare și follow-up.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_01", code: "S1", label: "Oferă feedback constructiv" },
                { id: "icare_02", code: "S2", label: "Sprijină planurile de dezvoltare" },
                { id: "icare_03", code: "S3", label: "Se implică în propria dezvoltare continuă" },
              ],
            },
            {
              id: "icare_inspiring_leading_by_example",
              code: "ICARE-1.2",
              type: "statement_score_set",
              label: "Conducere prin exemplu",
              required: true,
              instructions: "Aliniere între valori, angajamente și comportamentul zilnic.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_04", code: "S1", label: "Acționează conform valorilor declarate" },
                { id: "icare_05", code: "S2", label: "Respectă angajamentele asumate față de echipă" },
                { id: "icare_06", code: "S3", label: "Tratează toți membrii echipei cu respect și echitate" },
              ],
            },
            {
              id: "icare_inspiring_engagement_environment",
              code: "ICARE-1.3",
              type: "statement_score_set",
              label: "Crearea unui mediu care stimulează implicarea",
              required: true,
              instructions: "Mediu sigur, energizant și orientat către contribuția fiecărui membru.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_07", code: "S1", label: "Creează spațiu psihologic sigur pentru exprimare" },
                { id: "icare_08", code: "S2", label: "Delegă cu sens, nu doar cu sarcini" },
                { id: "icare_09", code: "S3", label: "Recunoaște contribuția individuală la succesul echipei" },
              ],
            },
          ],
        },
        {
          id: "create_trust",
          title: "Construirea încrederii",
          questions: [
            {
              id: "icare_trust_collaboration",
              code: "ICARE-2.1",
              type: "statement_score_set",
              label: "Promotor al colaborării",
              required: true,
              instructions: "Transparență, colaborare și prioritizarea interesului comun.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_10", code: "S1", label: "Verifică înțelegerea comună după discuții" },
                { id: "icare_11", code: "S2", label: "Împărtășește context și motivații proprii" },
                { id: "icare_12", code: "S3", label: "Prioritizează interesul comun față de cel personal sau al echipei" },
              ],
            },
            {
              id: "icare_trust_inspired",
              code: "ICARE-2.2",
              type: "statement_score_set",
              label: "Inspirație împărtășită",
              required: true,
              instructions: "Sens, ambiție și angajament construite împreună cu echipa.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_13", code: "S1", label: "Conectează munca echipei la un scop mai larg" },
                { id: "icare_14", code: "S2", label: "Co-construiește ambiții îndrăznețe cu echipa" },
                { id: "icare_15", code: "S3", label: "Inspiră prin propriul nivel de angajament" },
              ],
            },
            {
              id: "icare_trust_reality",
              code: "ICARE-2.3",
              type: "statement_score_set",
              label: "Ancorare în realitate",
              required: true,
              instructions: "Ascultare activă, informații relevante și realism onest.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_16", code: "S1", label: "Ascultă activ înainte de a răspunde sau decide" },
                { id: "icare_17", code: "S2", label: "Împărtășește informații relevante proactiv" },
                { id: "icare_18", code: "S3", label: "Recunoaște faptele neplăcute cu onestitate" },
              ],
            },
            {
              id: "icare_trust_illuminating",
              code: "ICARE-2.4",
              type: "statement_score_set",
              label: "Clarificare",
              required: true,
              instructions: "Claritate strategică în contexte complexe și incerte.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_19", code: "S1", label: "Comunică strategia și direcția cu claritate" },
                { id: "icare_20", code: "S2", label: "Oferă claritate în situații de ambiguitate" },
                { id: "icare_21", code: "S3", label: "Acționează cu claritate în medii complexe și incerte" },
              ],
            },
          ],
        },
        {
          id: "awareness",
          title: "Conștientizare",
          questions: [
            {
              id: "icare_awareness_humility",
              code: "ICARE-3.1",
              type: "statement_score_set",
              label: "Modestie",
              required: true,
              instructions: "Feedback, limite personale și integrarea perspectivelor diferite.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_22", code: "S1", label: "Solicită feedback despre propriul comportament" },
                { id: "icare_23", code: "S2", label: "Știe când să ceară ajutor sau să admită că nu știe" },
                { id: "icare_24", code: "S3", label: "Integrează perspectivele diferite de a sa în decizii" },
              ],
            },
            {
              id: "icare_awareness_emotional_intelligence",
              code: "ICARE-3.2",
              type: "statement_score_set",
              label: "Inteligență emoțională și situațională",
              required: true,
              instructions: "Autoreglare, interes autentic și adaptarea comunicării.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_25", code: "S1", label: "Recunoaște și gestionează propriile emoții în interacțiuni" },
                { id: "icare_26", code: "S2", label: "Arată interes autentic față de oameni ca indivizi" },
                { id: "icare_27", code: "S3", label: "Adaptează comunicarea la stilul și nevoile interlocutorului" },
              ],
            },
            {
              id: "icare_awareness_open_world",
              code: "ICARE-3.3",
              type: "statement_score_set",
              label: "Deschidere către lume",
              required: true,
              instructions: "Curiozitate, benchmarkuri externe și facilitarea schimbării.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_28", code: "S1", label: "Caută activ benchmarkuri și tendințe externe" },
                { id: "icare_29", code: "S2", label: "Îmbrățișează și facilitează schimbarea" },
                { id: "icare_30", code: "S3", label: "Explorează activ domenii adiacente sau noi tehnologii" },
              ],
            },
          ],
        },
        {
          id: "results",
          title: "Rezultate",
          questions: [
            {
              id: "icare_results_ambitious",
              code: "ICARE-4.1",
              type: "statement_score_set",
              label: "Ambiție asumată pentru companie",
              required: true,
              instructions: "Inovație, asumarea riscului și învățare din performanță.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_31", code: "S1", label: "Propune soluții inovatoare și îndrăznețe" },
                { id: "icare_32", code: "S2", label: "Promovează asumarea responsabilă a riscului" },
                { id: "icare_33", code: "S3", label: "Urmărește performanța și învață din eșecuri" },
              ],
            },
            {
              id: "icare_results_caring",
              code: "ICARE-4.2",
              type: "statement_score_set",
              label: "Grijă egală pentru angajați și clienți",
              required: true,
              instructions: "Echilibru între performanță, bunăstarea echipei și standarde realiste.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_34", code: "S1", label: "Echilibrează presiunile de performanță cu bunăstarea echipei" },
                { id: "icare_35", code: "S2", label: "Acordă atenție echilibrului muncă-viață al membrilor echipei" },
                { id: "icare_36", code: "S3", label: "Construiește standarde înalte bazate pe înțelegerea realității" },
              ],
            },
            {
              id: "icare_results_agility",
              code: "ICARE-4.3",
              type: "statement_score_set",
              label: "Agilitate antreprenorială",
              required: true,
              instructions: "Testare rapidă, simplificare și conectarea rețelei externe la oportunități.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_37", code: "S1", label: "Testează și învață rapid (test & learn)" },
                { id: "icare_38", code: "S2", label: "Livrează rezultate mai rapid prin simplificare și prioritizare" },
                { id: "icare_39", code: "S3", label: "Conectează rețeaua externă la oportunități de business" },
              ],
            },
          ],
        },
        {
          id: "empowerment",
          title: "Împuternicire",
          questions: [
            {
              id: "icare_empowerment_decision_making",
              code: "ICARE-5.1",
              type: "statement_score_set",
              label: "Decizie aproape de teren",
              required: true,
              instructions: "Autonomie, inițiativă și raportare transparentă.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_40", code: "S1", label: "Delegă autoritatea decizională la nivelul potrivit" },
                { id: "icare_41", code: "S2", label: "Ia inițiativă și acționează fără să aștepte permisiunea" },
                { id: "icare_42", code: "S3", label: "Setează obiective clare și raportează transparent rezultatele" },
              ],
            },
            {
              id: "icare_empowerment_collective_intelligence",
              code: "ICARE-5.2",
              type: "statement_score_set",
              label: "Cultivarea inteligenței colective",
              required: true,
              instructions: "Diversitate, co-construcție, decizii asumate și refuzul compromisului facil.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_43", code: "S1", label: "Susține decizia finală chiar dacă diferă de propria opinie" },
                { id: "icare_44", code: "S2", label: "Caută și oferă sfaturi fără a impune soluții" },
                { id: "icare_45", code: "S3", label: "Refuză compromisul sistematic în favoarea soluțiilor mai bune" },
              ],
            },
            {
              id: "icare_empowerment_helping_team",
              code: "ICARE-5.3",
              type: "statement_score_set",
              label: "Sprijinirea echipei",
              required: true,
              instructions: "Contribuție la dinamica echipei, deblocare și sharing de cunoaștere.",
              scale: icareFourPointScale,
              statements: [
                { id: "icare_46", code: "S1", label: "Alimentează dinamica și energia pozitivă a echipei" },
                { id: "icare_47", code: "S2", label: "Facilitează deblocarea obstacolelor pentru colegii din echipă" },
                { id: "icare_48", code: "S3", label: "Dezvoltă competențele echipei prin sharing de cunoaștere" },
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
    title: "Feedback 360 pentru manager",
    description: "Formular scurt de feedback confidențial pentru persoana către care raportezi.",
    schema: {
      schema_version: "questionnaire.v1",
      source: {
        type: "prototype",
        path: "seeded/boss_360",
        status: "provisional",
      },
      instructions:
        "Răspunde concret și echilibrat. Persoana evaluată nu primește răspunsurile individuale.",
      sections: [
        {
          id: "manager_feedback",
          title: "Feedback manager",
          questions: [
            {
              id: "boss_360_q01",
              code: "Q1",
              type: "likert",
              label: "Managerul meu clarifică așteptările și prioritățile.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q02",
              code: "Q2",
              type: "likert",
              label: "Managerul meu oferă feedback util și la timp.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q03",
              code: "Q3",
              type: "likert",
              label: "Managerul meu creează spațiu pentru întrebări și opinii diferite.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q04",
              code: "Q4",
              type: "likert",
              label: "Managerul meu susține colaborarea în echipă.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q05",
              code: "Q5",
              type: "likert",
              label: "Managerul meu gestionează tensiunile într-un mod constructiv.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
          ],
        },
      ],
    },
  },
};

fallbackDefinitionDetails.boss_360 = {
  ...fallbackDefinitionDetails.icare,
  key: "boss_360",
  title: "Feedback 360 iCARE pentru manager",
  description:
    "Feedback comportamental iCARE pentru manager din autoevaluare, colegi și raportori direcți.",
  schema: {
    ...fallbackDefinitionDetails.icare.schema,
    audience: "participant",
    instructions:
      "Răspunde pentru persoana indicată în sarcină. Evaluează comportamentele iCARE observabile din perspectiva ta.",
    scoring: undefined,
  },
};

fallbackDefinitionDetails.boss_360_en = {
  ...fallbackDefinitionDetails.boss_360,
  key: "boss_360_en",
  title: "iCARE 360 Feedback for Manager",
  description:
    "iCARE behavioral feedback for a manager from self, manager peers, and direct reports.",
};

export async function listQuestionnaireDefinitionStubs(
  includeRetired = false,
  options: { latestOnly?: boolean } = {},
): Promise<QuestionnaireDefinitionStub[]> {
  const latestOnly = options.latestOnly ?? true;
  try {
    const url = includeRetired
      ? `${getApiBaseUrl()}/forms/definitions?include_retired=true`
      : `${getApiBaseUrl()}/forms/definitions`;
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return isDemoFallbackEnabled() ? fallbackDefinitions : [];
    }
    const serverDefs = (await response.json()) as QuestionnaireDefinition[];
    const stubs = serverDefs
      .filter((definition) => !legacyHiddenQuestionnaireKeys.has(definition.key))
      .map(stubFromDefinition);
    return latestOnly ? latestDefinitionStubs(stubs) : stubs;
  } catch (e) {
    console.error("Error listing definitions", e);
    const fallback = isDemoFallbackEnabled() ? fallbackDefinitions : [];
    return latestOnly ? latestDefinitionStubs(fallback) : fallback;
  }
}

export async function getQuestionnaireDefinition(
  key: string,
): Promise<QuestionnaireDefinition | null> {
  const [realKey, versionStr] = key.split("@");
  const targetVersion = versionStr ? parseInt(versionStr) : null;

  try {
    const url = targetVersion
      ? `${getApiBaseUrl()}/forms/definitions/${realKey}?version=${targetVersion}`
      : `${getApiBaseUrl()}/forms/definitions/${realKey}`;
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return isDemoFallbackEnabled() ? (fallbackDefinitionDetails[realKey] ?? null) : null;
    }
    return (await response.json()) as QuestionnaireDefinition;
  } catch (e) {
    console.error("Error getting definition", e);
    return isDemoFallbackEnabled() ? (fallbackDefinitionDetails[realKey] ?? null) : null;
  }
}

export async function createQuestionnaireDefinitionOnServer(
  definition: Omit<QuestionnaireDefinition, "version"> & { active?: boolean }
): Promise<QuestionnaireDefinition> {
  const response = await fetch(`${getApiBaseUrl()}/forms/definitions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      key: definition.key,
      title: definition.title,
      description: definition.description,
      schema: definition.schema,
      active: definition.active ?? true,
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut crea chestionarul pe server.");
  }
  return (await response.json()) as QuestionnaireDefinition;
}

export async function updateQuestionnaireDefinitionOnServer(
  key: string,
  fields: { title?: string; description?: string; schema?: any; active?: boolean }, // eslint-disable-line @typescript-eslint/no-explicit-any
  version?: number
): Promise<QuestionnaireDefinition> {
  const url = version
    ? `${getApiBaseUrl()}/forms/definitions/${key}?version=${version}`
    : `${getApiBaseUrl()}/forms/definitions/${key}`;
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      title: fields.title,
      description: fields.description,
      schema: fields.schema,
      active: fields.active,
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut actualiza chestionarul pe server.");
  }
  return (await response.json()) as QuestionnaireDefinition;
}

export async function activateQuestionnaireDefinitionOnServer(
  key: string,
  version: number
): Promise<QuestionnaireDefinition> {
  const response = await fetch(`${getApiBaseUrl()}/forms/definitions/${key}/versions/${version}/activate`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut activa versiunea chestionarului.");
  }
  return (await response.json()) as QuestionnaireDefinition;
}

export async function deleteQuestionnaireDefinitionOnServer(
  key: string,
  version?: number,
): Promise<QuestionnaireDefinition> {
  const url = version
    ? `${getApiBaseUrl()}/forms/definitions/${key}?version=${version}`
    : `${getApiBaseUrl()}/forms/definitions/${key}`;
  const response = await fetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut pensiona chestionarul.");
  }
  return (await response.json()) as QuestionnaireDefinition;
}

export async function getQuestionnaireResponse(
  assignmentId: string,
  options: RequestInit = {},
): Promise<QuestionnaireResponseRecord | null> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return {
      id: `seeded-${assignmentId}-draft`,
      assignment_id: assignmentId,
      questionnaire_key: seededAssignmentQuestionnaires[assignmentId],
      questionnaire_version: 1,
      status: "draft",
      answers: {},
    };
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response`, {
      cache: "no-store",
      credentials: "include",
      ...options,
      headers: {
        ...(options.headers ?? {}),
      },
    });
    if (!response.ok) return null;
    return (await response.json()) as QuestionnaireResponseRecord;
  } catch {
    return null;
  }
}

export async function saveQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "draft");
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      throw await responseError(response, "Nu am putut salva draftul.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut salva draftul.");
  }
}

export async function submitQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "submitted");
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      throw await responseError(response, "Nu am putut trimite răspunsurile.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut trimite răspunsurile.");
  }
}

function canUseSeededAssignmentFallback(assignmentId: string): boolean {
  return isDemoFallbackEnabled() && Boolean(seededAssignmentQuestionnaires[assignmentId]);
}

async function responseError(response: Response, fallbackMessage: string): Promise<Error> {
  const payload =
    typeof response.json === "function" ? await response.json().catch(() => null) : null;
  const message = payload?.error?.message ?? fallbackMessage;
  return new Error(message);
}

function normalizeResponseError(error: unknown, fallbackMessage: string): Error {
  if (error instanceof Error) return error;
  return new Error(fallbackMessage);
}

function seededQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
  status: "draft" | "submitted",
): QuestionnaireResponseRecord {
  const questionnaireKey = seededAssignmentQuestionnaires[assignmentId];

  if (!questionnaireKey) {
    throw new Error(status === "draft" ? "Nu am putut salva draftul." : "Nu am putut trimite răspunsurile.");
  }

  return {
    id: `seeded-${assignmentId}-${status}`,
    assignment_id: assignmentId,
    questionnaire_key: questionnaireKey,
    questionnaire_version: 1,
    status,
    answers,
  };
}
