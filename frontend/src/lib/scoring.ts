export const COMPETENCY_LEVEL_DESCRIPTIONS: Record<string, string> = {
  INTEGRARE: "E reflex automat — apare și sub stres, fără efort conștient.",
  CONSOLIDARE: "Folosit consecvent în situații variate; cere puțin efort conștient.",
  APLICARE: "Folosit ocazional, când contextul e favorabil și există atenție.",
  CONȘTIENTIZARE: "Înțeles ca noțiune; încă nu apare constant în practică.",
};

export const COMPETENCY_LEVEL_COLORS: Record<string, string> = {
  INTEGRARE: "#639922",
  CONSOLIDARE: "#1A4A7A",
  APLICARE: "#BA7517",
  CONȘTIENTIZARE: "#E24B4A",
};

export function roleplayXp(score: number): number {
  if (score <= 0) return 0;
  const calculated = Math.ceil(score / 20.0);
  return Math.min(5, Math.max(1, calculated));
}

export function quizXp(percent: number): number {
  if (percent <= 0) return 0;
  const calculated = Math.round(percent / 10.0);
  return Math.min(10, Math.max(0, calculated));
}

export function streakBonusPct(streakDays: number): number {
  if (streakDays >= 30) return 20;
  if (streakDays >= 14) return 15;
  if (streakDays >= 7) return 10;
  if (streakDays >= 3) return 5;
  return 0;
}

export function evidenceCeiling(projectDays: number): number {
  return Math.max(500, Math.round((projectDays * 100) / 12.0));
}

export function masteryLevel(score: number): string {
  if (score < 25) return "CONȘTIENTIZARE";
  if (score < 50) return "APLICARE";
  if (score < 75) return "CONSOLIDARE";
  return "INTEGRARE";
}

export interface ScoreItem {
  score: number;
  createdAt: string;
  sourceType?: string;
}

export interface CompetencyEvidence {
  level: "INTEGRARE" | "CONSOLIDARE" | "APLICARE" | "CONȘTIENTIZARE";
  levelDescription: string;
  color: string;
  totalRoleplays: number;
  scores70Count: number;
  daysSpan70: number;
  distinctDays70: number;
  averageScore: number;
  whyNotHigher: string;
}

export function computeDailyXp(
  entries: Array<{ sourceType: string; score: number; createdAt: string }>,
): number {
  let total = 0;
  for (const item of entries) {
    const normSource = (item.sourceType || "session").toLowerCase();
    if (["test_in", "test_out", "test-in", "test-out"].includes(normSource)) {
      continue;
    }
    if (["cunostinte", "quiz", "knowledge"].includes(normSource)) {
      total += quizXp(item.score);
    } else {
      total += roleplayXp(item.score);
    }
  }
  return Math.min(100, total);
}

export function computeStreak(
  datesList: string[],
  referenceDateStr?: string,
): number {
  if (!datesList || datesList.length === 0) return 0;

  const dateObjects = datesList
    .map((d) => new Date(d).toISOString().slice(0, 10))
    .filter((v, i, a) => a.indexOf(v) === i)
    .sort()
    .reverse();

  if (dateObjects.length === 0) return 0;

  const ref = referenceDateStr
    ? new Date(referenceDateStr).toISOString().slice(0, 10)
    : new Date().toISOString().slice(0, 10);

  const diffMs =
    new Date(ref).getTime() - new Date(dateObjects[0]).getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays > 1) return 0;

  let streak = 1;
  let currentCheck = dateObjects[0];

  for (let i = 1; i < dateObjects.length; i++) {
    const prev = dateObjects[i];
    const stepDiff = Math.floor(
      (new Date(currentCheck).getTime() - new Date(prev).getTime()) /
        (1000 * 60 * 60 * 24),
    );
    if (stepDiff === 1) {
      streak++;
      currentCheck = prev;
    } else {
      break;
    }
  }

  return streak;
}

export function computeCompetencyEvidence(
  entries: ScoreItem[],
): CompetencyEvidence {
  const validRoleplays = entries.filter((e) => {
    const src = (e.sourceType || "session").toLowerCase();
    return !["cunostinte", "quiz", "knowledge", "test_in", "test_out", "test-in", "test-out"].includes(src);
  });

  if (validRoleplays.length === 0) {
    return {
      level: "CONȘTIENTIZARE",
      levelDescription: COMPETENCY_LEVEL_DESCRIPTIONS.CONȘTIENTIZARE,
      color: COMPETENCY_LEVEL_COLORS.CONȘTIENTIZARE,
      totalRoleplays: 0,
      scores70Count: 0,
      daysSpan70: 0,
      distinctDays70: 0,
      averageScore: 0,
      whyNotHigher: "Exersează primul role-play pentru a debloca nivelul Aplicare (scor ≥50%).",
    };
  }

  const avgScore =
    Math.round(
      (validRoleplays.reduce((sum, e) => sum + e.score, 0) /
        validRoleplays.length) *
        10,
    ) / 10;

  const scores70 = validRoleplays.filter((e) => e.score >= 70);
  const scores50 = validRoleplays.filter((e) => e.score >= 50);

  const distinctDays70 = new Set(
    scores70.map((e) => new Date(e.createdAt).toISOString().slice(0, 10)),
  ).size;

  let daysSpan70 = 0;
  if (scores70.length >= 2) {
    const timestamps = scores70
      .map((e) => new Date(e.createdAt).getTime())
      .sort((a, b) => a - b);
    daysSpan70 = Math.floor(
      (timestamps[timestamps.length - 1] - timestamps[0]) /
        (1000 * 60 * 60 * 24),
    );
  }

  let level: "INTEGRARE" | "CONSOLIDARE" | "APLICARE" | "CONȘTIENTIZARE" = "CONȘTIENTIZARE";
  let whyNotHigher = "";

  if (scores70.length >= 3 && daysSpan70 >= 14) {
    level = "INTEGRARE";
    whyNotHigher = "Nivel maxim atins: reflex automat integrat în practică și testat în timp.";
  } else if (scores70.length >= 2 && distinctDays70 >= 2) {
    level = "CONSOLIDARE";
    if (scores70.length < 3) {
      whyNotHigher = "Pentru Integrare: ai nevoie de cel puțin 3 simulări cu scor ≥70% întinse pe minim 14 zile.";
    } else {
      const daysNeeded = 14 - daysSpan70;
      whyNotHigher = `Pentru Integrare: ai cele 3 scoruri ≥70%, dar intervalul actual este de ${daysSpan70} zile (necesar ≥14 zile, mai sunt ~${daysNeeded} zile de consistență).`;
    }
  } else if (scores50.length >= 1) {
    level = "APLICARE";
    whyNotHigher = "Pentru Consolidare: ai nevoie de minim 2 simulări cu scor ≥70% în cel puțin 2 zile diferite.";
  } else {
    level = "CONȘTIENTIZARE";
    whyNotHigher = "Pentru Aplicare: ai nevoie de cel puțin o simulare cu scor ≥50%.";
  }

  return {
    level,
    levelDescription: COMPETENCY_LEVEL_DESCRIPTIONS[level],
    color: COMPETENCY_LEVEL_COLORS[level],
    totalRoleplays: validRoleplays.length,
    scores70Count: scores70.length,
    daysSpan70,
    distinctDays70,
    averageScore: avgScore,
    whyNotHigher,
  };
}
