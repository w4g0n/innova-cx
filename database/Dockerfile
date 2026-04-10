FROM postgres:14.22-alpine

# Alpine Linux compiles PostgreSQL with --sysconfdir=/etc/postgresql, so
# initdb generates a postgresql.conf that hardcodes:
#   hba_file = '/etc/postgresql/pg_hba.conf'
#
# The stock image does not create /etc/postgresql/, which causes Docker's
# bind-mount to create the mount-point as a DIRECTORY (not a file) when the
# parent path doesn't exist. PostgreSQL then crashes with:
#   FATAL: could not load pg_hba.conf: "Is a directory"
#
# Pre-creating the file here ensures Docker overlays the bind-mount as a
# file-over-file, which is reliable on all Docker host configurations.
RUN mkdir -p /etc/postgresql && touch /etc/postgresql/pg_hba.conf
