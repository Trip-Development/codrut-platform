#!/usr/bin/env bash
#
# Cheia îngustă a urcării cu aprobare din GitHub — plicul 243 (A1).
#
# Se instalează ca /usr/local/sbin/cody-urcare.sh (root:root 0750) și e comanda FORȚATĂ a cheii
# `cody-urcare-<loc>` din authorized_keys (`restrict,command="/usr/local/sbin/cody-urcare.sh"`).
# Cheia nu poate cere nimic în afara verbelor de mai jos: nu are shell, nu citește .env, nu
# schimbă scriptul. Comanda vine numai din SSH_ORIGINAL_COMMAND.
#
# IEȘIREA E PUBLICĂ (depozitul e public, jurnalul rulării la fel): se tipăresc numai cuvintele
# de mai jos — niciun număr din bază, nicio adresă, niciun rând din .env. Fără xtrace.
#
# Verbe: stare · setari · fereastra · martori inainte <id> · martori dupa <id> · jurnal <id>
#        pune <sha> <id> (tokenul GHCR pe stdin) · intoarce <id> · retine <id>
# Bazele de date (db, redis) nu se repornesc niciodată.
set -euo pipefail
umask 077

CONF="${CODY_URCARE_CONF:-/etc/cody-urcare.conf}"
STARE_DIR=/var/lib/cody-urcare
LOG_FILE=/var/log/cody-urcare.log
LOCK_FILE=/var/lock/cody-urcare.lock
LIB_DIR=/usr/local/lib/cody-urcare
ENV_FILE=.env
GITHUB_REPO=Trip-Development/codrut-platform
SANATATE_INTERNA=http://127.0.0.1:8000/api/health/ready
# shellcheck source=/dev/null
source "$CONF"

nepermis() {
  echo "comandă nepermisă"
  exit 64
}

# --- citirea comenzii ------------------------------------------------------------------------
read -r -a CUV <<< "${SSH_ORIGINAL_COMMAND:-}" || true
N=${#CUV[@]}
(( N > 0 )) || nepermis
VERB="${CUV[0]}"
ID=""
SHA=""
este_id() { [[ "$1" =~ ^[0-9]{1,20}$ ]]; }
este_sha() { [[ "$1" =~ ^[0-9a-f]{40}$ ]]; }
case "$VERB" in
  stare|setari|fereastra)
    (( N == 1 )) || nepermis ;;
  martori)
    (( N == 3 )) || nepermis
    [[ "${CUV[1]}" == inainte || "${CUV[1]}" == dupa ]] || nepermis
    este_id "${CUV[2]}" || nepermis
    ID="${CUV[2]}" ;;
  jurnal|intoarce|retine)
    (( N == 2 )) || nepermis
    este_id "${CUV[1]}" || nepermis
    ID="${CUV[1]}" ;;
  pune)
    (( N == 3 )) || nepermis
    este_sha "${CUV[1]}" || nepermis
    este_id "${CUV[2]}" || nepermis
    SHA="${CUV[1]}"
    ID="${CUV[2]}" ;;
  *)
    nepermis ;;
esac

mkdir -p "$STARE_DIR"
echo "$(date -u +%FT%TZ) ${VERB}${CUV[1]:+ ${CUV[1]}} ${ID}" >> "$LOG_FILE" 2>/dev/null || true
# Curățenie: dosarele rulărilor mai vechi de 30 de zile, numai în dosarul scriptului.
find "$STARE_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

cd "$DIR"
read -r -a FISIERE_COMPOSE <<< "$COMPOSE_FILES"
compose_cu() {
  local env_file="$1"
  shift
  local -a argumente=(compose --env-file "$env_file")
  local f
  for f in "${FISIERE_COMPOSE[@]}"; do argumente+=(-f "$f"); done
  docker "${argumente[@]}" "$@"
}
compose() { compose_cu "$ENV_FILE" "$@"; }

imaginea() {
  local id
  id="$(compose ps -q "$1" 2>/dev/null </dev/null || true)"
  [[ -n "$id" ]] || { echo "(oprit)"; return 0; }
  docker inspect --format '{{.Config.Image}}' "$id" 2>/dev/null </dev/null || echo "(necunoscut)"
}

psql_citire() {
  compose exec -T "$SERV_DB" sh -c \
    'psql -X -q -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' 2>/dev/null
}

migrarea() {
  printf 'select version_num from alembic_version;\n' \
    | psql_citire | grep -vE '^(BEGIN|ROLLBACK)$' | grep -E '^[0-9A-Za-z_]+$' | head -1
}

