# Lavalink v4 + YouTube plugin (pinned — bump together with application.yml notes)
FROM ghcr.io/lavalink-devs/lavalink:4

# YouTube source lives in a plugin since v4 (verified: youtube-source 1.18.2)
ADD https://github.com/lavalink-devs/youtube-source/releases/download/1.18.2/youtube-plugin-1.18.2.jar ./plugins/youtube-plugin.jar
COPY application.yml ./application.yml

# Render free tier ≈512MB RAM — cap the JVM heap
ENV JAVA_TOOL_OPTIONS="-Xmx300M"
