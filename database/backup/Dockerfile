# =============================================================================
# InnovaCX — Backup Service Container
# =============================================================================
# Minimal Alpine image with:
#   - postgresql14-client : pg_dump, pg_restore, psql
#   - gnupg               : gpg symmetric encryption
#   - gzip                : compression (included in Alpine base)
#
# NO cron daemon — scheduling is handled by a pure shell sleep loop
# in entrypoint.sh. This avoids the setpgid permission error that
# dcron triggers in unprivileged Docker containers.
# =============================================================================

FROM alpine:3.19

RUN apk add --no-cache \
    postgresql14-client \
    gnupg \
    tzdata

# Copy scripts into the container
COPY backup.sh       /usr/local/bin/backup.sh
COPY restore_test.sh /usr/local/bin/restore_test.sh
COPY entrypoint.sh   /usr/local/bin/entrypoint.sh

# Normalize Windows line endings and make all scripts executable
RUN sed -i 's/\r$//' /usr/local/bin/backup.sh \
    && sed -i 's/\r$//' /usr/local/bin/restore_test.sh \
    && sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/backup.sh \
              /usr/local/bin/restore_test.sh \
              /usr/local/bin/entrypoint.sh

# The backup volume will be mounted at /backups
RUN mkdir -p /backups

CMD ["/bin/sh", "/usr/local/bin/entrypoint.sh"]