sanatatea_interna() {
  compose exec -T "$SERV_BACKEND" python -c \
    "import urllib.request as u; print(u.urlopen('${SANATATE_INTERNA}', timeout=10).status)" \
    2>/dev/null </dev/null | tr -dc '0-9' || true
}

valoarea_din_env() {
  awk -F= -v k="$1" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "$2"
}

# --- verbele de citire -----------------------------------------------------------------------
fa_stare() {
  echo "loc=${LOC}"
  echo "backend=$(imaginea "$SERV_BACKEND")"
  echo "worker=$(imaginea "$SERV_WORKER")"
  echo "frontend=$(imaginea "$SERV_FRONTEND")"
  echo "migrare=$(migrarea || echo '(necitit)')"
  local s
  s="$(sanatatea_interna)"
  echo "sanatate_interna=${s:-000}"
}

# Lista e SCRISĂ AICI, nu primită din GitHub (P61 §2 pct. 1b).
SETARI_CITITE=(
  CODRUT_VERTEX_TIMEOUT_EVALUATOR_REPLICA_SECONDS CODRUT_VERTEX_TIMEOUT_SECONDS
  CODRUT_VERTEX_REGION CODRUT_VERTEX_ACTOR_MODEL CODRUT_VERTEX_EVALUATOR_MODEL
  CODRUT_GENERATION_PROVIDER CODRUT_GENERATION_ENGINES CODRUT_THINKING_BUDGET_EVALUATOR
  CODRUT_THINKING_BUDGET_ACTOR
)
fa_setari() {
  local v val
  for v in "${SETARI_CITITE[@]}"; do
    if val="$(compose exec -T "$SERV_BACKEND" printenv "$v" 2>/dev/null </dev/null)"; then
      echo "${v}=${val}"
    else
      echo "${v}=(nesetat)"
    fi
  done
  # Valorile efective (P61 1c-a/1c-b), fără niciun apel spre model.
  compose exec -T "$SERV_BACKEND" python -c '
from codrut.core.config import get_settings as g
from codrut.modules.practice.prompts import CODY_PROMPT_VERSION as V
s = g()
print("prompt=" + str(V))
print("provider=" + str(s.generation_provider))
print("regiunea=" + str(s.vertex_region))
print("actor=" + str(s.vertex_actor_model))
print("profesor=" + str(s.vertex_evaluator_model))
print("gandire_profesor=" + str(s.thinking_budget_evaluator))
print("gandire_actor=" + str(s.thinking_budget_actor))
print("timp=%s %s" % (s.vertex_timeout_seconds, s.vertex_timeout_evaluator_replica_seconds))
try:
    from codrut.modules.practice import motoare as m
    print("motoare=" + ",".join(m.citeste_lista(s)))
except Exception:
    print("motoare=(modul absent)")
' 2>/dev/null </dev/null | grep -E '^(prompt|provider|regiunea|actor|profesor|gandire_profesor|gandire_actor|timp|motoare)=' \
    || echo "efective=(necitite)"
}

SQL_ACTIVITATE="begin transaction read only;
select 'ACTIVITATE|trimiteri_15min', count(*) filter (where submitted_at >= now() - interval '15 minutes') from questionnaire_responses;
select 'ACTIVITATE|atingeri_15min', count(*) filter (where updated_at >= now() - interval '15 minutes') from questionnaire_responses;
select 'ACTIVITATE_CODY|replici_15min', count(*) from practice_turns where created_at >= now() - interval '15 minutes';
select 'ACTIVITATE_CODY|sesiuni_atinse_15min', count(*) from practice_sessions where greatest(started_at, coalesce(updated_at, started_at)) >= now() - interval '15 minutes';
rollback;"

fa_fereastra() {
  local randuri linie valoare citite=0 ocupat=0
  randuri="$(printf '%s\n' "$SQL_ACTIVITATE" | psql_citire || true)"
  while IFS= read -r linie; do
    [[ "$linie" == ACTIVITATE* ]] || continue
    citite=$((citite + 1))
    valoare="${linie##*|}"
    [[ "$valoare" == 0 ]] || ocupat=1
  done <<< "$randuri"
  if (( citite == 4 && ocupat == 0 )); then
    echo "fereastra=libera"
  else
    echo "fereastra=ocupata"
  fi
}

