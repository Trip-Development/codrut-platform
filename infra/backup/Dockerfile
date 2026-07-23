FROM restic/restic:0.18.1 AS restic

FROM postgres:18-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/codrut-backup /restore /var/cache/restic \
    && chown -R postgres:postgres /restore /var/cache/restic

COPY --from=restic /usr/bin/restic /usr/local/bin/restic
COPY infra/backup/ /opt/codrut-backup/

RUN chmod 0555 /opt/codrut-backup/*.sh \
    && restic version | grep -F 'restic 0.18.1'

USER postgres

ENV RESTIC_CACHE_DIR=/var/cache/restic

ENTRYPOINT ["/opt/codrut-backup/entrypoint.sh"]
CMD ["backup"]
