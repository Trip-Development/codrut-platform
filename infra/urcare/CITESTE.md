# Cheia îngustă a urcării (plicul 243)

1. `cody-urcare.sh` → `/usr/local/sbin/cody-urcare.sh` (`root:root 0750`), din vârful lui 243-A1 (`sha256sum` comparat).
2. Ajutătoarele din `.github/scripts/` (`capture_codrut_rollback.sh`, `assert_codrut_release.sh`, `check_vps_capacity.sh`, `retain_codrut_images.sh`) → `/usr/local/lib/cody-urcare/` (`root 0755`); cheia nu le poate rescrie.
3. `/etc/cody-urcare.conf` (`root 0600`) după `cody-urcare.conf.exemplu`: `LOC=proba` sau `LOC=live`.
4. `authorized_keys`: copie înainte (`authorized_keys.inainte-de-243`), apoi UN rând: `restrict,command="/usr/local/sbin/cody-urcare.sh" <cheia publică> cody-urcare-<loc>`.
5. Încercare de pe Mac, numai citiri: `ssh -i <cheie> root@<gazda> stare` → `loc=<loc>`; `… id` → cod 64.
6. În GitHub, mediul (`proba` / `production`): secretele `URCARE_SSH_KEY`, `URCARE_HOST`, variabila `URCARE_KNOWN_HOSTS` (din `known_hosts`-ul Mac-ului, nu din `ssh-keyscan`).
7. Verbele și ce tipăresc: antetul scriptului. Ieșirea e publică — numai cuvinte, nicio cifră din bază.
8. `.env` NU se mai rescrie din secretele GitHub pe calea asta: se schimbă numai `BACKEND_IMAGE`, `FRONTEND_IMAGE`, `CODRUT_RELEASE_SHA`. Un secret schimbat în GitHub ajunge pe live numai pe calea veche (`deploy-vps.yml`).
9. Un pachet care schimbă `_deploy-vps.yml` e oprit pe calea asta (urcă pe calea veche).
10. Întoarcerea singură se face numai dacă migrarea bazei nu s-a schimbat la `pune`.
11. Starea fiecărei rulări: `/var/lib/cody-urcare/<id>/` (martori și migrare, fără nume); se curăță singură după 30 de zile.
12. Jurnalul apelurilor: `/var/log/cody-urcare.log` (verb, id, ora).
13. Cheia veche root (`SSH_PRIVATE_KEY`, mediul `prod`) rămâne pentru calea veche; se scoate numai printr-un plic separat, după trei urcări bune.
14. Testele: `cd .github/scripts && python3 -m unittest test_cody_urcare` (docker/curl/flock falși).
15. Scoaterea: ștergi rândul din `authorized_keys` (sau pui copia înapoi), apoi scriptul, `/usr/local/lib/cody-urcare/` și `/etc/cody-urcare.conf`.