# Martorii (din p60/p61-martori-productie.sh): număr | amprentă pe rânduri, fără nume.
SQL_MARTORI="begin transaction read only;
select 'MARTOR|questionnaire_assignments', count(*), md5(coalesce(string_agg(t::text, '|' order by t::text), '')) from questionnaire_assignments t;
select 'MARTOR|questionnaire_responses', count(*), md5(coalesce(string_agg(t::text, '|' order by t::text), '')) from questionnaire_responses t;
select 'MARTOR|scoring_results', count(*), md5(coalesce(string_agg(t::text, '|' order by t::text), '')) from scoring_results t;
select 'MARTOR|result_publications_fara_updated_at', count(*), md5(coalesce(string_agg((to_jsonb(t) - 'updated_at')::text, '|' order by (to_jsonb(t) - 'updated_at')::text), '')) from result_publications t;
select 'MARTOR|competency_scores', count(*), md5(coalesce(string_agg(id::text, '|' order by id), '')) from competency_scores;
select 'MARTOR|practice_sessions', count(*) from practice_sessions;
select 'MARTOR|email_sends', count(*) from email_sends;
select 'MARTOR|company_projects_show_results', count(*) filter (where show_participant_results) from company_projects;
select 'MARTOR|practice_max_sessions', md5(coalesce(string_agg(max_sessions_per_day::text, ',' order by max_sessions_per_day), '')) from practice_program_settings;
rollback;"
# Numai aceștia au voie să crească în timpul urcării (oamenii pot exersa după ea).
POT_CRESTE="competency_scores practice_sessions"

citeste_martorii() { printf '%s\n' "$SQL_MARTORI" | psql_citire | grep -E '^MARTOR\|' || true; }

fa_martori_inainte() {
  local d="$STARE_DIR/$ID" m
  mkdir -p "$d"
  m="$(citeste_martorii)"
  [[ -n "$m" ]] || { echo "martori_inainte=necitit"; exit 1; }
  printf '%s\n' "$m" > "$d/inainte"
  echo "martori_inainte=scris"
  echo "martori=$(grep -c '^MARTOR|' "$d/inainte")"
}

fa_martori_dupa() {
  local d="$STARE_DIR/$ID" acum linie nume rand_nou nou_n vechi_n verdict rai=0
  [[ -s "$d/inainte" ]] || { echo "martori_dupa_refuzat=lipsa_inainte"; exit 65; }
  acum="$(citeste_martorii)"
  printf '%s\n' "$acum" > "$d/dupa"
  while IFS= read -r linie; do
    [[ "$linie" == MARTOR\|* ]] || continue
    nume="$(cut -d'|' -f2 <<< "$linie")"
    rand_nou="$(grep -F "MARTOR|${nume}|" "$d/dupa" | head -1 || true)"
    [[ -n "$rand_nou" ]] || rand_nou="$(grep -Fx "MARTOR|${nume}" "$d/dupa" | head -1 || true)"
    if [[ "$rand_nou" == "$linie" ]]; then
      verdict=identic
    elif [[ -z "$rand_nou" ]]; then
      verdict=SCHIMBAT
    else
      vechi_n="$(cut -d'|' -f3 <<< "$linie")"
      nou_n="$(cut -d'|' -f3 <<< "$rand_nou")"
      if [[ "$vechi_n" =~ ^[0-9]+$ && "$nou_n" =~ ^[0-9]+$ ]] && (( nou_n < vechi_n )); then
        verdict=SCAZUT
      elif [[ " $POT_CRESTE " == *" $nume "* && "$vechi_n" =~ ^[0-9]+$ && "$nou_n" =~ ^[0-9]+$ ]] \
           && (( nou_n > vechi_n )); then
        verdict=crescut
      else
        verdict=SCHIMBAT
      fi
    fi
    [[ "$verdict" == identic || "$verdict" == crescut ]] || rai=1
    echo "${nume}=${verdict}"
  done < "$d/inainte"
  if (( rai == 0 )); then echo "martori=buni"; else echo "martori=RAI"; exit 1; fi
}

fa_jurnal() {
  local id jurnal
  id="$(compose ps -q "$SERV_BACKEND" 2>/dev/null </dev/null || true)"
  [[ -n "$id" ]] || { echo "jurnal=(backend oprit)"; exit 1; }
  jurnal="$(docker logs "$id" 2>&1 </dev/null || true)"
  echo "traceback=$(grep -c 'Traceback' <<< "$jurnal" || true)"
  echo "campul_vechi=$(grep -c 'ultima_replica_om=' <<< "$jurnal" || true)"
  echo "fara_nota_timp=$(grep -c 'motiv=timp' <<< "$jurnal" || true)"
}

# --- verbele care scriu (sub lacăt) ------------------------------------------------------------
exec 9>"$LOCK_FILE"
lacat() { flock -n 9 || { echo "lacat=ocupat"; exit 75; }; }

