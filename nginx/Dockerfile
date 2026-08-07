FROM nginx:latest
# Drop stock conf.d so no stale config lingers in the image layers.
RUN rm -f /etc/nginx/conf.d/*.conf
COPY default.conf /etc/nginx/conf.d/default.conf