PAS=""
pas() { PAS="$1"; }
picat() { echo "${PAS}=PICAT"; exit 1; }

NOU_ENV=""
COMPOSE_COPII=()
curata_pune() {
  docker logout ghcr.io >/dev/null 2>&1 || true
  [[ -n "$NOU_ENV" && -f "$NOU_ENV" ]] && rm -f "$NOU_ENV"
  return 0
}

aduce_compose() {
  # Fișierele compose de la `sha`, prin API, cu copie înainte și validare (ca cody-test-deploy.sh).
  local -a surse
  read -r -a surse <<< "$COMPOSE_SURSE"
  local i f nou cod
  for i in "${!FISIERE_COMPOSE[@]}"; do
    f="${FISIERE_COMPOSE[$i]}"
    nou="$(mktemp)"
    cod="$(curl -sS -o "$nou" -w '%{http_code}' \
      -H "Authorization: Bearer ${GHCR_TOKEN}" -H 'Accept: application/vnd.github.raw' \
      "https://api.github.com/repos/${GITHUB_REPO}/contents/${surse[$i]}?ref=${SHA}" \
      2>/dev/null || echo 000)"
    if [[ "$cod" != 200 || ! -s "$nou" ]]; then rm -f "$nou"; return 1; fi
    if ! cmp -s "$nou" "$f"; then
      cp -a "$f" "${f}.inainte-de-urcare-${ID}"
      COMPOSE_COPII+=("$f")
      cp "$nou" "$f"
    fi
    rm -f "$nou"
  done
}

reface_compose() {
  local f
  for f in ${COMPOSE_COPII[@]+"${COMPOSE_COPII[@]}"}; do
    cp -a "${f}.inainte-de-urcare-${ID}" "$f"
  done
}

fa_pune() {
  lacat
  trap curata_pune EXIT
  local d="$STARE_DIR/$ID" be fe inainte dupa
  mkdir -p "$d"
  be="${IMAGINE_REPO}-backend:${ETICHETA}${SHA}"
  fe="${IMAGINE_REPO}-frontend:${ETICHETA}${SHA}"

  pas tokenul
  GHCR_TOKEN=""
  IFS= read -r GHCR_TOKEN || true
  [[ -n "$GHCR_TOKEN" ]] || picat
  echo "tokenul=ok"

  if [[ "$LOC" == live ]]; then
    pas capacitatea
    bash "$LIB_DIR/check_vps_capacity.sh" preflight / 85 8 >/dev/null 2>&1 || picat
    echo "capacitatea=ok"
  fi

  pas intoarcerea_pregatita
  bash "$LIB_DIR/capture_codrut_rollback.sh" previous-images.env .env.rollback >/dev/null 2>&1 \
    || picat
  echo "intoarcerea_pregatita=ok"

  pas imaginile_aduse
  printf '%s\n' "$GHCR_TOKEN" | docker login ghcr.io -u cody-urcare --password-stdin \
    >/dev/null 2>&1 || picat
  docker pull "$be" >/dev/null 2>&1 || picat
  docker pull "$fe" >/dev/null 2>&1 || picat
  echo "imaginile_aduse=ok"

  pas compose_adus
  if ! aduce_compose; then reface_compose; picat; fi
  if ! compose config >/dev/null 2>&1; then reface_compose; picat; fi
  echo "compose_adus=ok"

  pas env_nou
  NOU_ENV="${ENV_FILE}.next"
  awk -v be="$be" -v fe="$fe" -v sha="$SHA" '
    BEGIN { b = f = s = 0 }
    /^BACKEND_IMAGE=/ { print "BACKEND_IMAGE=" be; b = 1; next }
    /^FRONTEND_IMAGE=/ { print "FRONTEND_IMAGE=" fe; f = 1; next }
    /^CODRUT_RELEASE_SHA=/ { print "CODRUT_RELEASE_SHA=" sha; s = 1; next }
    { print }
    END {
      if (!b) print "BACKEND_IMAGE=" be
      if (!f) print "FRONTEND_IMAGE=" fe
      if (!s) print "CODRUT_RELEASE_SHA=" sha
    }' "$ENV_FILE" > "$NOU_ENV" || { reface_compose; picat; }
  chmod 0600 "$NOU_ENV"
  if ! compose_cu "$NOU_ENV" config >/dev/null 2>&1; then reface_compose; picat; fi
  echo "env_nou=ok"

  pas migrarea
  inainte="$(migrarea || true)"
  [[ -n "$inainte" ]] || { reface_compose; picat; }
  printf '%s\n' "$inainte" > "$d/migrare-inainte"
  compose_cu "$NOU_ENV" run --rm -T "$SERV_BACKEND" alembic upgrade head >/dev/null 2>&1 \
    </dev/null || { reface_compose; picat; }
  if [[ "$LOC" == live ]]; then
    compose_cu "$NOU_ENV" run --rm -T "$SERV_BACKEND" python -m \
      codrut.tools.reconcile_result_publications >/dev/null 2>&1 </dev/null \
      || { reface_compose; picat; }
  fi
  echo "migrarea=ok"

  pas serviciile
  mv "$NOU_ENV" "$ENV_FILE"
  NOU_ENV=""
  chmod 0600 "$ENV_FILE"
  compose up -d --force-recreate --no-build --pull never --wait \
    "$SERV_BACKEND" "$SERV_WORKER" "$SERV_FRONTEND" >/dev/null 2>&1 </dev/null || picat
  echo "serviciile=ok"

  pas imaginile_verificate
  [[ "$(imaginea "$SERV_BACKEND")" == "$be" ]] || picat
  [[ "$(imaginea "$SERV_WORKER")" == "$be" ]] || picat
  [[ "$(imaginea "$SERV_FRONTEND")" == "$fe" ]] || picat
  if [[ "$LOC" == live ]]; then
    bash "$LIB_DIR/assert_codrut_release.sh" "$be" "$fe" >/dev/null 2>&1 || picat
  fi
  echo "imaginile_verificate=ok"

  pas sanatatea
  [[ "$(sanatatea_interna)" == 200 ]] || picat
  echo "sanatatea=ok"

  dupa="$(migrarea || true)"
  printf '%s\n' "$dupa" > "$d/migrare-dupa"
  echo "pus=da"
  if [[ "$inainte" == "$dupa" ]]; then echo "migrare_schimbata=nu"; else echo "migrare_schimbata=da"; fi
}

fa_intoarce() {
  lacat
  local d="$STARE_DIR/$ID"
  if [[ ! -s "$d/migrare-inainte" || ! -s "$d/migrare-dupa" || ! -s .env.rollback ]]; then
    echo "intoarcere_refuzata=lipsa_stare"; exit 1
  fi
  if ! cmp -s "$d/migrare-inainte" "$d/migrare-dupa"; then
    echo "intoarcere_refuzata=migrare"; exit 1
  fi
  local be fe
  be="$(valoarea_din_env BACKEND_IMAGE .env.rollback)"
  fe="$(valoarea_din_env FRONTEND_IMAGE .env.rollback)"
  [[ -n "$be" && -n "$fe" ]] || { echo "intoarcere_refuzata=lipsa_stare"; exit 1; }
  cp -a "$ENV_FILE" "${ENV_FILE}.inainte-de-intoarcere-${ID}"
  cp -a .env.rollback "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
  pas serviciile
  compose up -d --force-recreate --no-build --pull never --wait \
    "$SERV_BACKEND" "$SERV_WORKER" "$SERV_FRONTEND" >/dev/null 2>&1 </dev/null || picat
  pas sanatatea
  [[ "$(sanatatea_interna)" == 200 ]] || picat
  echo "intors=da"
  echo "backend=$(imaginea "$SERV_BACKEND")"
  echo "frontend=$(imaginea "$SERV_FRONTEND")"
}

fa_retine() {
  lacat
  local cb cf pb pf
  cb="$(valoarea_din_env BACKEND_IMAGE "$ENV_FILE")"
  cf="$(valoarea_din_env FRONTEND_IMAGE "$ENV_FILE")"
  pb="$(valoarea_din_env BACKEND_IMAGE previous-images.env 2>/dev/null || true)"
  pf="$(valoarea_din_env FRONTEND_IMAGE previous-images.env 2>/dev/null || true)"
  if bash "$LIB_DIR/retain_codrut_images.sh" "$cb" "$pb" "$cf" "$pf" >/dev/null 2>&1; then
    echo "retinere=ok"
  else
    echo "retinere=de_curatat_manual"
  fi
}

case "$VERB" in
  stare) fa_stare ;;
  setari) fa_setari ;;
  fereastra) fa_fereastra ;;
  martori) if [[ "${CUV[1]}" == inainte ]]; then fa_martori_inainte; else fa_martori_dupa; fi ;;
  jurnal) fa_jurnal ;;
  pune) fa_pune ;;
  intoarce) fa_intoarce ;;
  retine) fa_retine ;;
esac
